"""Synthetic streams and handles only; no native query or socket starts."""
import hashlib
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.v0_s2_native_sampler import parse_gpu,sample_stream,execute


class Stream:
    def __init__(self,lines):self.lines=iter(lines);self.ended=threading.Event();self.closed=False
    def readline(self,limit):
        try:return next(self.lines)
        except StopIteration:self.ended.wait(3);return b''
    def close(self):self.closed=True;self.ended.set()


class Process:
    def __init__(self,lines):self.stdout=Stream(lines);self.returncode=None;self.terminations=0
    def poll(self):return self.returncode
    def terminate(self):self.terminations+=1;self.returncode=0;self.stdout.ended.set()
    def kill(self):self.terminate()
    def wait(self,timeout):return self.returncode


class Memory:
    def __init__(self,ram=4096,callback=lambda:None):self.ram=ram;self.closed=False;self.callback=callback;self.calls=0;self.start_ticks={'42':100}
    def snapshot(self):self.calls+=1;self.callback();return self.ram,{'42':1000}
    def close(self):self.closed=True


class SamplerTests(unittest.TestCase):
    def run_stream(self,lines,*,ram=4096,timestamps=(0,1),emit_error=False):
        process=Process(lines);memory=Memory(ram);points=[];times=iter(timestamps)
        main=threading.current_thread()
        def clock():return 0 if threading.current_thread() is main else next(times)
        def emit(value):
            if emit_error:raise OSError('fixture disk failure')
            points.append(value)
        try:
            value=sample_stream(process,stopped=lambda:len(points)>=2,memory=memory,emit=emit,max_seconds=60,clock=clock)
            return value,points
        finally:
            self.assertEqual(0,process.poll());self.assertEqual(1,process.terminations)
            self.assertTrue(process.stdout.closed);self.assertTrue(memory.closed)

    def test_valid_trace_exact_limits_and_owned_terminal_cleanup(self):
        value,points=self.run_stream([b'0,23551\n',b'0,23551\n'],ram=2048)
        self.assertEqual(2,value['samples']);self.assertTrue(value['stopped_by_owner'])
        self.assertEqual([0,1],[p['sample_index'] for p in points])
        self.assertEqual({'42':1000},points[0]['private_bytes'])

    def test_over_threshold_gap_parse_and_sink_failures_never_succeed(self):
        for lines,options in [([b'0,23552\n'],{}),([b'0,1\n'],{'ram':2047}),
                              ([b'0,1\n',b'0,1\n'],{'timestamps':(0,1.501)}),
                              ([b'0,1\n',b'0,1\n'],{'timestamps':(0,0)}),
                              ([b'1,1\n'],{}),([b'0,N/A\n'],{}),([b'0,1\n'],{'emit_error':True})]:
            with self.subTest(lines=lines,options=options),self.assertRaises((ValueError,OSError)):
                self.run_stream(lines,**options)

    def test_reader_start_failure_still_stops_child_and_closes_memory(self):
        process=Process([]);memory=Memory()
        with patch('threading.Thread.start',side_effect=RuntimeError('fixture')),self.assertRaises(RuntimeError):
            sample_stream(process,stopped=lambda:False,memory=memory,emit=lambda x:None,max_seconds=1)
        self.assertEqual(1,process.terminations);self.assertTrue(memory.closed);self.assertTrue(process.stdout.closed)

    def test_invalid_binary_pin_refuses_before_process_or_memory_reads(self):
        with tempfile.TemporaryDirectory() as temp:
            binary=Path(temp)/'nvidia-smi.exe';binary.write_bytes(b'synthetic executable, never run')
            args=SimpleNamespace(run_root=temp,nvidia_smi=str(binary),binary_sha256='a'*64,max_seconds=60,private_pids=[42])
            with patch('subprocess.Popen') as spawn,patch('tools.v0_s2_native_sampler.WindowsMemory') as memory,self.assertRaises(ValueError):
                execute(args)
            spawn.assert_not_called();memory.assert_not_called()
            self.assertEqual([binary],list(Path(temp).iterdir()))

    def test_executor_persists_process_set_and_rejects_old_evidence_slot(self):
        with tempfile.TemporaryDirectory() as temp:
            binary=Path(temp)/'nvidia-smi.exe';binary.write_bytes(b'synthetic executable, never run')
            args=SimpleNamespace(run_root=temp,nvidia_smi=str(binary),binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),max_seconds=60,private_pids=[42])
            process=Process([b'0,1\n',b'0,2\n']);memory=Memory()
            def mark():
                if memory.calls==2:(Path(temp)/'resource-sampler.stop').touch()
            memory.callback=mark
            with patch('subprocess.Popen',return_value=process) as spawn,patch('tools.v0_s2_native_sampler.WindowsMemory',return_value=memory):
                value=execute(args)
            self.assertEqual('RESOURCE_TRACE_COLLECTED_NOT_STAGE_ACCEPTANCE',value['decision'])
            self.assertEqual([42],value['private_process_set']);self.assertTrue(value['owned_gpu_query_exited'])
            self.assertEqual(2,len((Path(temp)/'resource-trace.jsonl').read_text().splitlines()))
            self.assertEqual(str(binary),spawn.call_args.args[0][0])
            with patch('subprocess.Popen') as spawn,self.assertRaises(ValueError):execute(args)
            spawn.assert_not_called()


if __name__=='__main__':unittest.main()
