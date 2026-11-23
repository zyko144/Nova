$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
dotnet publish MediaHost/NovaMediaHost.csproj -c Release -r win-x64 --self-contained true -o MediaHost/bin-runtime
if ($LASTEXITCODE -ne 0) { throw 'Compilation du moteur vidéo échouée' }
Copy-Item autofill.js MediaHost/bin-runtime/autofill.js -Force
New-Item -ItemType Directory -Force MediaHost/bin-runtime/Extensions | Out-Null
Copy-Item blocker/ubol -Destination MediaHost/bin-runtime/Extensions/ -Recurse -Force
python -m PyInstaller --clean --noconfirm --windowed --icon nova.ico --add-data "assets;assets" --add-data "update-install.ps1;." --add-data "autofill.js;." --name NovaBrowser main.py
if ($LASTEXITCODE -ne 0) { throw 'Compilation échouée' }
# Qt 6.12 utilise les fonctions ICU du système Windows. Une autre icuuc.dll
# collectée par PyInstaller peut masquer celle du système et bloquer QtCore.
$icuFile = Join-Path $PSScriptRoot 'dist/NovaBrowser/_internal/icuuc.dll'
if (Test-Path -LiteralPath $icuFile) {
    Move-Item -LiteralPath $icuFile -Destination (Join-Path $PSScriptRoot 'build/icuuc-excluded.dll') -Force
}
Copy-Item MediaHost/bin-runtime -Destination dist/NovaBrowser/MediaHost -Recurse -Force
Copy-Item Configurer-Google-Nova.ps1,Configurer-Google.cmd dist/NovaBrowser/ -Force
Write-Output 'Prêt : dist/NovaBrowser/NovaBrowser.exe'
