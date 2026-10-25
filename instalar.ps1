# Instala o miner da Kick (esta pasta), baixa o miner da Twitch do projeto original
# e cria o atalho "Miners Kick e Twitch" na Área de Trabalho.
# Uso: dois cliques no instalar.bat (ou: powershell -ExecutionPolicy Bypass -File .\instalar.ps1)
# Pode ser rodado de novo: o que já estiver instalado é mantido.

# "Stop" quebraria no PowerShell 5.1: stderr de programas externos vira erro fatal. Cada passo checa $LASTEXITCODE.
$ProgressPreference = "SilentlyContinue"  # a barra de progresso deixa o download até 10x mais lento no PS 5.1
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Repo = $PSScriptRoot
$TwitchDir = Join-Path $Repo "twitch\Twitch-Channel-Points-Miner-v2"
# Versão do miner da Twitch revisada para este projeto.
# SHA completo: um prefixo curto poderia, em tese, coincidir com outro commit.
$TwitchRepo = "https://github.com/rdavydov/Twitch-Channel-Points-Miner-v2"
$TwitchCommit = "8a35f87cd5345074003c7f6eedb48aedadc3b9b3"

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Green }
function Fail($msg) { Write-Host "`nERRO: $msg" -ForegroundColor Red; exit 1 }

# 1. Python 3.10 a 3.13 (versões mais novas podem não ter as bibliotecas prontas)
function Find-Python {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        foreach ($v in "3.12", "3.13", "3.11", "3.10") {
            & py "-$v" -c "import sys" 2>$null
            if ($LASTEXITCODE -eq 0) { return @("py", "-$v") }
        }
    }
    # Instalação feita agora pelo winget ainda não está no PATH desta janela
    $local = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
    if (Test-Path $local) { return @($local) }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        & python -c "import sys; sys.exit(0 if (3, 10) <= sys.version_info[:2] <= (3, 13) else 1)" 2>$null
        if ($LASTEXITCODE -eq 0) { return @("python") }
    }
    return $null
}

Step "Procurando Python 3.10 a 3.13"
$Py = Find-Python
if (-not $Py) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Fail "Python nao encontrado. Instale o Python 3.12 em https://www.python.org/downloads/ e rode o instalador de novo."
    }
    Step "Instalando Python 3.12 (pode levar alguns minutos)"
    winget install -e --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
    $Py = Find-Python
    if (-not $Py) { Fail "A instalacao do Python falhou. Instale o Python 3.12 em https://www.python.org/downloads/ e rode o instalador de novo." }
}
$PyExe = $Py[0]
$PyArgs = @($Py | Select-Object -Skip 1)
function PyRun { & $PyExe @PyArgs @args }
Write-Host ("Usando: " + (PyRun -c "import sys; print(sys.executable, sys.version.split()[0])"))

PyRun -c "import tkinter" 2>$null
if ($LASTEXITCODE -ne 0) { Fail "Este Python nao tem tkinter (necessario para a janela de controle). Reinstale pelo instalador oficial do python.org." }

# 2. Miner da Kick
Step "Instalando o miner da Kick"
if (-not (Test-Path "$Repo\.venv\Scripts\python.exe")) { PyRun -m venv "$Repo\.venv" }
& "$Repo\.venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r "$Repo\requirements.txt"
if ($LASTEXITCODE -ne 0) { Fail "pip falhou no miner da Kick." }
if (-not (Test-Path "$Repo\config.json")) {
    Copy-Item "$Repo\config.example.json" "$Repo\config.json"
}

# 3. Miner da Twitch, baixado do projeto original na versão revisada
Step "Instalando o miner da Twitch"
if (-not (Test-Path $TwitchDir)) {
    $Zip = Join-Path $env:TEMP "twitch-miner-$TwitchCommit.zip"
    try {
        Invoke-WebRequest "$TwitchRepo/archive/$TwitchCommit.zip" -OutFile $Zip -UseBasicParsing
        Expand-Archive $Zip -DestinationPath "$Repo\twitch" -Force
    } catch { Fail "Nao foi possivel baixar o miner da Twitch: $($_.Exception.Message)" }
    Remove-Item $Zip -ErrorAction SilentlyContinue
    Rename-Item "$Repo\twitch\Twitch-Channel-Points-Miner-v2-$TwitchCommit" "Twitch-Channel-Points-Miner-v2"
    Set-Content "$TwitchDir\.versao" $TwitchCommit
}
# Confere sempre, inclusive em reinstalação: a pasta precisa estar exatamente na versão revisada
if (Test-Path "$TwitchDir\.git") { $Head = (git -C $TwitchDir rev-parse HEAD).Trim() }
elseif (Test-Path "$TwitchDir\.versao") { $Head = (Get-Content "$TwitchDir\.versao").Trim() }
else { $Head = "desconhecida" }
if ($Head -ne $TwitchCommit) { Fail "O miner da Twitch esta na versao $Head, esperado $TwitchCommit. Apague a pasta $TwitchDir e rode de novo." }

if (-not (Test-Path "$TwitchDir\.venv\Scripts\python.exe")) { PyRun -m venv "$TwitchDir\.venv" }
& "$TwitchDir\.venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r "$TwitchDir\requirements.txt"
if ($LASTEXITCODE -ne 0) { Fail "pip falhou no miner da Twitch." }
if (-not (Test-Path "$TwitchDir\run.py")) { Copy-Item "$Repo\twitch\run.example.py" "$TwitchDir\run.py" }
# Script de login é nosso: sempre atualiza
Copy-Item "$Repo\twitch\login_twitch.py" "$TwitchDir\login_twitch.py" -Force

# 4. Atalho na Área de Trabalho, abrindo a janela de controle sem console
Step "Criando atalho na Area de Trabalho"
$Pythonw = (PyRun -c "import sys; print(sys.executable)").Trim() -replace "python\.exe$", "pythonw.exe"
$Desktop = [Environment]::GetFolderPath("Desktop")
$Lnk = (New-Object -ComObject WScript.Shell).CreateShortcut("$Desktop\Miners Kick e Twitch.lnk")
$Lnk.TargetPath = $Pythonw
$Lnk.Arguments = "`"$Repo\controle\controle_miners.pyw`""
$Lnk.WorkingDirectory = "$Repo\controle"
$Lnk.Description = "Iniciar e parar os miners da Kick e da Twitch"
if (Test-Path "$Repo\controle\miners.ico") { $Lnk.IconLocation = "$Repo\controle\miners.ico,0" }
$Lnk.Save()

Step "Pronto!"
Write-Host "  Abra o atalho 'Miners Kick e Twitch' na Area de Trabalho e clique em 'Configurar'."
