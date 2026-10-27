# Janela simples para iniciar e parar os miners da Kick e da Twitch em segundo plano.
# Roda com pythonw (sem console). Os miners continuam rodando mesmo se esta janela for fechada.
#
# Com "--guardiao" este mesmo arquivo vira o vigia: um processo escondido, aberto pelo
# Iniciar, que reinicia um miner que parou ou cujo log da Twitch travou. Ele também
# continua rodando com a janela fechada e sai sozinho depois do Parar ou do Atualizar.

import ctypes
import json
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
import tkinter as tk
from pathlib import Path
from tkinter import messagebox
from urllib.parse import unquote

# Este arquivo fica em <repo>/controle; o miner da Kick é a raiz do repo
# e o da Twitch é baixado pelo instalar.ps1 em <repo>/twitch
REPO = Path(__file__).resolve().parent.parent
MINERS = {
    "Kick": {
        "dir": REPO,
        "script": "main.py",
        "out": "miner-saida.txt",
        "err": "miner-log.txt",  # o loguru escreve no stderr
    },
    "Twitch": {
        "dir": REPO / "twitch" / "Twitch-Channel-Points-Miner-v2",
        "script": "run.py",
        "out": "miner-log.txt",
        "err": "miner-erros.txt",
    },
}
PAINEL = "http://localhost:5000"
NO_WINDOW = subprocess.CREATE_NO_WINDOW
KICK_CONFIG = REPO / "config.json"
TWITCH_CONFIG = MINERS["Twitch"]["dir"] / "config_twitch.json"

# Vigia: o arquivo .guardiao existe enquanto ele deve rodar (o Iniciar cria; Parar e Atualizar apagam)
GUARD_FLAG = Path(__file__).with_name(".guardiao")
GUARD_LOG = Path(__file__).with_name("guardiao-log.txt")
GUARD_MUTEX = "Local\\miners_kick_twitch_guardiao"
GUARD_INTERVAL = 60       # segundos entre as checagens
TWITCH_STALL = 10 * 60    # log da Twitch parado por este tempo = miner travado
RESTART_GAP = 10 * 60     # tempo mínimo entre dois reinícios do mesmo miner

BG, CARD, TEXT, MUTED = "#0b0d0c", "#131715", "#e9efeb", "#8a968f"
GREEN, RED, AMBER = "#53fc18", "#ff5a5f", "#ffb547"


def running_pids():
    """{miner: [pids]} dos lançadores python.exe do .venv de cada miner.
    O lançador do venv cria um python filho; parar com /T derruba os dois."""
    ps = (
        "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
        "% { \"$($_.ProcessId)|$($_.ExecutablePath)\" }"
    )
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps],
        capture_output=True, text=True, creationflags=NO_WINDOW,
    ).stdout
    result = {name: [] for name in MINERS}
    for line in out.splitlines():
        pid, _, path = line.partition("|")
        for name, m in MINERS.items():
            venv = str(m["dir"] / ".venv").lower()
            if path.lower().startswith(venv):
                result[name].append(int(pid))
    return result


def installed(name):
    return (MINERS[name]["dir"] / ".venv" / "Scripts" / "python.exe").exists()


def start_miner(name):
    m = MINERS[name]
    # Os arquivos são recriados a cada início; o processo filho fica com os handles
    with open(m["dir"] / m["out"], "w", encoding="utf-8") as out, \
         open(m["dir"] / m["err"], "w", encoding="utf-8") as err:
        subprocess.Popen(
            [str(m["dir"] / ".venv" / "Scripts" / "python.exe"), "-u", m["script"]],
            cwd=m["dir"], stdout=out, stderr=err, stdin=subprocess.DEVNULL,
            creationflags=NO_WINDOW,
        )


def stop_pids(pids):
    for pid in pids:
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True, creationflags=NO_WINDOW,
        )


