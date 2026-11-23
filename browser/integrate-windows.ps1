param([Parameter(Mandatory=$true)][string]$Executable)
$ErrorActionPreference='Stop'
$target=[IO.Path]::GetFullPath($Executable)
if (-not (Test-Path -LiteralPath $target) -or [IO.Path]::GetExtension($target) -ne '.exe') { exit 2 }
$shell=New-Object -ComObject WScript.Shell
$programs=[Environment]::GetFolderPath('Programs')
$shortcut=$shell.CreateShortcut((Join-Path $programs 'Nova.lnk'))
$shortcut.TargetPath=$target
$shortcut.WorkingDirectory=[IO.Path]::GetDirectoryName($target)
$shortcut.IconLocation=$target+',0'
$shortcut.Description='Nova'
$shortcut.Save()
