$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Security
Write-Host 'Configuration Google de Nova - stockage chiffre sur ce compte Windows.'
Write-Host 'Saisissez le secret renouvele du client OAuth Application de bureau.'
Write-Host 'Il ne sera envoye ni dans GitHub ni dans un fichier en clair.'
$novaSecureValue = Read-Host 'Secret du client Google' -AsSecureString
$novaPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($novaSecureValue)
try {
    $novaPlainValue = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($novaPointer).Trim()
    if ($novaPlainValue.Length -lt 10) { throw 'Valeur vide ou trop courte.' }
    $novaData = [Text.Encoding]::UTF8.GetBytes($novaPlainValue)
    $novaEntropy = [Text.Encoding]::UTF8.GetBytes('NovaBrowser-local-vault-v1')
    $novaCipher = [Security.Cryptography.ProtectedData]::Protect($novaData, $novaEntropy, [Security.Cryptography.DataProtectionScope]::CurrentUser)
    $novaDirectory = Join-Path $env:LOCALAPPDATA 'NovaBrowser/NovaBrowser'
    New-Item -ItemType Directory -Path $novaDirectory -Force | Out-Null
    $novaDestination = Join-Path $novaDirectory 'google-client.dat'
    $novaTemporary = Join-Path $novaDirectory 'google-client.tmp'
    [IO.File]::WriteAllBytes($novaTemporary, $novaCipher)
    Move-Item -LiteralPath $novaTemporary -Destination $novaDestination -Force
    Write-Host 'Configuration enregistree. Vous pouvez cliquer Continuer avec Google dans Nova.'
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($novaPointer)
    if ($novaData) { [Array]::Clear($novaData, 0, $novaData.Length) }
    $novaPlainValue = $null
    $novaSecureValue.Dispose()
}
Read-Host 'Entree pour fermer'
