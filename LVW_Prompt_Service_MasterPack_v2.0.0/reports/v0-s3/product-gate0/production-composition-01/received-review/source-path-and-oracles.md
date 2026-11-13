Static exact-candidate Git object excerpts; not executed.

### tools/test_v0_s3_supervisor.py:919 run_fixture

```python
def run_fixture(tmp_path, scenario, *, rows=None, root=None, phase_seconds=1.0,
                grace_seconds=0.25, run_id=RUN_ID):
    """Run one enumerated fixture scenario under the real parent.

    The executor of the guarded runner owns the start: it charges the shared
    counter before the operating system action, it holds the original child
    handle and it enforces the independent per child deadline.  The parent
    supervisor under test never starts a process itself.
    """
    rows = rows if rows is not None else sixteen_rows()
    root = root if root is not None else (tmp_path / 'run')
    (root / 'temp/s3-quality').mkdir(parents=True, exist_ok=True)
    guard_root = os.environ.get('LVW_S3_GUARD_ROOT')
    if not guard_root:
        raise AssertionError('the guarded runner did not publish its owned root')
    executor = bound_executor()
    if executor is None:
        raise AssertionError('the guarded runner did not publish its executor')
    context = fixture_context(guard_root, root, rows, run_id=run_id)
    os.environ['LVW_S3_FIXTURE_CONTEXT'] = str(context)
    command = build_fixture_command(scenario,
                                    python=MACHINE_BINDING['python']['path'])
    supervisor = ParentSupervisor(command=command, run_id=run_id,
                                  candidate_sha=CANDIDATE_SHA,
                                  authorization_sha256=AUTHORIZATION_SHA,
                                  plan=plan(), root=root,
                                  phase_timeout=phase_seconds,
                                  child_timeout=phase_seconds * 2,
                                  grace_seconds=grace_seconds)
    supervisor.spawner = executor.spawn
    try:
        return supervisor.run()
    finally:
        os.environ.pop('LVW_S3_FIXTURE_CONTEXT', None)
```

### tools/test_v0_s3_supervisor.py:956 test_the_fixture_clean_terminal_is_verified_by_the_parent

```python
def test_the_fixture_clean_terminal_is_verified_by_the_parent(tmp_path):
    """I07/I24: the real fixture process ends with a verified terminal."""
    root = tmp_path / 'run'
    (root / 'temp/s3-quality').mkdir(parents=True)
    payload = json.dumps({'rows': [{'asset_id': 'SYN-01', 'execution_status': 'PASS'}]}).encode()
    (root / 'temp/s3-quality/qd-receipt.json').write_bytes(payload)
    evidence = run_fixture(tmp_path, 'clean_terminal', root=root)
    assert evidence['terminal_received'] is True
    assert evidence['canonical_receipt_verified'] is True
    assert evidence['row_status']['SYN-01'] == 'PASS'
    assert evidence['cleanup']['proven_stopped'] is True
```

### tools/test_v0_s3_supervisor.py:970 test_a_blocking_callback_is_actually_stopped

```python
def test_a_blocking_callback_is_actually_stopped(tmp_path):
    """I08: a blocked callback is stopped by the parent, not by a timeout text."""
    evidence = run_fixture(tmp_path, 'blocking_callback')
    assert evidence['protocol_violation'] == 'PHASE_DEADLINE_EXCEEDED'
    assert evidence['cleanup']['proven_stopped'] is True
    assert evidence['cleanup']['exit_code'] is not None
    assert evidence['root_retained'] is True
    assert evidence['resend_allowed'] is False
```

### tools/test_v0_s3_supervisor.py:981 test_a_blocking_persistence_is_actually_stopped

```python
def test_a_blocking_persistence_is_actually_stopped(tmp_path):
    """I09: a blocked persistence is stopped by the parent."""
    evidence = run_fixture(tmp_path, 'blocking_persistence')
    assert evidence['cleanup']['proven_stopped'] is True
    assert evidence['root_retained'] is True
```

### tools/test_v0_s3_supervisor.py:1000 test_a_protocol_violation_is_refused

