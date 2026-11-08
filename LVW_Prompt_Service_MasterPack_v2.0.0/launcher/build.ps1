$ErrorActionPreference = 'Stop'
$pack = Split-Path $PSScriptRoot -Parent
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
& $compiler /nologo /target:winexe /platform:anycpu /optimize+ /codepage:65001 /reference:System.Windows.Forms.dll /reference:System.Drawing.dll /reference:System.dll /reference:System.Core.dll ('/win32icon:' + (Join-Path $PSScriptRoot 'LVW.ico')) ('/out:' + (Join-Path $pack 'LVW.exe')) (Join-Path $PSScriptRoot 'Launcher.cs')
if ($LASTEXITCODE -ne 0) { throw 'Launcher compilation failed.' }
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut((Join-Path $pack '启动LVW.lnk'))
$link.TargetPath = Join-Path $pack 'LVW.exe'
$link.WorkingDirectory = $pack
$link.IconLocation = (Join-Path $pack 'LVW.exe') + ',0'
$link.Description = 'LVW local image and video prompt workbench'
$link.Save()
