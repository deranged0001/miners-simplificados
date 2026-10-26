# -*- coding: utf-8 -*-
# Configuração simplificada do Twitch Channel Points Miner v2:
# só assiste e coleta pontos, sem apostas.
#
# Baseado no example.py de https://github.com/rdavydov/Twitch-Channel-Points-Miner-v2
# Este arquivo é distribuído sob a GPL-3.0, a mesma licença do projeto original.
#
# O instalar.ps1 copia este arquivo para twitch/Twitch-Channel-Points-Miner-v2/run.py.
# Usuário e canais ficam no config_twitch.json ao lado, preenchido pelo botão "Configurar".

import json
import logging
import sys
import threading
import time
from pathlib import Path

from TwitchChannelPointsMiner import TwitchChannelPointsMiner
from TwitchChannelPointsMiner.classes.Chat import ChatPresence
from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer, StreamerSettings

config_file = Path(__file__).with_name("config_twitch.json")
if not config_file.exists():
    sys.exit("Falta o config_twitch.json. Abra o app 'Miners Kick e Twitch' e clique em 'Configurar'.")
config = json.loads(config_file.read_text(encoding="utf-8"))

twitch_miner = TwitchChannelPointsMiner(
    username=config["username"],                # Sem senha: o login é pelo código em twitch.tv/activate
    enable_analytics=False,
    streamer_settings=StreamerSettings(
        make_predictions=False,                 # O padrão é True e aposta seus pontos. Mantenha False.
        community_goals=False,                  # True gastaria pontos em metas da comunidade
        follow_raid=True,
        claim_drops=True,
        claim_moments=True,
        watch_streak=True,
    ),
)


def chat_ok(streamer):
    """Conectado ao chat da Twitch e dentro do canal."""
    t = streamer.irc_chat
    bot = getattr(t, "chat_irc", None)
    if not (t and t.is_alive() and bot):
        return False
    return bot.connection.is_connected() and f"#{streamer.username}" in bot.channels


def chat_watchdog(miner, interval=60):
    """A conexão de chat da Twitch às vezes cai sem aviso e o miner não volta sozinho.
    Jogos que contam quem está no chat deixam de ver você. Isto confere a cada minuto
    e reconecta o chat dos canais ao vivo que caíram."""
    log = logging.getLogger("chat_watchdog")
    strikes = {}
    keepalive = set()
    while True:
        time.sleep(interval)
        try:
            check_chats(miner, log, strikes, keepalive)
        except Exception as e:
            log.error(f"Watchdog do chat falhou nesta rodada: {e}")


def check_chats(miner, log, strikes, keepalive):
    for s in list(miner.streamers):
        if not (s.is_online and s.settings.chat == ChatPresence.ONLINE and s.irc_chat):
            strikes.pop(s.username, None)
            continue
        if chat_ok(s):
            strikes.pop(s.username, None)
            conn = s.irc_chat.chat_irc.connection
            if id(conn) not in keepalive:
                # PING periódico: uma conexão morta sem aviso passa a dar erro e a ser detectada
                conn.set_keepalive(60)
                keepalive.add(id(conn))
            continue
        # Duas checagens seguidas, para não atrapalhar a entrada normal no chat
        strikes[s.username] = strikes.get(s.username, 0) + 1
        if strikes[s.username] >= 2:
            log.warning(f"Chat de {s.username} caiu; reconectando")
            s.leave_chat()
            s.toggle_chat()
            strikes.pop(s.username, None)


threading.Thread(target=chat_watchdog, args=(twitch_miner,), daemon=True).start()

twitch_miner.mine(
    # Nome do canal como aparece em twitch.tv/<nome>. A ordem é a prioridade.
    [Streamer(name) for name in config["streamers"]],
    followers=False,                            # True minera também todos os canais que você segue
)