```python
def test_a_protocol_violation_is_refused(tmp_path, scenario, code):
    """I12/I13: every protocol violation is a stable refusal."""
    # The message count negative case carries its own short synthetic run
    # identity, so that its wire fits into the frozen byte budget of a
    # stream.  The identity is bound by the parent and by the child.
    run_id = FLOOD_RUN_ID if scenario == 'message_flood' else RUN_ID
    evidence = run_fixture(tmp_path, scenario, run_id=run_id)
    assert evidence['protocol_violation'] == code
    assert evidence['cleanup']['proven_stopped'] is True
    assert evidence['root_retained'] is True
```

### tools/test_v0_s3_supervisor.py:1013 test_a_bad_terminal_reference_is_refused

```python
def test_a_bad_terminal_reference_is_refused(tmp_path):
    """I24: a terminal reference outside the bound root is refused."""
    evidence = run_fixture(tmp_path, 'bad_terminal_reference')
    assert evidence['canonical_receipt_verified'] is False
    assert evidence['root_retained'] is True
```

### tools/fixtures/v0_s3_supervisor_fixture.py:265 scenario_blocking_persistence

```python
def scenario_blocking_persistence(writer, values, rows):
    writer.write(writer.message('STARTED', {'root': values['root'] or '',
                                             'plan_rows': len(rows),
                                             'driver': 'fixture'}))
    # A partial line: the message is never terminated, so the protocol is
    # unresolved and the parent has to stop the held process.  The raw byte
    # semantics of ``write_raw`` are kept exactly: the frame stays
    # incomplete on purpose.
    writer.write_raw(b'{"schema":"' + product()['schema'].encode('utf-8') + b'","run_id":"')
    return BLOCK_FOREVER
```

### tools/fixtures/v0_s3_supervisor_fixture.py:332 scenario_nonfinite_number

```python
def scenario_nonfinite_number(writer, values, rows):
    """The nonfinite number negative case.

    The frame is *complete*: it carries the whole protocol message and it is
    terminated by the newline of the JSONL protocol.  The parent really
    decodes it and the parser refuses the NaN.  The raw byte semantics of
    ``write_raw`` are not used here and are not changed anywhere else.
    """
    writer.write(writer.message('STARTED', {'root': values['root'] or '',
                                             'plan_rows': len(rows),
                                             'driver': 'fixture',
                                             'value': float('nan')}))
    return BLOCK_FOREVER
```

### tools/fixtures/v0_s3_supervisor_fixture.py:354 flood_messages

```python
def flood_messages(values, rows):
    """The exact messages of the message count negative case.

    The list holds exactly ``MAX_MESSAGES + 1`` complete messages: the
    ``STARTED`` message and the progress messages that follow it.  Every
    message is closed, carries the identity of the context document and has
    an empty payload, so the frozen byte budget of the stream cannot hide
    the message count.
    """
    schema = product()['schema']
    count = product()['max_messages'] + 1
    messages = []
    for sequence in range(1, count + 1):
        if sequence == 1:
            event = 'STARTED'
            payload = {'root': values.get('root') or '', 'plan_rows': len(rows),
                       'driver': 'fixture'}
        else:
            event = 'PROGRESS'
            payload = {}
        messages.append({'schema': schema, 'run_id': values['run_id'],
                         'candidate_sha': values['candidate_sha'],
                         'authorization_sha256': values['authorization_sha256'],
                         'sequence': sequence, 'event': event,
                         'payload': payload})
    return messages
```

### tools/fixtures/v0_s3_supervisor_fixture.py:382 flood_wire

```python
def flood_wire(values, rows):
    """The exact wire bytes of the message count negative case.

    The wire is computed before a single byte is written: the number of
    frames, the length of every frame and the total number of bytes are
    real values, not estimates.
    """
    frames = [Writer.encode(message) + b'\n'
              for message in flood_messages(values, rows)]
    return frames
```

### tools/fixtures/v0_s3_supervisor_fixture.py:394 scenario_message_flood

```python
def scenario_message_flood(writer, values, rows):
    """The message count negative case: exactly one message too many.

    The wire is bounded *before* it is written.  If the frames of this
    negative case did not fit into the frozen byte caps, the byte budget
    would hide the message count and the scenario would refuse itself
    instead of proving the wrong reason.
    """
    limits = product()
    frames = flood_wire(values, rows)
    total = sum(len(frame) for frame in frames)
    longest = max(len(frame) for frame in frames)
    if (len(frames) != limits['max_messages'] + 1
            or longest > limits['max_message_bytes']
            or total > limits['max_stream_bytes']):
        raise SystemExit('FIXTURE_WIRE_BUDGET_EXCEEDED')
    for frame in frames:
        writer.write_raw(frame)
    return BLOCK_FOREVER
```

