"""Offline amendment negatives and actual own-file closure checks; no native I/O."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools import v0_s2_stage_checkpoint as cp
from tools import v0_s2_supplemental as sup
from tools.v0_s2_stage_archive import OwnedArchive
from tools.v0_s2_checkpoint_oracles import EvidenceError


class SupplementalTests(unittest.TestCase):
    def test_request_without_explicit_active_approval_never_runs_a_command(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);p=root/sup.REQUEST;p.parent.mkdir(parents=True)
            p.write_bytes((cp.ROOT/sup.REQUEST).read_bytes())
            with patch.object(cp,'ROOT',root),patch('subprocess.run') as run,self.assertRaises(FileNotFoundError):
                sup.authority('a'*40,require_cleanup=False)
            run.assert_not_called()

    def test_changed_request_or_revocation_is_denied_before_git_or_target_access(self):
        request=(cp.ROOT/sup.REQUEST).read_bytes();approval=(cp.ROOT/sup.APPROVAL).read_bytes()
        for mutate in ('request','approval'):
            with self.subTest(mutate=mutate),tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary);p=root/sup.REQUEST;p.parent.mkdir(parents=True);p.write_bytes(request)
                a=root/sup.APPROVAL;a.write_bytes(approval)
                if mutate=='request':p.write_bytes(request+b' ')
                else:
                    value=json.loads(approval);value['status']='REVOKED';a.write_text(json.dumps(value))
                with patch.object(cp,'ROOT',root),patch('subprocess.run') as run,self.assertRaises(EvidenceError):
                    sup.authority('a'*40,require_cleanup=False)
                run.assert_not_called()

    def test_supplemental_prepare_cannot_skip_its_authority_or_cleanup_gate(self):
        with tempfile.TemporaryDirectory() as temporary,patch.object(cp,'ROOT',Path(temporary)), \
                patch.object(cp,'STATE_ROOT',Path(temporary)/'state'), \
                patch.object(sup,'authority',side_effect=EvidenceError('cleanup not proven')) as authority, \
                patch.object(cp,'resolve_installed') as native:
            with self.assertRaises(EvidenceError):cp.prepare(sup.SLOT,'a'*40,'reports/v0-s2/offline-checkpoint-21/receipt.json')
            self.assertFalse(cp.child_path(sup.SLOT).exists());native.assert_not_called()
            authority.assert_called_once_with('a'*40,require_cleanup=True)

    def test_no_fourth_slot_is_available(self):
        for name in ('full-supplemental-02','full-recheck-02'):
            with self.assertRaises(EvidenceError):cp.child_path(name)

    def fixture(self,parent):
        root=parent/'owned';root.mkdir();(root/'input').mkdir();(root/'outside-input').mkdir()
        (root/'input/redirect').symlink_to(root/'outside-input',target_is_directory=True)
        (root/'outside-input/source.mp4').write_bytes(b'safe');(root/'input/empty.mp4').touch()
        dest=parent/'archive';dest.mkdir()
        archive=OwnedArchive(dest,run_id='fixture-only',candidate_sha='a'*40,authorization_sha256='b'*64,authorize=lambda *a:None)
        expected={'outside-input/source.mp4':{'sha256':hashlib.sha256(b'safe').hexdigest(),'bytes':4},
            'input/empty.mp4':{'sha256':hashlib.sha256(b'').hexdigest(),'bytes':0}}
        return root,archive,expected

    def test_own_file_closure_matches_without_following_link_or_deleting_anything(self):
        with tempfile.TemporaryDirectory() as temporary:
            root,archive,expected=self.fixture(Path(temporary))
            rows=sup.check_retained_tree(archive,root,expected)
            self.assertEqual(3,len(rows));self.assertTrue((root/'input/redirect').is_symlink())
            self.assertEqual(b'safe',(root/'outside-input/source.mp4').read_bytes())

    def test_unknown_files_directories_changed_bytes_or_redirect_targets_are_preserved(self):
        for change in ('file','directory','bytes','target'):
            with self.subTest(change=change),tempfile.TemporaryDirectory() as temporary:
                parent=Path(temporary);root,archive,expected=self.fixture(parent)
                if change=='file':(root/'unknown').write_text('must keep')
                elif change=='directory':(root/'unknown').mkdir()
                elif change=='bytes':(root/'outside-input/source.mp4').write_bytes(b'evil')
                else:
                    foreign=parent/'foreign';foreign.mkdir();(foreign/'keep').write_text('keep')
                    (root/'input/redirect').unlink();(root/'input/redirect').symlink_to(foreign,target_is_directory=True)
                with self.assertRaises(EvidenceError):sup.check_retained_tree(archive,root,expected)
                self.assertTrue(root.exists())
                if change=='target':self.assertEqual('keep',(foreign/'keep').read_text())

    def test_real_git_descendant_cannot_change_product_or_frozen_thresholds(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);stage_name='.agent-governance/stages/V0-S2/stage-control.json'
            stage=cp.repository_json(stage_name);stage.pop('supplemental_authorization',None)
            for name,value in [(stage_name,stage),(cp.PROGRAM,cp.repository_json(cp.PROGRAM)),
                    ('plans/execution-control.json',{'coordinate':{'stage_id':'V0-S2'}})]:
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value))
            def git(*args):return subprocess.check_output(['git',*args],cwd=root,stderr=subprocess.DEVNULL).decode().strip()
            git('init','-q');git('add','.');git('-c','user.name=fixture','-c','user.email=fixture@example.invalid','commit','-qm','baseline')
            baseline=git('rev-parse','HEAD')
            request={'corrected_candidate':baseline,'runtime_budget':cp.BUDGET,'acceptance_hash':cp.ACCEPTANCE,'prior_failed_runs':[],'forbidden':cp.FORBIDDEN+['human experience signoff', 'final V1 release signoff', 'V2/V3 execution'],
                'offline_receipt':cp.PROGRAM,'offline_receipt_sha256':hashlib.sha256((root/cp.PROGRAM).read_bytes()).hexdigest(),
                'seed_artifact_sha256':{}}
            raw=cp.canonical(request);request_sha=hashlib.sha256(raw).hexdigest()
            p=root/sup.REQUEST;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
            approval=cp.repository_json(sup.APPROVAL);approval['status']='ACTIVE';approval['request_sha256']=request_sha
            (root/sup.APPROVAL).write_text(json.dumps(approval))
            stage['supplemental_authorization']={'approval':sup.APPROVAL,'request':sup.REQUEST,'slot':sup.SLOT,'max_runs':1,'max_rechecks':0}
            (root/stage_name).write_text(json.dumps(stage));git('add','.');git('-c','user.name=fixture','-c','user.email=fixture@example.invalid','commit','-qm','synthetic amendment')
            candidate=git('rev-parse','HEAD')
            with patch.object(cp,'ROOT',root),patch.object(sup,'REQUEST_SHA',request_sha):
                self.assertEqual(request_sha,sup.authority(candidate,require_cleanup=False)['request_sha256'])
                stage['budgets']['corrected_candidate_full_rechecks']=2
                (root/stage_name).write_text(json.dumps(stage));git('add','.');git('-c','user.name=fixture','-c','user.email=fixture@example.invalid','commit','-qm','invalid threshold')
                with self.assertRaises(EvidenceError):sup.authority(git('rev-parse','HEAD'),require_cleanup=False)



class CleanupControllerTests(unittest.TestCase):
    """Actual own-tree archival/deletion with an explicitly synthetic native boundary."""
    def test_claim_expiry_unknown_entries_and_public_disk_failure_are_fail_closed(self):
        import time
        from contextlib import ExitStack
        from tools import v0_s2_execution_bindings as bindings
        for mode in ('success','unknown','disk-full'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as temporary,ExitStack() as stack:
                parent=Path(temporary).resolve();pack=parent/'pack';pack.mkdir();state=parent/'state';state.mkdir()
                root=state/'full-recheck-01/lvw-s2-default-ccmmyy5d';root.mkdir(parents=True)
                (root/'input').mkdir();(root/'outside-input').mkdir()
                (root/'outside-input/source.mp4').write_bytes(b'safe');(root/'input/empty.mp4').touch()
                (root/'input/redirect').symlink_to(root/'outside-input',target_is_directory=True)
                expected={'outside-input/source.mp4':{'sha256':hashlib.sha256(b'safe').hexdigest(),'bytes':4},
                    'input/empty.mp4':{'sha256':hashlib.sha256(b'').hexdigest(),'bytes':0}}
                if mode=='unknown':(root/'unknown').write_text('preserve')
                info=root.stat();scope={'wsl_path':str(root),'windows_path':'C:/fixture/owned',
                    'observed_device':str(info.st_dev),'observed_inode':str(info.st_ino)}
                request=cp.canonical({'retained_root_cleanup':scope});request_sha=hashlib.sha256(request).hexdigest()
                for name,raw in [(sup.REQUEST,request),(sup.APPROVAL,b'{}'),(sup.HARNESS,b'non-executable test identity')]:
                    p=pack/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
                refs={'approval':sup.APPROVAL,'approval_sha256':hashlib.sha256(b'{}').hexdigest(),
                    'request':sup.REQUEST,'request_sha256':request_sha}
                ps=parent/'synthetic-tool';ps.write_bytes(b'not an installed executable')
                snapshot={'files':[{'alias':'POWERSHELL','sha256':hashlib.sha256(ps.read_bytes()).hexdigest()}]}
                manifest=hashlib.sha256(json.dumps(snapshot['files'],ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
                original={'candidate_sha':'a'*40,'sequence':{'error_code':'StopProbe:REPARSE_NATIVE_IDENTITY_MISMATCH'},
                    'runtime_evidence':{'default':{'binding_proof':{'manifest_sha256':manifest}}}}
                raw=cp.canonical(original);(root.parent/'terminal.json').write_bytes(raw)
                (root.parent/'installed-bindings.json').write_text(json.dumps(snapshot))
                cleanup={'proven':True,'owned_count':0,'final_target_listener_count':0,'http_workers_pending':{},
                    'owned_listener_terminal_states':[],'owned_wrapper_terminal_states':[]}
                (root.parent/'default-preparation-failure.json').write_text(json.dumps({'cleanup':cleanup}))
                report=pack/'reports/v0-s2/full-recheck-01/receipt.json';report.parent.mkdir(parents=True,exist_ok=True)
                report.write_text(json.dumps({'raw_terminal_sha256':hashlib.sha256(raw).hexdigest()}))
                stack.enter_context(patch.object(cp,'ROOT',pack));stack.enter_context(patch.object(cp,'STATE_ROOT',state))
                stack.enter_context(patch.object(sup,'REQUEST_SHA',request_sha))
                stack.enter_context(patch.object(sup,'authority',return_value=refs))
                stack.enter_context(patch.object(cp,'program_authority',return_value='0'*64))
                stack.enter_context(patch.object(cp,'source_gate',return_value={'payload_sha256':'1'*64}))
                stack.enter_context(patch.object(sup,'retained_expected',return_value=expected))
                stack.enter_context(patch.object(cp,'windows_path',return_value=root))
                real_plain=bindings.plain
                stack.enter_context(patch.object(bindings,'plain',side_effect=lambda value:ps if str(value)=='/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe' else real_plain(value)))
                def native(argv,**kwargs):
                    script=argv[-1]
                    if '$item=Get-Item' in script:
                        value={'path':'C:/fixture/owned/input/redirect','attributes':0x400,'link_type':'Junction',
                            'targets':['C:/fixture/owned/outside-input']}
                    else:
                        self.assertIn('[System.IO.Directory]::Delete(',script)
                        (root/'input/redirect').unlink();value={'link_absent':True,'target_exists':True}
                    return subprocess.CompletedProcess(argv,0,json.dumps(value).encode(),b'')
                run=stack.enter_context(patch.object(subprocess,'run',side_effect=native))
                offline=pack/'reports/v0-s2/offline-checkpoint-22/receipt.json';offline.parent.mkdir(parents=True);offline.write_bytes(b'{}')
                sup.prepare_cleanup('a'*40,'reports/v0-s2/offline-checkpoint-22/receipt.json')
                auth_path=pack/'reports/v0-s2/authorization-supplemental-cleanup-01.json'
                # prepare binds the offline receipt bytes; the fixture source
                # gate is synthetic, but expiry and file effects below are real.
                if mode=='disk-full':
                    writer=cp.write_new
                    def fail_public(path,value):
                        if path==pack/'reports/v0-s2/supplemental-cleanup-01/receipt.json':
                            raise OSError('synthetic disk full')
                        return writer(path,value)
                    stack.enter_context(patch.object(cp,'write_new',side_effect=fail_public))
                    with self.assertRaises(OSError):sup.cleanup()
                else:
                    result=sup.cleanup()
                    self.assertEqual('NO_GO' if mode=='unknown' else 'CLEANUP_PROVEN_NOT_PRODUCT_ACCEPTANCE',result['decision'])
                auth=json.loads(auth_path.read_text())
                self.assertEqual('EXPIRED_CLEANUP_PROVEN' if mode=='success' else 'EXPIRED_NO_GO',auth['status'])
                self.assertEqual(b'1',(state/sup.CLEANUP/'lease.closed').read_bytes())
                if mode=='unknown':
                    run.assert_not_called();self.assertEqual('preserve',(root/'unknown').read_text())
                else:
                    self.assertEqual(2,run.call_count);self.assertFalse(root.exists())
                    self.assertTrue((state/sup.CLEANUP/'default-raw/ARCHIVE_MANIFEST.json').exists())
                with self.assertRaises(EvidenceError):sup.cleanup()


if __name__=='__main__':unittest.main()
