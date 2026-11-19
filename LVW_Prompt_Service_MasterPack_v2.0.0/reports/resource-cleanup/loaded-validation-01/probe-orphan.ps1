$ErrorActionPreference='Stop'
$expectedExe='C:\Users\Administrator\AppData\Local\Programs\Ollama\ollama.exe'
$parentId=28716
$parentBirth=639307041926107858L
$loadedBefore=[DateTimeOffset]::Parse('2026-11-19T16:56:49.3026397Z').UtcDateTime.Ticks
$result=@()
foreach($row in @(Get-CimInstance Win32_Process -Filter "Name='ollama.exe' AND ParentProcessId=28716")) {
 $p=[Diagnostics.Process]::GetProcessById([int]$row.ProcessId)
 $heldHandle=$p.Handle
 $birth=$p.StartTime.ToUniversalTime().Ticks
 $current=Get-CimInstance Win32_Process -Filter ("ProcessId="+$p.Id)
 $result+=@{pid=$p.Id;birth_ticks=$birth;parent_pid=$current.ParentProcessId;executable_matches=($p.MainModule.FileName -ieq $expectedExe);runner_role=($current.CommandLine -match '\srunner(?:\s|$)');within_original_live_window=($birth -ge $parentBirth -and $birth -le $loadedBefore);cim_creation_ticks=$current.CreationDate.ToUniversalTime().Ticks;live=(-not $p.HasExited)}
 $p.Dispose()
}
ConvertTo-Json -InputObject $result -Compress