### tools/v0_s3_supervisor.py:113 decode_message

```python
def decode_message(raw):
    """Decode one protocol line with the strict rules of the contract."""
    if not isinstance(raw, (bytes, bytearray)):
        raise SupervisionError('MESSAGE_NOT_BYTES')
    if len(raw) > MAX_MESSAGE_BYTES:
        raise SupervisionError('MESSAGE_TOO_LARGE')
    if not raw.strip():
        raise SupervisionError('MESSAGE_EMPTY')
    try:
        text = bytes(raw).decode('utf-8')
    except UnicodeDecodeError as error:
        raise SupervisionError('MESSAGE_NOT_UTF8') from error
    try:
        value = json.loads(text, object_pairs_hook=_strict_pairs,
                           parse_constant=_reject_constant)
    except SupervisionError:
        raise
    except (ValueError, TypeError) as error:
        raise SupervisionError('MESSAGE_NOT_JSON') from error
    if not isinstance(value, dict):
        raise SupervisionError('MESSAGE_NOT_OBJECT')
    if set(value) != MESSAGE_KEYS:
        raise SupervisionError('MESSAGE_KEY_SET_INVALID')
    if value['schema'] != PROTOCOL_SCHEMA:
        raise SupervisionError('MESSAGE_SCHEMA_INVALID')
    if value['event'] not in EVENTS:
        raise SupervisionError('MESSAGE_EVENT_INVALID')
    if type(value['sequence']) is not int or value['sequence'] < 1:
        raise SupervisionError('MESSAGE_SEQUENCE_INVALID')
    if not isinstance(value['payload'], dict):
        raise SupervisionError('MESSAGE_PAYLOAD_INVALID')
    return value
```

### tools/v0_s3_supervisor.py:362 run

```python
    def run(self):
        try:
            while True:
                # The stream is asked for its descriptor on every read, so a
                # stream that stops being readable is noticed at once and not
                # only at the start of the run.
                descriptor = self.stream.fileno()
                block = os.read(descriptor, 65536)
                if not block:
                    break
                before = self.total
                if before + len(block) > self.limit:
                    # The bytes that are still inside the budget are kept,
                    # the rest of the block is dropped: the retained bytes
                    # never exceed the frozen budget of the stream.  The
                    # dropped bytes are observed but never kept, so the
                    # digest of this reader covers the prefix only.
                    allowed = self.limit - before
                    kept = block[:allowed] if allowed > 0 else b''
                    self._retain(kept, before + len(block), overflow=True)
                    break
                self._retain(block, before + len(block))
            self._publish_end()
        except Exception as error:  # noqa: BLE001 - the failure stays visible
            self._publish_error(type(error).__name__)
        finally:
            self.finished.set()
```

### tools/v0_s3_supervisor.py:628 _consume_stdout

```python
    def _consume_stdout(self):
        if self.stdout_reader is None:
            return
        block = self.stdout_reader.take()
        if not block:
            return
        self.stdout_buffer.extend(block)
        while True:
            index = self.stdout_buffer.find(b'\n')
            if index < 0:
                break
            line = bytes(self.stdout_buffer[:index])
            del self.stdout_buffer[:index + 1]
            if len(line) > MAX_MESSAGE_BYTES:
                raise SupervisionError('MESSAGE_TOO_LARGE')
            message = decode_message(line)
            self.state.accept(message)
            self.messages.append(message)
            if message['event'] == 'HISTORY_WAIT_STARTED':
                self._fix_history_deadline(message['payload']['asset_id'])
            if message['event'] == 'ROW_FINISHED':
                self._close_history_deadline(message['payload']['asset_id'])
            if message['event'] == 'TERMINAL':
                self.terminal_receipt = message['payload']['canonical_receipt']
```

### tools/v0_s3_supervisor.py:698 run

