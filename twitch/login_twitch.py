# -*- coding: utf-8 -*-
# Faz só o login da Twitch (código em twitch.tv/activate) e salva cookies/<usuario>.pkl.
# Aberto pelo botão "Login da Twitch" do app de controle, numa janela de console visível.
# Usa as classes do Twitch Channel Points Miner v2 (GPL-3.0); este arquivo também é GPL-3.0.

import json
import logging
import os
import webbrowser
from pathlib import Path

from TwitchChannelPointsMiner.classes.Twitch import Twitch
from TwitchChannelPointsMiner.utils import get_user_agent

# O miner mostra o código pelo logging
logging.basicConfig(level=logging.INFO, format="%(message)s")

username = json.loads(Path("config_twitch.json").read_text(encoding="utf-8"))["username"]
twitch = Twitch(username, get_user_agent("CHROME"))
if os.path.isfile(twitch.cookies_file):
    print(f"\nVocê já está logado como {username}.")
    print(f"Para trocar de conta, apague {twitch.cookies_file} e faça o login de novo.")
else:
    print(f"\nLogin da Twitch para: {username}")
    print("Vai abrir twitch.tv/activate no navegador. Digite lá o código que aparecer abaixo.\n")
    webbrowser.open("https://www.twitch.tv/activate")
    twitch.login()
    if os.path.isfile(twitch.cookies_file):
        print("\nLogin feito! Pode fechar esta janela e clicar em Iniciar.")
    else:
        print("\nO login não foi concluído. Feche esta janela e tente de novo.")
input("\nAperte Enter para fechar...")
