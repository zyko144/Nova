param(
    [Parameter(Mandatory=$true)][string]$Archive,
    [Parameter(Mandatory=$true)][string]$Sha256,
    [Parameter(Mandatory=$true)][string]$InstallPath,
    [Parameter(Mandatory=$true)][int]$ParentPid,
    [Parameter(Mandatory=$true)][string]$Version,
    [Parameter(Mandatory=$true)][string]$StatePath
)
$ErrorActionPreference='Stop'
$installFull=[IO.Path]::GetFullPath($InstallPath).TrimEnd('\')
$archiveFull=[IO.Path]::GetFullPath($Archive)
$stateFull=[IO.Path]::GetFullPath($StatePath)
$parentFolder=[IO.Directory]::GetParent($installFull).FullName
$leaf=[IO.Path]::GetFileName($installFull)
$stageFull=Join-Path $parentFolder ($leaf+'.update-'+[Guid]::NewGuid().ToString('N'))
$backupFull=Join-Path $parentFolder ($leaf+'.backup-'+[Guid]::NewGuid().ToString('N'))
$movedOld=$false
$newInstalled=$false
function Save-Result([bool]$Success,[string]$Message) {
    @{success=$Success;version=$Version;message=$Message}|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $stateFull 'update-result.json') -Encoding UTF8
}
try {
    if ($Version -notmatch '^\d+\.\d+\.\d+$' -or $Sha256 -notmatch '^[a-fA-F0-9]{64}$') { throw 'Métadonnées de mise à jour invalides.' }
    if (-not (Test-Path -LiteralPath (Join-Path $installFull 'NovaBrowser.exe')) -or -not (Test-Path -LiteralPath (Join-Path $installFull '_internal'))) { throw 'Dossier Nova invalide.' }
    if (-not $archiveFull.StartsWith($stateFull.TrimEnd('\')+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Archive hors du dossier de mise à jour.' }
    $hasher=[Security.Cryptography.SHA256]::Create()
    $archiveStream=[IO.File]::OpenRead($archiveFull)
    try { $actualHash=([BitConverter]::ToString($hasher.ComputeHash($archiveStream))).Replace('-','') }
    finally { $archiveStream.Dispose();$hasher.Dispose() }
    if ($actualHash -ne $Sha256) { throw 'Empreinte du paquet incorrecte.' }
    $process=Get-Process -Id $ParentPid -ErrorAction SilentlyContinue
    if ($process -and -not $process.WaitForExit(60000)) { throw 'Nova est encore en cours d’utilisation.' }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip=[IO.Compression.ZipFile]::OpenRead($archiveFull)
    try {
        $total=0L
        if ($zip.Entries.Count -gt 20000) { throw 'Trop de fichiers dans le paquet.' }
        foreach ($entry in $zip.Entries) {
            $name=$entry.FullName.Replace('\','/')
            if ([IO.Path]::IsPathRooted($name) -or $name.Contains(':') -or $name.Split('/') -contains '..') { throw 'Chemin dangereux dans le paquet.' }
            $total+=$entry.Length
            if ($total -gt 3GB) { throw 'Paquet décompressé trop volumineux.' }
            $resolved=[IO.Path]::GetFullPath((Join-Path $stageFull $name))
            if (-not $resolved.StartsWith($stageFull.TrimEnd('\')+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Chemin hors du dossier de préparation.' }
        }
    } finally { $zip.Dispose() }
    [IO.Compression.ZipFile]::ExtractToDirectory($archiveFull,$stageFull)
    if (-not (Test-Path -LiteralPath (Join-Path $stageFull 'NovaBrowser.exe')) -or -not (Test-Path -LiteralPath (Join-Path $stageFull '_internal')) -or -not (Test-Path -LiteralPath (Join-Path $stageFull 'MediaHost'))) { throw 'Paquet Nova incomplet.' }
    # These two exact sibling paths are checked before either directory move.
    foreach($target in @($stageFull,$backupFull)) {
        if ([IO.Directory]::GetParent([IO.Path]::GetFullPath($target)).FullName -ne $parentFolder -or $target -eq $installFull) { throw 'Dossier de remplacement invalide.' }
    }
    Move-Item -LiteralPath $installFull -Destination $backupFull
    $movedOld=$true
    Move-Item -LiteralPath $stageFull -Destination $installFull
    $newInstalled=$true
    Save-Result $true ('Nova '+$Version+' est installé. Vos données ont été conservées.')
    Start-Process -FilePath (Join-Path $installFull 'NovaBrowser.exe') -WindowStyle Hidden
    # The previous installation is intentionally retained as a rollback backup.
} catch {
    $message=$_.Exception.Message
    if ($movedOld -and -not $newInstalled -and -not (Test-Path -LiteralPath $installFull)) {
        Move-Item -LiteralPath $backupFull -Destination $installFull
    }
    Save-Result $false ('Installation interrompue : '+$message)
    if (Test-Path -LiteralPath (Join-Path $installFull 'NovaBrowser.exe')) { Start-Process -FilePath (Join-Path $installFull 'NovaBrowser.exe') -WindowStyle Hidden }
    exit 1
}