```python
    def run(self):
        """Drive the worker to a terminal state or to a refusal."""
        if self.process is None:
            self.start()
        while True:
            # The protocol is consumed first: a frame that was already
            # received is never lost.  A stream failure is checked right
            # after the consumption, so a resource failure revokes the later
            # actions even when a terminal event of the same batch was read.
            try:
                self._consume_stdout()
            except SupervisionError as error:
                self.violation = error.code
                break
            failure = self._stream_failure()
            if failure is not None:
                self.violation = failure
                break
            if self.state.terminal is not None:
                break
            expired = self._deadline_state()
            if expired is not None:
                self.deadline_exceeded = True
                self.violation = expired
                break
            status = self.process.poll()
            if status is not None:
                # The worker left.  Wait for the bounded readers to reach the
                # end of their stream and drain them, so a terminal event
                # that is already in the pipe is not lost.  The wait uses the
                # one shared drain deadline, so it can not outlive the
                # deadlines of this run.
                self._await_readers(self._drain_deadline())
                try:
                    self._consume_stdout()
                except SupervisionError as error:
                    self.violation = error.code
                    break
                failure = self._stream_failure()
                if failure is not None:
                    self.violation = failure
                    break
                if self.state.terminal is None:
                    self.violation = 'WORKER_EXITED_WITHOUT_TERMINAL'
                    break
                break
            time.sleep(self.poll_interval)
        self.cleanup = self._terminate_owned_worker()
        self.exit_code = self.process.poll()
        self._drain_streams()
        self._verify_terminal_receipt()
        self._derive_row_status()
        return self.evidence()
```

### tools/v0_s3_supervisor.py:912 _terminate_owned_worker

```python
    def _terminate_owned_worker(self):
        """Terminate only the worker handle that this parent started.

        No other process is touched.  A PID that the worker reported is
        never used, and no process is selected by a name that was read from
        a file.
        """
        outcome = {'requested': False, 'cooperative_cancel': False,
                   'terminated': False, 'killed': False, 'proven_stopped': False,
                   'exit_code': None, 'pid': getattr(self.process, 'pid', None),
                   'birth': self.birth, 'native_cleanup_proven': False,
                   'native_cleanup_owner': 'original_driver'}
        if self.process is None:
            return outcome
        if self.violation is not None:
            outcome['cooperative_cancel'] = self._request_cooperative_cancel()
        if self.process.poll() is None:
            outcome['requested'] = True
            try:
                self.process.terminate()
                outcome['terminated'] = True
            except Exception:  # noqa: BLE001 - the failure stays visible
                outcome['terminate_failed'] = True
            try:
                self.process.wait(timeout=self.grace_seconds)
            except Exception:  # noqa: BLE001 - a timeout or an error
                try:
                    self.process.kill()
                    outcome['killed'] = True
                except Exception:  # noqa: BLE001 - the failure stays visible
                    outcome['kill_failed'] = True
                try:
                    self.process.wait(timeout=self.grace_seconds)
                except Exception:  # noqa: BLE001 - the failure stays visible
                    outcome['kill_failed'] = True
        outcome['exit_code'] = self.process.poll()
        outcome['proven_stopped'] = outcome['exit_code'] is not None
        return outcome
```

### tools/v0_s3_quality_worker.py:254 run_worker

