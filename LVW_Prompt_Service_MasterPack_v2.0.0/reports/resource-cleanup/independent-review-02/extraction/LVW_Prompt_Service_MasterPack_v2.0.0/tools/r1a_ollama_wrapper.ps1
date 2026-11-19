param(
  [Parameter(Mandatory=$true)][string]$Exe,
  [Parameter(Mandatory=$true)][string]$Owner,
  [Parameter(Mandatory=$true)][string]$Terminal,
  [Parameter(Mandatory=$true)][string]$StopRequest,
  [Parameter(Mandatory=$true)][string]$StdoutLog,
  [Parameter(Mandatory=$true)][string]$StderrLog,
  [Parameter(Mandatory=$true)][string]$ErrorLog,
  [int]$MaxSeconds = 420
)

$ErrorActionPreference = 'Stop'
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_NO_CLOUD = '1'
$env:NO_PROXY = '127.0.0.1,localhost'
$utf8 = New-Object System.Text.UTF8Encoding($false)
$child = $null
$stopRequested = $false
$leaseExpired = $false
$deadline = [DateTime]::UtcNow.AddSeconds($MaxSeconds)

try {
  $child = Start-Process -FilePath $Exe -ArgumentList @('serve') -PassThru -WindowStyle Hidden `
    -RedirectStandardOutput $StdoutLog -RedirectStandardError $StderrLog
  $identity = [pscustomobject]@{
    pid = $child.Id
    start_filetime_utc = $child.StartTime.ToFileTimeUtc().ToString()
    executable_path = $child.Path
  }
  [IO.File]::WriteAllText($Owner, ($identity | ConvertTo-Json -Compress), $utf8)
  while (-not $child.HasExited) {
    if ([DateTime]::UtcNow -ge $deadline) {
      $leaseExpired = $true
      $child.Kill()
      $child.WaitForExit()
      break
    }
    if (Test-Path -LiteralPath $StopRequest) {
      $stopRequested = $true
      $child.Kill()
      $child.WaitForExit()
      break
    }
    Start-Sleep -Milliseconds 200
  }
  $terminalState = [pscustomobject]@{
    pid = $child.Id
    start_filetime_utc = $identity.start_filetime_utc
    executable_path = $identity.executable_path
    child_exited = $child.HasExited
    stop_requested = $stopRequested
    lease_expired = $leaseExpired
    exit_code = $child.ExitCode
    wrapper_error = $false
  }
  [IO.File]::WriteAllText($Terminal, ($terminalState | ConvertTo-Json -Compress), $utf8)
  exit 0
} catch {
  $message = $_.Exception.GetType().FullName + ':' + $_.Exception.Message
  [IO.File]::WriteAllText($ErrorLog, $message, $utf8)
  if ($null -ne $child -and -not $child.HasExited) {
    $child.Kill()
    $child.WaitForExit()
  }
  $pidValue = $null
  $childExited = $true
  if ($null -ne $child) {
    $pidValue = $child.Id
    $childExited = $child.HasExited
  }
  $terminalState = [pscustomobject]@{
    pid = $pidValue
    child_exited = $childExited
    stop_requested = $false
    lease_expired = $leaseExpired
    wrapper_error = $true
  }
  [IO.File]::WriteAllText($Terminal, ($terminalState | ConvertTo-Json -Compress), $utf8)
  exit 1
}
