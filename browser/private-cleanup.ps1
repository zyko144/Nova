param([Parameter(Mandatory=$true)][string]$Directory,[string]$ProcessIds='')
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\')+'\'
$target=[IO.Path]::GetFullPath($Directory).TrimEnd('\')
if (-not $target.StartsWith($root,[StringComparison]::OrdinalIgnoreCase) -or [IO.Path]::GetDirectoryName($target) -ne $root.TrimEnd('\') -or [IO.Path]::GetFileName($target) -notmatch '^Nova-private-[a-zA-Z0-9_-]+$') { exit 2 }
foreach($processIdText in ($ProcessIds -split ',')) {
    $processNumber=0
    if ([int]::TryParse($processIdText,[ref]$processNumber) -and $processNumber -gt 0) {
        $process=Get-Process -Id $processNumber -ErrorAction SilentlyContinue
        if($process){$null=$process.WaitForExit(10000)}
    }
}
for($attempt=0;$attempt -lt 20;$attempt++) {
    try { if(Test-Path -LiteralPath $target){Remove-Item -LiteralPath $target -Recurse -Force};exit 0 }
    catch { Start-Sleep -Milliseconds 500 }
}
exit 1