def clean_channels(text):
    """Um canal por linha (ou separados por vírgula); aceita o link do canal.
    Devolve (canais, inválidos)."""
    names, bad = [], []
    for item in re.split(r"[\s,;]+", text):
        name = item.strip().rstrip("/").split("/")[-1].lstrip("@").lower()
        if not name:
            continue
        if re.fullmatch(r"[a-z0-9_-]{2,30}", name):
            if name not in names:
                names.append(name)
        else:
            bad.append(item)
    return names, bad


def clean_token(token):
    """Aceita o valor do header (com ou sem "Bearer ") ou o cookie session_token (com %7C)."""
    token = unquote(token.strip())
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    return token


def load_kick_config():
    if not KICK_CONFIG.exists():
        shutil.copy(REPO / "config.example.json", KICK_CONFIG)
    return json.loads(KICK_CONFIG.read_text(encoding="utf-8"))


def kick_settings():
    """(token, canais) da primeira conta; vazio se ainda for o exemplo."""
    try:
        acc = load_kick_config()["Accounts"][0]
    except (OSError, ValueError, KeyError, IndexError):
        return "", []
    if acc.get("token", "").startswith("YOUR_KICK_TOKEN"):
        return "", []
    return acc.get("token", ""), acc.get("streamers", [])


def save_kick(token, channels):
    # Mantém o resto do config.json (Telegram, Discord...) e deixa só uma conta
    config = load_kick_config()
    old = (config.get("Accounts") or [{}])[0]
    acc = {"alias": "Minha conta", "proxy": None}
    if not old.get("token", "").startswith("YOUR_KICK_TOKEN"):
        acc.update(old)
    # O miner só assiste quem está ao vivo; com o limite igual ao número de canais, todos cabem
    acc.update(token=token, streamers=channels, max_concurrent=max(len(channels), 1))
    config["Accounts"] = [acc]
    config.setdefault("WebDashboard", {})["enabled"] = True
    KICK_CONFIG.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")


def twitch_settings():
    try:
        config = json.loads(TWITCH_CONFIG.read_text(encoding="utf-8"))
        return config["username"], config["streamers"]
    except (OSError, ValueError, KeyError):
        return "", []


