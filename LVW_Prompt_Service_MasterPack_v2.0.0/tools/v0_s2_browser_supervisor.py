"""Bounded parent-side transport for the native browser worker.

No CLI, process launch, authorization creation, product oracle or Stage PASS.
The sealed Stage parent supplies independent evidence handlers and an original
Popen handle; every permission waits for its handler's actual evidence result.
"""
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import re
import selectors
import threading
import time

from tools.v0_s2_public_phase import encoded

ACTIONS = frozenset(('preflight', 'browser_start', 'browser_owner', 'upload', 'public_submit',
    'case_begin', 'case_queued', 'busy_manual', 'cancel_ready', 'case_finished', 'offline_op', 'user_write'))
LIMITS = {'browser_start': 1, 'browser_owner': 1, 'upload': 1, 'public_submit': 2,
    'case_begin': 2, 'case_queued': 2, 'busy_manual': 1, 'cancel_ready': 240,
    'case_finished': 3, 'offline_op': 1, 'user_write': 16, 'preflight': 1}
MAX_LINE = 65536


class ProtocolError(ValueError):
    pass


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise ProtocolError('BROWSER_DUPLICATE_JSON_KEY')
            result[key] = value
        return result
    def constant(_): raise ProtocolError('BROWSER_NONFINITE_JSON')
    def floating(value):
        result = float(value)
        if not math.isfinite(result): raise ProtocolError('BROWSER_NONFINITE_JSON')
        return result
    try:
        if len(raw) > MAX_LINE: raise ProtocolError('BROWSER_RECORD_LIMIT')
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant, parse_float=floating)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise ProtocolError('BROWSER_INVALID_JSON') from error


