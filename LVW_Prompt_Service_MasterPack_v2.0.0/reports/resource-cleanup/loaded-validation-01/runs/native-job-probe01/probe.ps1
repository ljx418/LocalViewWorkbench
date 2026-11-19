$ErrorActionPreference='Stop';$env:TEMP='\\wsl.localhost\Ubuntu-24.04\tmp\lvw-win-job-probe-25dkp0vn';$env:TMP='\\wsl.localhost\Ubuntu-24.04\tmp\lvw-win-job-probe-25dkp0vn';Add-Type -TypeDefinition '
using System;
using System.Text;
using System.Threading;
using System.Runtime.InteropServices;
using System.ComponentModel;
public sealed class LvwOwnedJob : IDisposable {
  IntPtr job = IntPtr.Zero, process = IntPtr.Zero;
  public uint Pid { get; private set; }
  public long BirthTicks { get; private set; }
  [StructLayout(LayoutKind.Sequential)] struct Limits {
    public long ProcessTime, JobTime;
    public uint Flags;
    public UIntPtr MinWorkingSet, MaxWorkingSet;
    public uint ActiveProcessLimit;
    public UIntPtr Affinity;
    public uint PriorityClass, SchedulingClass;
  }
  [StructLayout(LayoutKind.Sequential)] struct IO {
    public ulong ReadOperations, WriteOperations, OtherOperations, ReadBytes, WriteBytes, OtherBytes;
  }
  [StructLayout(LayoutKind.Sequential)] struct Extended {
    public Limits Basic; public IO Io;
    public UIntPtr ProcessMemory, JobMemory, PeakProcessMemory, PeakJobMemory;
  }
  [StructLayout(LayoutKind.Sequential)] struct Accounting {
    public long User, Kernel, PeriodUser, PeriodKernel;
    public uint PageFaults, TotalProcesses, ActiveProcesses, TerminatedProcesses;
  }
  [StructLayout(LayoutKind.Sequential)] struct Security {
    public int Length; public IntPtr Descriptor; public int Inherit;
  }
  [StructLayout(LayoutKind.Sequential)] struct Startup {
    public uint Size; public IntPtr Reserved, Desktop, Title;
    public uint X, Y, XSize, YSize, XCount, YCount, Fill, Flags;
    public ushort Show, ReservedSize; public IntPtr ReservedData, Input, Output, Error;
  }
  [StructLayout(LayoutKind.Sequential)] struct ProcessInfo {
    public IntPtr Process, Thread; public uint Pid, Tid;
  }
  [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)] static extern IntPtr CreateJobObject(IntPtr a, string n);
  [DllImport("kernel32.dll", SetLastError=true)] static extern bool SetInformationJobObject(IntPtr j, int c, ref Extended v, int n);
  [DllImport("kernel32.dll", SetLastError=true)] static extern bool QueryInformationJobObject(IntPtr j, int c, out Accounting v, int n, IntPtr r);
  [DllImport("kernel32.dll", SetLastError=true)] static extern bool AssignProcessToJobObject(IntPtr j, IntPtr p);
  [DllImport("kernel32.dll", SetLastError=true)] static extern bool TerminateJobObject(IntPtr j, uint code);
  [DllImport("kernel32.dll", SetLastError=true)] static extern bool TerminateProcess(IntPtr p, uint code);
  [DllImport("kernel32.dll", SetLastError=true)] static extern uint WaitForSingleObject(IntPtr p, uint ms);
  [DllImport("kernel32.dll", SetLastError=true)] static extern uint ResumeThread(IntPtr t);
  [DllImport("kernel32.dll", SetLastError=true)] static extern bool CloseHandle(IntPtr h);
  [DllImport("kernel32.dll", SetLastError=true)] static extern bool GetProcessTimes(IntPtr p, out long b, out long e, out long k, out long u);
  [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)] static extern IntPtr CreateFile(string p, uint access, uint share, ref Security s, uint creation, uint flags, IntPtr template);
  [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)] static extern bool CreateProcess(string app, StringBuilder cmd, IntPtr pa, IntPtr ta, bool inherit, uint flags, IntPtr env, string cwd, ref Startup si, out ProcessInfo pi);
  static void Check(bool ok) { if (!ok) throw new Win32Exception(Marshal.GetLastWin32Error()); }
  static bool Valid(IntPtr h) { return h != IntPtr.Zero && h != new IntPtr(-1); }
  public bool HasExited { get { return process != IntPtr.Zero && WaitForSingleObject(process, 0) == 0; } }
  public bool Empty {
    get { if (job == IntPtr.Zero) return true;
      Accounting a; Check(QueryInformationJobObject(job, 1, out a, Marshal.SizeOf(typeof(Accounting)), IntPtr.Zero));
      return a.ActiveProcesses == 0;
    }
  }
  public void Start(string exe, string stdout, string stderr) {
    if (job != IntPtr.Zero || process != IntPtr.Zero) throw new InvalidOperationException("Already started");
    job = CreateJobObject(IntPtr.Zero, null); Check(Valid(job));
    Extended limits = new Extended(); limits.Basic.Flags = 0x2000; // KILL_ON_JOB_CLOSE; no BREAKAWAY flags.
    Check(SetInformationJobObject(job, 9, ref limits, Marshal.SizeOf(typeof(Extended))));
    Security sa = new Security(); sa.Length = Marshal.SizeOf(typeof(Security)); sa.Inherit = 1;
    IntPtr output = IntPtr.Zero, error = IntPtr.Zero, input = IntPtr.Zero;
    ProcessInfo pi = new ProcessInfo();
    try {
      output = CreateFile(stdout, 0x40000000, 3, ref sa, 1, 0x80, IntPtr.Zero); Check(Valid(output));
      error = CreateFile(stderr, 0x40000000, 3, ref sa, 1, 0x80, IntPtr.Zero); Check(Valid(error));
      input = CreateFile("NUL", 0x80000000, 3, ref sa, 3, 0x80, IntPtr.Zero); Check(Valid(input));
      Startup si = new Startup(); si.Size = (uint)Marshal.SizeOf(typeof(Startup));
      si.Flags = 0x100; si.Input = input; si.Output = output; si.Error = error;
      Check(CreateProcess(exe, new StringBuilder("\"" + exe + "\" serve"), IntPtr.Zero, IntPtr.Zero, true,
                          0x08000004, IntPtr.Zero, null, ref si, out pi)); // NO_WINDOW | SUSPENDED
      process = pi.Process; Pid = pi.Pid;
      // This is the first possible execution: attach before ResumeThread, so
      // every runner inherits the private job even if the wrapper later dies.
      Check(AssignProcessToJobObject(job, process));
      long born, exited, kernel, user; Check(GetProcessTimes(process, out born, out exited, out kernel, out user));
      BirthTicks = DateTime.FromFileTimeUtc(born).Ticks;
      Check(ResumeThread(pi.Thread) != 0xffffffff);
    } catch {
      if (process != IntPtr.Zero) { TerminateProcess(process, 1); WaitForSingleObject(process, 5000); }
      throw;
    } finally {
      if (Valid(pi.Thread)) CloseHandle(pi.Thread);
      if (Valid(output)) CloseHandle(output);
      if (Valid(error)) CloseHandle(error);
      if (Valid(input)) CloseHandle(input);
    }
  }
  public bool Stop(int timeoutMs) {
    if (job == IntPtr.Zero) return process == IntPtr.Zero;
    Check(TerminateJobObject(job, 1));
    int elapsed = 0;
    while (elapsed <= timeoutMs) {
      if (Empty && (process == IntPtr.Zero || HasExited)) return true;
      Thread.Sleep(50); elapsed += 50;
    }
    return false;
  }
  public void Dispose() {
    if (job != IntPtr.Zero) { CloseHandle(job); job = IntPtr.Zero; }
    if (process != IntPtr.Zero) { CloseHandle(process); process = IntPtr.Zero; }
  }
}
';$job=[LvwOwnedJob]::new();try{$job.Start('C:\Windows\System32\cmd.exe','\\wsl.localhost\Ubuntu-24.04\tmp\lvw-win-job-probe-25dkp0vn\stdout.log','\\wsl.localhost\Ubuntu-24.04\tmp\lvw-win-job-probe-25dkp0vn\stderr.log');$born=$job.BirthTicks;$ownedId=$job.Pid;if(!$job.Stop(5000) -or !$job.Empty -or !$job.HasExited){throw 'KERNEL_JOB_EXIT_UNPROVEN'};@{status='NATIVE_JOB_KERNEL_PASS';pid=$ownedId;birth_ticks=$born;job_empty=$job.Empty;original_exited=$job.HasExited}|ConvertTo-Json -Compress}finally{$job.Dispose()}