def save_twitch(username, channels):
    TWITCH_CONFIG.write_text(
        json.dumps({"username": username, "streamers": channels}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def configured(name):
    if name == "Kick":
        return bool(kick_settings()[0])
    return bool(twitch_settings()[0])


def twitch_logged_in():
    user = twitch_settings()[0]
    return bool(user) and (MINERS["Twitch"]["dir"] / "cookies" / f"{user}.pkl").exists()


def ready(name):
    """Instalado, configurado e, na Twitch, com login feito.
    Sem login o miner da Twitch esperaria o código numa janela escondida."""
    return installed(name) and configured(name) and (name == "Kick" or twitch_logged_in())


def open_twitch_login():
    m = MINERS["Twitch"]
    subprocess.Popen(
        [str(m["dir"] / ".venv" / "Scripts" / "python.exe"), "login_twitch.py"],
        cwd=m["dir"], creationflags=subprocess.CREATE_NEW_CONSOLE,
    )


def painel_up():
    try:
        urllib.request.urlopen(PAINEL + "/api/data", timeout=2)
        return True
    except OSError:
        return False


# ---------------------------------------------------------------- vigia

def guard_running():
    """O mutex com nome só existe enquanto um vigia está vivo."""
    k32 = ctypes.windll.kernel32
    k32.OpenMutexW.restype = ctypes.c_void_p
    handle = k32.OpenMutexW(0x00100000, False, GUARD_MUTEX)  # SYNCHRONIZE
    if handle:
        k32.CloseHandle(handle)
        return True
    return False


def start_guard():
    GUARD_FLAG.write_text("ligado", encoding="utf-8")
    if not guard_running():
        subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--guardiao"],
            cwd=Path(__file__).parent, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=NO_WINDOW,
        )


def stop_guard():
    """O vigia confere o arquivo a cada minuto e sai quando ele some."""
    GUARD_FLAG.unlink(missing_ok=True)


def guard_log(text):
    try:
        if GUARD_LOG.exists() and GUARD_LOG.stat().st_size > 1_000_000:
            GUARD_LOG.write_text("", encoding="utf-8")  # não deixa crescer para sempre
        with open(GUARD_LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%d/%m %H:%M:%S ") + text + "\n")
    except OSError:
        pass


def twitch_log_file():
    """O log completo do miner (nível DEBUG) é escrito a cada poucos segundos,
    mesmo sem canal ao vivo; o miner-log.txt pode ficar minutos sem nada."""
    user = twitch_settings()[0]
    full = MINERS["Twitch"]["dir"] / "logs" / f"{user}.log"
    return full if user and full.exists() else MINERS["Twitch"]["dir"] / MINERS["Twitch"]["out"]


def file_mark(path):
    try:
        st = path.stat()
        return st.st_size, st.st_mtime
    except OSError:
        return None


class Guard:
    """Uma rodada por minuto. Separado do loop para dar para testar."""

    def __init__(self, now):
        self.missing = {name: 0 for name in MINERS}
        self.last_restart = {name: now for name in MINERS}  # carência logo após abrir
        self.log_mark = None
        self.log_changed = now

    def restart(self, name, pids, reason, now):
        guard_log(f"{name}: {reason}; reiniciando.")
        stop_pids(pids)
        time.sleep(3)
        start_miner(name)
        self.last_restart[name] = now
        self.missing[name] = 0
        if name == "Twitch":
            self.log_mark, self.log_changed = None, now

    def check(self, now):
        pids = running_pids()
        for name in MINERS:
            if not ready(name):
                continue
            recent = now - self.last_restart[name] < RESTART_GAP
            if not pids[name]:
                # Duas rodadas seguidas, para não brigar com o Configurar (para e inicia em 2 s)
                self.missing[name] += 1
                if self.missing[name] >= 2 and not recent:
                    self.restart(name, [], "não estava rodando", now)
                continue
            self.missing[name] = 0
            if name != "Twitch":
                continue
            mark = file_mark(twitch_log_file())
            if mark != self.log_mark:
                self.log_mark, self.log_changed = mark, now
            elif now - self.log_changed >= TWITCH_STALL and not recent:
                minutes = int((now - self.log_changed) // 60)
                self.restart(name, pids[name], f"log parado há {minutes} min", now)


def run_guard():
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateMutexW.restype = ctypes.c_void_p
    k32.CloseHandle.argtypes = [ctypes.c_void_p]
    mutex = k32.CreateMutexW(None, False, GUARD_MUTEX)
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS: já tem um vigia
        return
    guard_log("Vigia ligado.")
    guard = Guard(time.time())
    while GUARD_FLAG.exists():
        try:
            guard.check(time.time())
        except Exception as e:
            guard_log(f"Erro na checagem: {e}")
        time.sleep(GUARD_INTERVAL)
    guard_log("Vigia desligado.")
    k32.CloseHandle(mutex)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Miners Kick e Twitch")
        # Ícone opcional: coloque um miners.ico nesta pasta (ele não vai para o git)
        icon = Path(__file__).with_name("miners.ico")
        if icon.exists():
            self.iconbitmap(str(icon))
        self.configure(bg=BG, padx=20, pady=18)
        self.resizable(False, False)
        self.busy = False

        tk.Label(self, text="Miners", bg=BG, fg=TEXT,
                 font=("Segoe UI", 16, "bold")).pack(anchor="w")
        tk.Label(self, text="Kick e Twitch em segundo plano", bg=BG, fg=MUTED,
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 12))

        self.status = {}
        for name in MINERS:
            row = tk.Frame(self, bg=CARD, padx=12, pady=10)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=name, bg=CARD, fg=TEXT, width=10, anchor="w",
                     font=("Segoe UI", 11, "bold")).pack(side="left")
            lbl = tk.Label(row, text="verificando…", bg=CARD, fg=MUTED,
                           font=("Segoe UI", 10))
            lbl.pack(side="right")
            self.status[name] = lbl

        self.guard_lbl = tk.Label(self, text="", bg=BG, fg=MUTED, font=("Segoe UI", 9))
        self.guard_lbl.pack(anchor="w", pady=(4, 0))

        btns = tk.Frame(self, bg=BG)
        btns.pack(fill="x", pady=(14, 0))
        self.btn_start = self._button(btns, "▶  Iniciar", GREEN, "#000", self.on_start)
        self.btn_start.pack(side="left", expand=True, fill="x", padx=(0, 4))
        self.btn_stop = self._button(btns, "■  Parar", "#2a2f2c", TEXT, self.on_stop)
        self.btn_stop.pack(side="left", expand=True, fill="x", padx=(4, 0))

        self.btn_panel = self._button(self, "Abrir painel da Kick", CARD, TEXT,
                                      lambda: webbrowser.open(PAINEL))
        self.btn_panel.pack(fill="x", pady=(8, 0))

        extra = tk.Frame(self, bg=BG)
        extra.pack(fill="x", pady=(8, 0))
        self._button(extra, "⚙  Configurar", CARD, TEXT, self.on_config).pack(
            side="left", expand=True, fill="x", padx=(0, 4))
        self._button(extra, "Login da Twitch", CARD, TEXT, self.on_login).pack(
            side="left", expand=True, fill="x", padx=(4, 0))

        self._button(self, "⟳  Atualizar", CARD, MUTED, self.on_update).pack(fill="x", pady=(8, 0))

        self.msg = tk.Label(self, text="", bg=BG, fg=MUTED, font=("Segoe UI", 9),
                            wraplength=280, justify="left")
        self.msg.pack(anchor="w", pady=(10, 0))

        # Volta a ligar o vigia se o último clique foi Iniciar (ex.: o PC reiniciou)
        if GUARD_FLAG.exists():
            start_guard()
        self.refresh()

    def _button(self, parent, text, bg, fg, cmd):
        return tk.Button(parent, text=text, bg=bg, fg=fg, activebackground=bg,
                         activeforeground=fg, relief="flat", bd=0, cursor="hand2",
                         font=("Segoe UI", 10, "bold"), padx=10, pady=8, command=cmd)

    def run_bg(self, work, done_msg):
        """Roda work() fora da thread da janela para ela não travar."""
        if self.busy:
            return
        self.busy = True
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="disabled")

        def task():
            try:
                work()
                msg = done_msg
            except Exception as e:
                msg = f"Erro: {e}"
            self.after(0, lambda: self._finish(msg))

        threading.Thread(target=task, daemon=True).start()

    def _finish(self, msg):
        self.busy = False
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="normal")
        self.msg.config(text=msg)
        self.refresh(schedule=False)

    def on_start(self):
        self.msg.config(text="Iniciando…")

        def work():
            pids = running_pids()
            if not any(ready(name) for name in MINERS):
                raise RuntimeError("nada pronto para iniciar. Clique em Configurar"
                                   " (e em Login da Twitch, se usar a Twitch).")
            for name in MINERS:
                if ready(name) and not pids[name]:
                    start_miner(name)
            start_guard()
            if not ready("Kick"):
                return
            # O painel sobe em ~1 s; espera até 20 s antes de abrir o navegador
            for _ in range(20):
                if painel_up():
                    webbrowser.open(PAINEL)
                    return
                threading.Event().wait(1)
            raise RuntimeError("o painel da Kick não respondeu. Veja miner-log.txt na pasta da Kick.")

        self.run_bg(work, "Miners prontos iniciados. O painel da Kick abre no navegador.")

    def on_stop(self):
        self.msg.config(text="Parando…")

        def work():
            stop_guard()  # antes de parar, senão o vigia inicia de novo
            for pids in running_pids().values():
                stop_pids(pids)

        self.run_bg(work, "Miners parados.")

    def on_login(self):
        if not installed("Twitch"):
            self.msg.config(text="O miner da Twitch não está instalado. Rode o instalar.bat.")
        elif not twitch_settings()[0]:
            self.msg.config(text="Primeiro clique em Configurar e coloque seu usuário da Twitch.")
        else:
            open_twitch_login()
            self.msg.config(text="Siga as instruções na janela preta que abriu.")

    def on_update(self):
        if not messagebox.askyesno(
            "Atualizar",
            "Baixar a versão mais nova do GitHub?\n\nOs miners param durante a atualização. "
            "Sua configuração e o login da Twitch são mantidos.",
            parent=self,
        ):
            return
        stop_guard()  # o vigia não pode reabrir os miners no meio da atualização
        subprocess.Popen(["cmd", "/c", str(REPO / "atualizar.bat")], cwd=REPO,
                         creationflags=subprocess.CREATE_NEW_CONSOLE)
        self.msg.config(text="Atualizando na janela preta. Quando terminar, feche e abra este app de novo.")

    def on_config(self):
        ConfigWindow(self)

    def apply_config(self, names, msg):
        """Reinicia só os miners cuja configuração mudou, para os canais novos já entrarem."""
        self.msg.config(text=msg + " Aplicando…")

        def work():
            pids = running_pids()
            for name in names:
                stop_pids(pids[name])
            threading.Event().wait(2)
            for name in names:
                if ready(name):
                    start_miner(name)

        restarted = [n for n in names if ready(n)]
        self.run_bg(work, msg + (f" {' e '.join(restarted)} reiniciado(s) com a lista nova." if restarted else ""))

    def refresh(self, schedule=True):
        def task():
            pids = running_pids()
            guard = guard_running()
            self.after(0, lambda: self._show(pids, guard))

        threading.Thread(target=task, daemon=True).start()
        if schedule:
            self.after(5000, self.refresh)

    def _show(self, pids, guard):
        self.guard_lbl.config(
            text="Vigia ligado: reinicia sozinho um miner que parar ou travar." if guard
            else "Vigia desligado: ele liga ao clicar em Iniciar.",
            fg=GREEN if guard else MUTED,
        )
        for name, lbl in self.status.items():
            if pids[name]:
                lbl.config(text="● rodando", fg=GREEN)
            elif not installed(name):
                lbl.config(text="não instalado", fg=MUTED)
            elif not configured(name):
                lbl.config(text="falta configurar", fg=AMBER)
            elif not ready(name):
                lbl.config(text="falta o login", fg=AMBER)
            else:
                lbl.config(text="● parado", fg=RED)