class Protocol:
    """One sequence space and consumed permissions, including failed attempts.

    The supervisor calls reserve/complete only on its event-loop thread. Evidence
    handlers can overlap (e.g. user writes while offline_op runs), but cannot
    approve a dependent action before its prerequisite has completed.
    """
    def __init__(self, config):
        self.config = copy.deepcopy(config)
        for key, length in [('candidate_sha', 40), ('authorization_sha256', 64), ('protocol_nonce', 64)]:
            if not re.fullmatch('[a-f0-9]{%d}' % length, self.config.get(key, '')):
                raise ProtocolError('BROWSER_PARENT_IDENTITY_INVALID')
        expiry = self.config.get('expires_at')
        if type(expiry) not in (int, float) or not math.isfinite(expiry) or not time.time() < expiry <= time.time()+7200:
            raise ProtocolError('BROWSER_PARENT_LEASE_INVALID')
        self.sequence = 0
        self.used = dict.fromkeys(ACTIONS, 0)
        self.completed = set()
        self.pending = {}
        self.cases = {}
        self.finished = set()
        self.prompt_ids = set()

    def reserve(self, raw):
        if time.time() >= self.config['expires_at']: raise ProtocolError('BROWSER_PARENT_LEASE_EXPIRED')
        request = strict_json(raw)
        if not isinstance(request, dict) or set(request) != {'kind', 'sequence', 'protocol_nonce',
                'candidate_sha', 'authorization_sha256', 'action', 'payload'}:
            raise ProtocolError('BROWSER_REQUEST_SHAPE')
        if (request['kind'] != 'lvw.s2.browser-parent-request/1' or type(request['sequence']) is not int
                or request['sequence'] != self.sequence+1 or self.sequence >= 512):
            raise ProtocolError('BROWSER_REQUEST_SEQUENCE')
        if any(request[key] != self.config[key] for key in ('protocol_nonce', 'candidate_sha', 'authorization_sha256')):
            raise ProtocolError('BROWSER_REQUEST_IDENTITY')
        action, payload = request['action'], request['payload']
        if not isinstance(action, str) or action not in ACTIONS or not isinstance(payload, dict):
            raise ProtocolError('BROWSER_REQUEST_ACTION')
        if len(self.pending) >= 8 or self.used[action] >= LIMITS[action]:
            raise ProtocolError('BROWSER_PARENT_ACTION_LIMIT')
        if action == 'preflight' and payload.get('run_root') != self.config.get('run_root'):
            raise ProtocolError('BROWSER_REQUEST_ROOT_MISMATCH')
        if action != 'preflight' and 'preflight' not in self.completed:
            raise ProtocolError('BROWSER_PREFLIGHT_NOT_COMPLETE')
        if action not in ('preflight', 'browser_start') and 'browser_start' not in self.completed:
            raise ProtocolError('BROWSER_START_NOT_COMPLETE')
        if action not in ('preflight', 'browser_start', 'browser_owner') and 'browser_owner' not in self.completed:
            raise ProtocolError('BROWSER_OWNER_NOT_COMPLETE')
        case = payload.get('case_id')
        if action == 'case_begin':
            if case not in ('complete', 'cancel') or case in self.cases or 'upload' not in self.completed:
                raise ProtocolError('BROWSER_CASE_ORDER')
            if case == 'cancel' and 'complete' not in self.finished: raise ProtocolError('BROWSER_FIRST_CASE_INCOMPLETE')
            self.cases[case] = 'begin-pending'
        elif action == 'public_submit':
            if self.cases.get(case) != 'begun' or not isinstance(payload.get('body'), dict):
                raise ProtocolError('BROWSER_SUBMIT_NOT_ARMED')
            self.cases[case] = 'submit-pending'  # Consume before the handler can await.
        elif action == 'case_queued':
            prompt = payload.get('prompt_id')
            if (self.cases.get(case) != 'submitted' or not isinstance(prompt, str)
                    or not re.fullmatch('[a-fA-F0-9-]{1,80}', prompt) or prompt in self.prompt_ids):
                raise ProtocolError('BROWSER_QUEUE_IDENTITY')
            self.prompt_ids.add(prompt)
            self.cases[case] = 'queue-pending'
        elif action in ('busy_manual', 'cancel_ready', 'case_finished'):
            target = 'complete' if action == 'busy_manual' or case in ('analysis_before_adoption', 'complete') else 'cancel'
            if self.cases.get(target) != payload.get('prompt_id') or not isinstance(payload.get('prompt_id'), str):
                raise ProtocolError('BROWSER_CURRENT_PROMPT_REQUIRED')
            if action == 'case_finished' and (case not in ('analysis_before_adoption', 'complete', 'cancel')
                    or case in self.finished or any(q['action'] == action and q['payload'].get('case_id') == case
                        for q in self.pending.values())):
                raise ProtocolError('BROWSER_DUPLICATE_OR_INVALID_TERMINAL')
            if action == 'case_finished' and case == 'complete' and 'analysis_before_adoption' not in self.finished:
                raise ProtocolError('BROWSER_ANALYSIS_JOIN_REQUIRED')
        elif action == 'offline_op' and 'cancel' not in self.finished:
            raise ProtocolError('BROWSER_CANCEL_JOIN_REQUIRED')
        self.sequence = request['sequence']
        self.used[action] += 1
        self.pending[self.sequence] = request
        return copy.deepcopy(request)

    def complete(self, sequence, payload):
        request = self.pending.get(sequence)
        if request is None or not isinstance(payload, dict): raise ProtocolError('BROWSER_HANDLER_RESULT_INVALID')
        action, original = request['action'], request['payload']
        if action == 'preflight' and payload.get('owned_run_root') != self.config.get('run_root'):
            raise ProtocolError('BROWSER_PARENT_ROOT_UNPROVEN')
        if action == 'browser_start' and (payload.get('ephemeral_user_root_verified') is not True
                or type(payload.get('comfy_pid')) is not int or payload['comfy_pid'] <= 0):
            raise ProtocolError('BROWSER_EPHEMERAL_USER_ROOT_UNPROVEN')
        if action == 'case_finished' and original['case_id'] == 'analysis_before_adoption':
            if not isinstance(payload.get('run_token'), str) or not payload['run_token']:
                raise ProtocolError('BROWSER_ANALYSIS_TOKEN_UNPROVEN')
        if action == 'cancel_ready' and (type(payload.get('ready')) is not bool
                or (payload['ready'] and (not isinstance(payload.get('run_token'), str) or not payload['run_token']))):
            raise ProtocolError('BROWSER_CANCEL_WINDOW_UNPROVEN')
        if action == 'offline_op' and (payload.get('owned_ollama_stopped') is not True
                or type(payload.get('comfy_pid')) is not int or payload['comfy_pid'] != self.comfy_pid):
            raise ProtocolError('BROWSER_OFFLINE_STOP_UNPROVEN')
        reply = {'kind': 'lvw.s2.browser-parent-reply/1', 'sequence': sequence, 'approved': True,
            **{key: self.config[key] for key in ('candidate_sha', 'authorization_sha256', 'protocol_nonce')}, 'payload': payload}
        raw = encoded(reply)
        if len(raw.rstrip(b'\n')) > MAX_LINE: raise ProtocolError('BROWSER_REPLY_LIMIT')
        self.completed.add(action)
        if action == 'browser_start': self.comfy_pid = payload['comfy_pid']
        if action == 'case_begin': self.cases[original['case_id']] = 'begun'
        if action == 'public_submit': self.cases[original['case_id']] = 'submitted'
        if action == 'case_queued': self.cases[original['case_id']] = original['prompt_id']
        if action == 'case_finished': self.finished.add(original['case_id'])
        del self.pending[sequence]
        return raw


