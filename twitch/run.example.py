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
import sys
from pathlib import Path

from TwitchChannelPointsMiner import TwitchChannelPointsMiner
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

twitch_miner.mine(
    # Nome do canal como aparece em twitch.tv/<nome>. A ordem é a prioridade.
    [Streamer(name) for name in config["streamers"]],
    followers=False,                            # True minera também todos os canais que você segue
)