```python
def run_worker(context, *, driver=None, emit=None, authorize=None, clock=None, sleep=None):
    """Really invoke the accepted quality phase under the parent protocol.

    ``emit`` is the protocol sink of the worker: it receives the event name
    and the bounded payload.  ``driver`` is the runtime seam; the production
    entry builds the native driver from the bound context, the offline tests
    inject an explicit fake runtime seam.  In both cases the phase that runs
    is the accepted ``QualityPhase`` itself.
    """
    if emit is None:
        raise WorkerError('WORKER_EMIT_REQUIRED')
    if driver is None:
        raise WorkerError('WORKER_DRIVER_REQUIRED')
    projection = context.projection()
    source_identity = context.source_identity()
    parent_budget = context.parent_budget()
    manifest = context.dependency_manifest()
    directory = manifest['path']
    if directory not in sys.path:
        # The existing dependency directory is appended, never prepended: an
        # existing dependency must not shadow the standard library.
        sys.path.append(directory)
    if authorize is None:
        def authorize(action, subject):
            return None
    emit('STARTED', {'root': str(context.root),
                     'plan_rows': 16,
                     'driver': context.document['driver']})
    sink = lambda event, payload: emit(event, payload)  # noqa: E731 - a thin bridge
    phase = QualityPhase(driver, context.root, run_id=context.run_id,
                          candidate_sha=context.candidate_sha,
                          authorization_sha256=context.authorization_sha256,
                          projection=projection,
                          projection_sha256=context.document['projection_sha256'],
                          source_identity=source_identity, authorize=authorize,
                          binding=context.binding(), parent_budget=parent_budget,
                          clock=clock, sleep=sleep, progress_sink=sink)
    receipt = phase.run()
    reference = context.canonical_receipt_reference
    path = context.root / reference
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise WorkerError('WORKER_CANONICAL_RECEIPT_UNREADABLE') from error
    emit('TERMINAL', {'canonical_receipt': {'reference': reference,
                                            'bytes': len(raw),
                                            'sha256': sha256_bytes(raw)},
                      'decision': receipt.get('decision'),
                      'dependency_scope': manifest['scope'],
                      'dependency_transitive_seal_complete':
                          manifest.get('transitive_seal_complete') is True,
                      'stage_pass_claim': False,
                      'product_gate0': False})
    return receipt
```

### tools/v0_s3_quality_worker.py:310 main

```python
def main(argv=None):
    """The production entry of the worker."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    context_path = None
    index = 0
    while index < len(arguments):
        if arguments[index] == '--context' and index + 1 < len(arguments):
            context_path = arguments[index + 1]
            index += 2
            continue
        raise WorkerError('WORKER_ARGUMENT_INVALID')
    if context_path is None:
        raise WorkerError('WORKER_CONTEXT_ARGUMENT_REQUIRED')
    try:
        context = WorkerContext.load(context_path)
        run_worker(context, driver=build_native_driver(context),
                   emit=ProtocolWriter(sys.stdout.buffer, run_id=context.run_id,
                                       candidate_sha=context.candidate_sha,
                                       authorization_sha256=context.authorization_sha256
                                       ).emit)
    except WorkerError as error:
        sys.stderr.write('S3_WORKER_REFUSED ' + error.code + '\n')
        return 2
    except QualityContractError as error:
        sys.stderr.write('S3_WORKER_REFUSED QUALITY ' + str(error)[:120] + '\n')
        return 3
    return 0
```

### reports/v0-s3/product-gate0/implementation-integration-01/executor.py:830 spawn

```python
    def spawn(self, command):
        """Start one child and take the custody of its original handle.

        The custody is taken immediately.  A failure of the registration or
        of the watchdog setup never loses the handle: the child is still
        stopped by this executor and the cleanup still runs.

        A failure of the operating system action itself never leaves a
        charge without a terminal state.  The charge was taken before the
        action, so it is settled here: either as a refusal that the guard
        proved before the fork, or as an unknown custody that keeps its
        slot, its reservation and the owned root.
        """
        # The scope of this action.  The nonce of the action is what a
        # refusal credential of this action has to present.
        action = {'nonce': uuid.uuid4().hex}
        self._local.action = action
        self._local.admission = None
        try:
            process = subprocess.Popen(command, stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       bufsize=0, cwd=str(self.guard_root))
        except BaseException as error:  # noqa: BLE001 - the state stays visible
            self._settle_without_handle(error)
            raise
        token = getattr(self._local, 'admission', None)
        self._local.admission = None
        self._local.action = None
        entry = self._take_custody(process, token)
        try:
            self._ensure_watchdog()
        except BaseException:
            # The watchdog could not be armed.  The handle is still owned.
            self._stop_child(entry)
            raise
        return process
```

### reports/v0-s3/product-gate0/implementation-integration-01/executor.py:1007 reconcile_exited_children