class Supervisor:
    """Drain both pipes while evidence callbacks and resource checks continue.

    authorize_owned_worker(process, config) must validate the ACTIVE child, exact
    source/tool/config identity and original owned process *before* any I/O here.
    Handlers receive (payload, observe); observe raises on abort/resource limits.
    They must have bounded work and call observe during waits. A stuck callback
    is explicitly unproven, never counted as successful cleanup. This component
    does not kill a browser or delete a profile based on a worker's PID claim.
    """
    def __init__(self, config, *, handlers, authorize_owned_worker, resource_observer):
        if set(handlers) != ACTIONS or any(not callable(h) for h in handlers.values()):
            raise ValueError('ALL_INDEPENDENT_BROWSER_HANDLERS_REQUIRED')
        if not callable(authorize_owned_worker) or not callable(resource_observer):
            raise ValueError('OWNED_MONITORED_PARENT_REQUIRED')
        self.protocol = Protocol(config)
        self.handlers = dict(handlers)
        self.authorize = authorize_owned_worker
        self.observer = resource_observer
        self.executed = False
        self.abort = threading.Event()
        self.observe_lock = threading.Lock()

    def observe(self):
        if self.abort.is_set(): raise ProtocolError('BROWSER_SUPERVISOR_ABORTED')
        with self.observe_lock: self.observer()

    def run(self, process, log_directory):
        if self.executed: raise ProtocolError('BROWSER_SUPERVISOR_ONE_SHOT')
        self.executed = True
        # No log creation, stream read or permission before external authority.
        self.authorize(process, copy.deepcopy(self.protocol.config))
        directory = Path(log_directory)
        expected = Path(self.protocol.config['run_root'])/'temp/browser-phase/parent'
        if directory != expected or directory.parent.resolve(strict=True) != expected.parent:
            raise ProtocolError('BROWSER_PARENT_LOG_ROOT_INVALID')
        if Path(self.protocol.config['run_root']).resolve(strict=True) != Path(self.protocol.config['run_root']):
            raise ProtocolError('BROWSER_PARENT_RUN_ROOT_NOT_CANONICAL')
        directory.mkdir(exist_ok=False)
        result = {'kind': 'BROWSER_PARENT_TRANSPORT_NOT_PRODUCT_ACCEPTANCE', 'decision': 'NO_GO',
            'stage_pass_claim': False, 'exit_code': None, 'requests': 0, 'replies': 0}
        responses = queue.Queue(maxsize=8)
        jobs, buffer = {}, bytearray()
        streams, output, errors = selectors.DefaultSelector(), None, None
        deadline = time.monotonic() + max(0, self.protocol.config['expires_at']-time.time())
        def callback(request):
            try:
                value = self.handlers[request['action']](copy.deepcopy(request['payload']), self.observe)
                responses.put_nowait((request['sequence'], value, None))
            except Exception as error:
                responses.put_nowait((request['sequence'], None, type(error).__name__+':'+str(error)))
        def append(stream, raw):
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        try:
            output = (directory/'worker.stdout.jsonl').open('xb')
            errors = (directory/'worker.stderr.log').open('xb')
            with (directory/'parent.replies.jsonl').open('xb') as replies:
                for pipe in (process.stdout, process.stderr):
                    os.set_blocking(pipe.fileno(), False); streams.register(pipe, selectors.EVENT_READ)
                # Replies <=64KiB can exceed a pipe's free capacity. Queue them
                # and drain nonblocking so a stalled worker never blocks guards.
                os.set_blocking(process.stdin.fileno(), False)
                outgoing = bytearray(); received = stderr_bytes = 0
                while streams.get_map() or jobs or outgoing:
                    self.observe()
                    if time.monotonic() >= deadline: raise ProtocolError('BROWSER_SUPERVISOR_DEADLINE')
                    for key, _ in streams.select(.05):
                        raw = os.read(key.fileobj.fileno(), 4096)
                        if not raw:
                            streams.unregister(key.fileobj)
                            if key.fileobj is process.stdout and buffer: raise ProtocolError('BROWSER_TRUNCATED_RECORD')
                            if key.fileobj is process.stdout and jobs:
                                raise ProtocolError('BROWSER_WORKER_DISCONNECTED_DURING_EVIDENCE')
                            continue
                        if key.fileobj is process.stderr:
                            stderr_bytes += len(raw)
                            if stderr_bytes > 2*1024*1024: raise ProtocolError('BROWSER_STDERR_LIMIT')
                            append(errors, raw); continue
                        received += len(raw)
                        if received > 512*(MAX_LINE+1): raise ProtocolError('BROWSER_STDOUT_LIMIT')
                        append(output, raw); buffer.extend(raw)
                        while b'\n' in buffer:
                            line, _, rest = buffer.partition(b'\n'); buffer[:] = rest
                            request = self.protocol.reserve(line)
                            result['requests'] += 1
                            thread = threading.Thread(target=callback, args=(request,), daemon=True)
                            limit = 1190 if request['action'] == 'offline_op' else 18
                            jobs[request['sequence']] = (thread, time.monotonic()+limit)
                            thread.start()
                        if len(buffer) > MAX_LINE: raise ProtocolError('BROWSER_RECORD_LIMIT')
                    while not responses.empty():
                        sequence, payload, error = responses.get_nowait()
                        if time.monotonic() >= jobs[sequence][1]: raise ProtocolError('BROWSER_EVIDENCE_HANDLER_TIMEOUT')
                        if error: raise ProtocolError('BROWSER_EVIDENCE_HANDLER_FAILED:'+error)
                        raw = self.protocol.complete(sequence, payload)
                        append(replies, raw); outgoing.extend(raw)
                        del jobs[sequence]; result['replies'] += 1
                    if outgoing:
                        try:
                            count = os.write(process.stdin.fileno(), outgoing)
                            del outgoing[:count]
                        except BlockingIOError: pass
                    if any(time.monotonic() >= stop for _, stop in jobs.values()):
                        raise ProtocolError('BROWSER_EVIDENCE_HANDLER_TIMEOUT')
                if process.wait(timeout=2) != 0: raise ProtocolError('BROWSER_WORKER_NONZERO_EXIT')
                if self.protocol.pending or not {'analysis_before_adoption', 'complete', 'cancel'} <= self.protocol.finished:
                    raise ProtocolError('BROWSER_REQUIRED_EVIDENCE_JOINS_MISSING')
                if not {'offline_op', 'browser_owner', 'busy_manual'} <= self.protocol.completed:
                    raise ProtocolError('BROWSER_REQUIRED_PERMISSIONS_MISSING')
                result['decision'] = 'TRANSPORT_COMPLETED_REQUIRES_PRODUCT_ORACLES'
        except Exception as error:
            result['error_code'] = type(error).__name__+':'+str(error)
        finally:
            self.abort.set()
            # EOF asks the worker's abort handler to close its own BrowserServer.
            # Original-process termination and independent browser/profile cleanup
            # remain the sealed parent's responsibility on any failure.
            process.stdin.close()
            for thread, _ in jobs.values(): thread.join(timeout=.05)
            result['callbacks_pending'] = sum(t.is_alive() for t, _ in jobs.values())
            result['worker_original_terminal'] = process.poll() is not None
            result['exit_code'] = process.returncode
            result['permissions_consumed'] = dict(self.protocol.used)
            result['artifacts'] = []
            streams.close()
            for stream in (output, errors):
                if stream is not None: stream.close()
            for path in sorted(directory.iterdir()):
                raw = path.read_bytes()
                result['artifacts'].append({'file': path.name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
            (directory/'supervisor-result.json').write_bytes(encoded(result))
        return result
