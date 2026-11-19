$ErrorActionPreference='Stop'
$expectedExe='C:\Users\Administrator\AppData\Local\Programs\Ollama\lib\ollama\llama-server.exe'
$parentId=28716
$parentBirth=639307041926107858L
$loadedBefore=[DateTimeOffset]::Parse('2026-11-19T16:56:49.3026397Z').UtcDateTime.Ticks
$expectedModel='sha256-7121486771cbfe218851513210c40b35dbdee93ab1ef43fe36283c883980f0df'
$rows=@(Get-CimInstance Win32_Process -Filter "Name='llama-server.exe' AND ParentProcessId=28716")
if($rows.Count -gt 1){throw 'AMBIGUOUS_MULTIPLE_RUNNERS'}
$result=@()
foreach($row in $rows) {
 $p=[Diagnostics.Process]::GetProcessById([int]$row.ProcessId)
 try {
  $heldHandle=$p.Handle
  $birth=$p.StartTime.ToUniversalTime().Ticks
  $current=Get-CimInstance Win32_Process -Filter ("ProcessId="+$p.Id)
  if($p.HasExited -or $current.ParentProcessId -ne $parentId -or $p.MainModule.FileName -ine $expectedExe -or $current.CommandLine -notmatch '--offline' -or $current.CommandLine -notmatch [regex]::Escape($expectedModel) -or $birth -lt $parentBirth -or $birth -gt $loadedBefore -or [Math]::Abs($current.CreationDate.ToUniversalTime().Ticks-$birth) -gt 10000){throw 'OWNERSHIP_NOT_PROVEN'}
  # Same held Process handle, not a PID/name-based kill. Creation is bounded
  # inside the original daemon's independently proven live interval.
  $p.Kill()
  if(!$p.WaitForExit(5000)){throw 'ORIGINAL_RUNNER_EXIT_UNPROVEN'}
  $result+=@{pid=$p.Id;birth_ticks=$birth;parent_pid=$parentId;executable_matches=$true;model_matches=$true;live_window_matches=$true;original_handle_exited=$p.HasExited}
 }finally{$p.Dispose()}
}
ConvertTo-Json -InputObject @{status='OWNED_RUNNER_RECOVERY';matched=$rows.Count;processes=$result} -Compress
