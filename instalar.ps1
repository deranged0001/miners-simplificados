# Instala o miner da Kick (esta pasta), baixa o miner da Twitch do projeto original
# e cria o atalho "Miners Kick e Twitch" na Área de Trabalho.
# Uso: powershell -ExecutionPolicy Bypass -File .\instalar.ps1
# Pode ser rodado de novo: o que já estiver instalado é mantido.

# "Stop" quebraria no PowerShell 5.1: stderr de programas externos vira erro fatal. Cada passo checa $LASTEXITCODE.
$Repo = $PSScriptRoot
$TwitchDir = Join-Path $Repo "twitch\Twitch-Channel-Points-Miner-v2"
# Versão do miner da Twitch revisada para este projeto
$TwitchRepo = "https://github.com/rdavydov/Twitch-Channel-Points-Miner-v2"
$TwitchCommit = "8a35f87"

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Green }
function Fail($msg) { Write-Host "`nERRO: $msg" -ForegroundColor Red; exit 1 }

# 1. Python 3.10 a 3.13 (versões mais novas podem não ter as bibliotecas prontas)
Step "Procurando Python 3.10 a 3.13"
$Py = $null
if (Get-Command py -ErrorAction SilentlyContinue) {
    foreach ($v in "3.12", "3.13", "3.11", "3.10") {
        & py "-$v" -c "import sys" 2>$null
        if ($LASTEXITCODE -eq 0) { $Py = @("py", "-$v"); break }
    }
}
if (-not $Py -and (Get-Command python -ErrorAction SilentlyContinue)) {
    & python -c "import sys; sys.exit(0 if (3, 10) <= sys.version_info[:2] <= (3, 13) else 1)" 2>$null
    if ($LASTEXITCODE -eq 0) { $Py = @("python") }
}
if (-not $Py) { Fail "Python 3.10 a 3.13 nao encontrado. Instale com: winget install Python.Python.3.12" }
$PyExe = $Py[0]
$PyArgs = @($Py | Select-Object -Skip 1)
function PyRun { & $PyExe @PyArgs @args }
Write-Host ("Usando: " + (PyRun -c "import sys; print(sys.executable, sys.version.split()[0])"))

PyRun -c "import tkinter" 2>$null
if ($LASTEXITCODE -ne 0) { Fail "Este Python nao tem tkinter (necessario para a janela de controle). Reinstale pelo instalador oficial do python.org." }

if (-not (Get-Command git -ErrorAction SilentlyContinue)) { Fail "Git nao encontrado. Instale com: winget install Git.Git" }

# 2. Miner da Kick
Step "Instalando o miner da Kick"
if (-not (Test-Path "$Repo\.venv\Scripts\python.exe")) { PyRun -m venv "$Repo\.venv" }
& "$Repo\.venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r "$Repo\requirements.txt"
if ($LASTEXITCODE -ne 0) { Fail "pip falhou no miner da Kick." }
if (-not (Test-Path "$Repo\config.json")) {
    Copy-Item "$Repo\config.example.json" "$Repo\config.json"
    Write-Host "Criado config.json a partir do config.example.json"
}

# 3. Miner da Twitch, baixado do projeto original na versão revisada
Step "Instalando o miner da Twitch"
if (-not (Test-Path $TwitchDir)) {
    git clone -q $TwitchRepo $TwitchDir
    if ($LASTEXITCODE -ne 0) { Fail "Nao foi possivel baixar $TwitchRepo" }
    git -C $TwitchDir -c advice.detachedHead=false checkout -q $TwitchCommit
    if ($LASTEXITCODE -ne 0) { Fail "Versao $TwitchCommit do miner da Twitch nao encontrada." }
}
if (-not (Test-Path "$TwitchDir\.venv\Scripts\python.exe")) { PyRun -m venv "$TwitchDir\.venv" }
& "$TwitchDir\.venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r "$TwitchDir\requirements.txt"
if ($LASTEXITCODE -ne 0) { Fail "pip falhou no miner da Twitch." }
if (-not (Test-Path "$TwitchDir\run.py")) {
    Copy-Item "$Repo\twitch\run.example.py" "$TwitchDir\run.py"
    Write-Host "Criado run.py a partir do twitch\run.example.py"
}

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

Step "Pronto! Falta configurar:"
Write-Host "  1. Kick:   coloque seu token e seus canais em $Repo\config.json"
Write-Host "  2. Twitch: coloque seu usuario e seus canais em $TwitchDir\run.py"
Write-Host "  3. Twitch, so na primeira vez: rode o comando abaixo e digite o codigo em twitch.tv/activate"
Write-Host "       cd `"$TwitchDir`"; .\.venv\Scripts\python.exe run.py"
Write-Host "     Depois do login, feche com Ctrl+C."
Write-Host "  4. Abra o atalho 'Miners Kick e Twitch' na Area de Trabalho e clique em Iniciar."
