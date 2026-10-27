# Atualiza esta pasta com a versão mais nova do GitHub, sem apagar a sua configuração.
# Uso: dois cliques no atualizar.bat, ou o botão "Atualizar" do app de controle.
#
# Só copia por cima os arquivos do repositório. Ficam como estão: config.json, .venv,
# o miner da Twitch baixado (com config_twitch.json e o login em cookies/) e os logs,
# porque nada disso está no ZIP do GitHub.

$ProgressPreference = "SilentlyContinue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Repo = $PSScriptRoot
$GitHub = "deranged0001/miners-simplificados"
$Marker = Join-Path $Repo ".atualizacao"  # commit instalado; não vai para o git

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Green }
function Fail($msg) { Write-Host "`nERRO: $msg" -ForegroundColor Red; exit 1 }

Step "Procurando atualizacao"
try {
    $Latest = (Invoke-RestMethod "https://api.github.com/repos/$GitHub/commits/main" -UseBasicParsing).sha
} catch { Fail "Nao foi possivel consultar o GitHub: $($_.Exception.Message)" }
$Current = if (Test-Path $Marker) { (Get-Content $Marker).Trim() } else { "" }
if ($Current -eq $Latest) {
    Write-Host "  Voce ja esta na versao mais nova ($($Latest.Substring(0, 7)))."
    exit 0
}

# Os miners precisam reiniciar para usar o código novo
Step "Parando os miners"
# Desliga o vigia do app de controle, senão ele reabre os miners no meio da cópia
Remove-Item (Join-Path $Repo "controle\.guardiao") -ErrorAction SilentlyContinue
$Venvs = @("$Repo\.venv", "$Repo\twitch\Twitch-Channel-Points-Miner-v2\.venv") | ForEach-Object { $_.ToLower() }
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object {
    $p = "$($_.ExecutablePath)".ToLower()
    $Venvs | Where-Object { $p.StartsWith($_) }
} | ForEach-Object { taskkill /PID $_.ProcessId /T /F | Out-Null }

Step "Baixando a versao $($Latest.Substring(0, 7))"
$Tmp = Join-Path $env:TEMP "miners-atualizacao-$Latest"
$Zip = "$Tmp.zip"
try {
    Invoke-WebRequest "https://github.com/$GitHub/archive/$Latest.zip" -OutFile $Zip -UseBasicParsing
    Expand-Archive $Zip -DestinationPath $Tmp -Force
} catch { Fail "Nao foi possivel baixar a atualizacao: $($_.Exception.Message)" }
$Src = Get-ChildItem $Tmp -Directory | Select-Object -First 1

Step "Copiando os arquivos novos"
# /E copia subpastas e não apaga nada que só existe aqui (config, venv, logs)
robocopy $Src.FullName $Repo /E /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { Fail "A copia dos arquivos falhou (robocopy $LASTEXITCODE)." }
Remove-Item $Zip -ErrorAction SilentlyContinue
cmd /c rmdir /s /q "$Tmp"

# Dependências novas, versão da Twitch, script de login e atalho
Step "Rodando o instalador"
& powershell -NoProfile -ExecutionPolicy Bypass -File "$Repo\instalar.ps1"
if ($LASTEXITCODE -ne 0) { Fail "O instalador falhou. Veja as mensagens acima." }

Set-Content $Marker $Latest
Step "Atualizado!"
Write-Host "  Feche o app 'Miners Kick e Twitch', abra de novo e clique em Iniciar."
