# Janela simples para iniciar e parar os miners da Kick e da Twitch em segundo plano.
# Roda com pythonw (sem console). Os miners continuam rodando mesmo se esta janela for fechada.

import ctypes
import subprocess
import threading
import urllib.request
import webbrowser
import tkinter as tk
from pathlib import Path

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


def painel_up():
    try:
        urllib.request.urlopen(PAINEL + "/api/data", timeout=2)
        return True
    except OSError:
        return False


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

        btns = tk.Frame(self, bg=BG)
        btns.pack(fill="x", pady=(14, 0))
        self.btn_start = self._button(btns, "▶  Iniciar", GREEN, "#000", self.on_start)
        self.btn_start.pack(side="left", expand=True, fill="x", padx=(0, 4))
        self.btn_stop = self._button(btns, "■  Parar", "#2a2f2c", TEXT, self.on_stop)
        self.btn_stop.pack(side="left", expand=True, fill="x", padx=(4, 0))

        self.btn_panel = self._button(self, "Abrir painel da Kick", CARD, TEXT,
                                      lambda: webbrowser.open(PAINEL))
        self.btn_panel.pack(fill="x", pady=(8, 0))

        self.msg = tk.Label(self, text="", bg=BG, fg=MUTED, font=("Segoe UI", 9),
                            wraplength=280, justify="left")
        self.msg.pack(anchor="w", pady=(10, 0))

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
            for name in MINERS:
                if installed(name) and not pids[name]:
                    start_miner(name)
            # O painel sobe em ~1 s; espera até 20 s antes de abrir o navegador
            for _ in range(20):
                if painel_up():
                    webbrowser.open(PAINEL)
                    return
                threading.Event().wait(1)
            raise RuntimeError("o painel da Kick não respondeu. Veja miner-log.txt na pasta da Kick.")

        self.run_bg(work, "Miners rodando. O painel abriu no navegador.")

    def on_stop(self):
        self.msg.config(text="Parando…")

        def work():
            for pids in running_pids().values():
                stop_pids(pids)

        self.run_bg(work, "Miners parados.")

    def refresh(self, schedule=True):
        def task():
            pids = running_pids()
            self.after(0, lambda: self._show(pids))

        threading.Thread(target=task, daemon=True).start()
        if schedule:
            self.after(5000, self.refresh)

    def _show(self, pids):
        for name, lbl in self.status.items():
            if pids[name]:
                lbl.config(text="● rodando", fg=GREEN)
            elif not installed(name):
                lbl.config(text="não instalado", fg=MUTED)
            else:
                lbl.config(text="● parado", fg=RED)


if __name__ == "__main__":
    # Sem isto a barra de tarefas agrupa a janela sob o ícone do pythonw
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("miners.kick.twitch")
    App().mainloop()