```python
    def reconcile_exited_children(self):
        """Release the slot of a child whose original handle proves its exit.

        The final reaper of the executor is the *last* accounting of the
        children.  A sequential run admits its next start long before that
        final reap: a child that has already exited keeps its charge in the
        ``STARTED`` state and keeps its concurrency slot, so the third
        sequential start would be refused by the shared counter although the
        first two children are gone.

        This reconciliation runs before an admission and it never replaces
        the final reap:

        * it looks only at the children that **this** executor owns,
        * it releases a slot only when the **original handle** proves that
          the child exited and when the shared counter **persists** the
          terminal state of that charge, with the exact identity of that
          charge (see ``persisted_terminal_matches``),
        * a live child, an unproven child, a conflicting persisted record
          and a settlement that the counter did not accept keep their slot,
        * the cumulative starts, the charges and the evidence of the
          original run are never removed, never refunded and never reset,
        * it never revokes the admissions, never stops the watchdog and
          never takes a new custody.

        The result is explicit: the entries that were released and the
        entries whose settlement could not be proven.  A failure is never
        hidden and it never releases anything.

        The reconciliation is bounded: it inspects the owned children of
        this executor once and it never waits for anything.
        """
        released = []
        failures = []
        with self._lock:
            children = list(self.children)
        for entry in children:
            index = entry.get('index')
            if index is None:
                continue
            if entry.get('state') != 'STARTED':
                # Only a child that this executor still holds open is a
                # candidate.  A settled child and an unknown child keep
                # their slot.
                continue
            if entry.get('settlement_persisted') is True:
                continue
            process = entry.get('process')
            if process is None:
                continue
            try:
                exit_code = process.poll()
            except Exception:  # noqa: BLE001 - the failure stays visible
                # The exit of this child cannot be observed: the slot is
                # kept and nothing is claimed about the child.
                exit_code = None
            if exit_code is None:
                # The child is still alive: it keeps its slot.
                continue
            state = 'TIMED_OUT' if entry.get('timed_out') else 'STOPPED'
            spent = round(self.clock() - entry['started'], 3)
            persisted = False
            settlement_error = None
            reason = None
            # The persisted proof comes first: the local marker of a former
            # reconciliation is never a proof by itself, and a record that
            # conflicts with this charge is never an idempotent success.
            proof, reason = self._persisted_terminal_proof(index, entry, exit_code, state)
            if proof:
                # The counter already persists exactly this terminal state.
                # The settlement is idempotent: the finished_wall of the
                # charge is never written a second time.
                persisted = True
            elif reason in ('NO_PERSISTED_RECORD', 'NOT_SETTLED'):
                # The charge is not settled yet: the settlement is attempted.
                try:
                    persisted = self.counter.finish(index, state=state, exit_code=exit_code,
                                                    spent=spent, pid=entry.get('pid'),
                                                    birth=entry.get('birth')) is True
                except CpuGateError as failure:
                    settlement_error = failure.code
                except OSError:
                    # An ordinary I/O failure of the counter is a failure of
                    # the settlement, never an absent proof.
                    settlement_error = 'CPU_COUNTER_IO_ERROR'
                if not persisted and settlement_error is None:
                    # The counter may have accepted the settlement of this
                    # very charge: only the strict proof decides.
                    proof, reason = self._persisted_terminal_proof(
                        index, entry, exit_code, state)
                    persisted = proof
                    if not proof:
                        settlement_error = reason
            else:
                # A conflict: the persisted state is not the terminal state
                # of this charge.  Nothing is released and the conflict is
                # reported.
                settlement_error = reason
            if not persisted:
                # Nothing is released: the charge keeps its slot, the
                # settlement of this session is uncertain and the finalizer
                # keeps the owned root.
                self.uncertain = True
                with self._lock:
                    record = self._charges.get(index)
                    if record is not None:
                        record['settlement_persisted'] = False
                        record['settlement_error'] = settlement_error
                        record['outcome'] = 'UNKNOWN'
                failures.append({'index': index, 'state': state,
                                 'exit_code': exit_code,
                                 'settlement_error': settlement_error,
                                 'reason': reason})
                continue
            entry['exit_code'] = exit_code
            entry['state'] = state
            entry['proven'] = True
            entry['settlement_persisted'] = True
            with self._lock:
                record = self._charges.get(index)
                if record is not None:
                    record['handle_proven'] = True
                    record['settlement_persisted'] = True
                    record['settlement_error'] = None
            released.append({'index': index, 'state': state, 'exit_code': exit_code,
                             'spent_wall_seconds': spent})
        return {'released': released, 'failures': failures}
```