class ConfigWindow(tk.Toplevel):
    """Preenche config.json (Kick) e config_twitch.json (Twitch) sem editar arquivos à mão."""

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("Configurar")
        self.configure(bg=BG, padx=20, pady=16)
        self.resizable(False, False)
        self.transient(app)
        self.grab_set()

        token, kick_channels = kick_settings()
        user, twitch_channels = twitch_settings()

        self._title("Kick")
        self._hint("Token da sua conta (o README explica como pegar). Ele fica só neste PC.")
        self.token = self._entry(token, secret=True)
        self.show = tk.BooleanVar()
        tk.Checkbutton(self, text="mostrar token", variable=self.show, bg=BG, fg=MUTED,
                       selectcolor=CARD, activebackground=BG, activeforeground=TEXT,
                       command=lambda: self.token.config(show="" if self.show.get() else "•")
                       ).pack(anchor="w")
        self._hint("Canais da Kick, um por linha (pode colar o link do canal):")
        self.kick_channels = self._text(kick_channels)

        self._title("Twitch")
        self._hint("Seu usuário da Twitch (sem senha: o login é pelo botão Login da Twitch).")
        self.user = self._entry(user)
        self._hint("Canais da Twitch, um por linha. A ordem é a prioridade:")
        self.twitch_channels = self._text(twitch_channels)
        if not installed("Twitch"):
            self._hint("O miner da Twitch não está instalado; rode o instalar.bat para usar.")

        btns = tk.Frame(self, bg=BG)
        btns.pack(fill="x", pady=(14, 0))
        app._button(btns, "Salvar", GREEN, "#000", self.save).pack(
            side="left", expand=True, fill="x", padx=(0, 4))
        app._button(btns, "Cancelar", "#2a2f2c", TEXT, self.destroy).pack(
            side="left", expand=True, fill="x", padx=(4, 0))

    def _title(self, text):
        tk.Label(self, text=text, bg=BG, fg=TEXT, font=("Segoe UI", 12, "bold")).pack(
            anchor="w", pady=(8, 2))

    def _hint(self, text):
        tk.Label(self, text=text, bg=BG, fg=MUTED, font=("Segoe UI", 9), wraplength=340,
                 justify="left").pack(anchor="w", pady=(4, 2))

    def _entry(self, value, secret=False):
        e = tk.Entry(self, bg=CARD, fg=TEXT, insertbackground=TEXT, relief="flat",
                     font=("Segoe UI", 10), width=44, show="•" if secret else "")
        e.insert(0, value)
        e.pack(fill="x", ipady=4)
        return e

    def _text(self, lines):
        t = tk.Text(self, bg=CARD, fg=TEXT, insertbackground=TEXT, relief="flat",
                    font=("Segoe UI", 10), width=44, height=6)
        t.insert("1.0", "\n".join(lines))
        t.pack(fill="x")
        return t

    def save(self):
        token = clean_token(self.token.get())
        kick_channels, bad_kick = clean_channels(self.kick_channels.get("1.0", "end"))
        user = self.user.get().strip().lstrip("@").lower()
        twitch_channels, bad_twitch = clean_channels(self.twitch_channels.get("1.0", "end"))

        problems = []
        if bad_kick or bad_twitch:
            problems.append("Nomes de canal inválidos: " + ", ".join(bad_kick + bad_twitch))
        if token and not re.fullmatch(r"\d+\|\S+", token):
            problems.append("O token da Kick parece errado: ele tem o formato número|letras.")
        if token and not kick_channels:
            problems.append("Coloque pelo menos um canal da Kick.")
        if user and not re.fullmatch(r"[a-z0-9_]{3,25}", user):
            problems.append("Usuário da Twitch inválido.")
        if user and not twitch_channels:
            problems.append("Coloque pelo menos um canal da Twitch.")
        if user and not installed("Twitch"):
            problems.append("O miner da Twitch não está instalado. Rode o instalar.bat.")
        if not token and not user:
            problems.append("Preencha a Kick, a Twitch ou as duas.")
        if problems:
            messagebox.showerror("Configurar", "\n\n".join(problems), parent=self)
            return

        old = {"Kick": kick_settings(), "Twitch": twitch_settings()}
        try:
            if token:
                save_kick(token, kick_channels)
            if user:
                save_twitch(user, twitch_channels)
        except (OSError, ValueError) as e:
            messagebox.showerror("Configurar", f"Não foi possível salvar: {e}", parent=self)
            return

        new = {"Kick": kick_settings(), "Twitch": twitch_settings()}
        changed = [name for name in MINERS if new[name] != old[name] and new[name][0]]
        added = [f"{c} ({name})" for name in changed for c in new[name][1] if c not in old[name][1]]
        self.destroy()
        if not changed:
            self.app.msg.config(text="Nada mudou na configuração.")
            return
        msg = "Salvo" + (f": {', '.join(added)} adicionado(s)" if added else "") + "."
        if "Twitch" in changed and not twitch_logged_in():
            msg += " Clique em Login da Twitch para minerar a Twitch."
        self.app.apply_config(changed, msg)


if __name__ == "__main__":
    if "--guardiao" in sys.argv:
        run_guard()
        sys.exit()
    # Sem isto a barra de tarefas agrupa a janela sob o ícone do pythonw
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("miners.kick.twitch")
    App().mainloop()
