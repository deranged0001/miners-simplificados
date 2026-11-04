# -*- coding: utf-8 -*-
# Configuração simplificada do Twitch Channel Points Miner v2:
# só assiste e coleta pontos, sem apostas.
#
# Baseado no example.py de https://github.com/rdavydov/Twitch-Channel-Points-Miner-v2
# Este arquivo é distribuído sob a GPL-3.0, a mesma licença do projeto original.
#
# O instalar.ps1 copia este arquivo para twitch/Twitch-Channel-Points-Miner-v2/run.py.
# Usuário e canais ficam no config_twitch.json ao lado, preenchido pelo botão "Configurar".

import copy
import json
import logging
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from TwitchChannelPointsMiner import TwitchChannelPointsMiner
from TwitchChannelPointsMiner.classes.Chat import ChatPresence
from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer, StreamerSettings
from TwitchChannelPointsMiner.constants import GQLOperations

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


# Recompensas de pontos de canal, usadas pelo painel da Kick (ele repassa para a porta abaixo)
BRIDGE_PORT = 5001
REDEEM_MUTATION = (
    "mutation RedeemCustomReward($input: RedeemCommunityPointsCustomRewardInput!) {"
    " redeemCommunityPointsCustomReward(input: $input) { error { code } redemption { id } } }"
)


class RedeemError(Exception):
    pass


def find_streamer(miner, channel):
    s = next((s for s in miner.streamers if s.username == channel), None)
    if s is None:
        raise RedeemError("canal desconhecido")
    return s


def load_rewards(miner, channel):
    """(id do canal, saldo, recompensas ativas), direto da Twitch."""
    data = copy.deepcopy(GQLOperations.ChannelPointsContext)
    data["variables"] = {"channelLogin": channel}
    community = (miner.twitch.post_gql_request(data).get("data") or {}).get("community")
    if not community:
        raise RedeemError("a Twitch não respondeu")
    ch = community["channel"]
    rewards = (ch.get("communityPointsSettings") or {}).get("customRewards") or []
    return ch["id"], ch["self"]["communityPoints"]["balance"], [r for r in rewards if r.get("isEnabled")]


def list_rewards(miner, channel):
    find_streamer(miner, channel)
    _, points, rewards = load_rewards(miner, channel)
    return {
        "points": points,
        "rewards": sorted((
            {
                "id": r["id"],
                "title": r["title"],
                "description": r.get("prompt") or "",
                "cost": r["cost"],
                "color": r.get("backgroundColor") or "",
                "paused": bool(r.get("isPaused")) or not r.get("isInStock", True),
                "needs_input": bool(r.get("isUserInputRequired")),
            }
            for r in rewards
        ), key=lambda r: r["cost"]),
    }


def redeem_reward(miner, channel, reward_id):
    streamer = find_streamer(miner, channel)
    # Confere de novo na Twitch: o id tem que existir, estar ativo e caber no saldo
    channel_id, points, rewards = load_rewards(miner, channel)
    reward = next((r for r in rewards if r["id"] == reward_id), None)
    if reward is None:
        raise RedeemError("essa recompensa não existe mais neste canal")
    if reward.get("isPaused") or not reward.get("isInStock", True):
        raise RedeemError("essa recompensa está pausada")
    if reward.get("isUserInputRequired"):
        raise RedeemError("essa recompensa pede um texto; resgate pelo site da Twitch")
    if points < reward["cost"]:
        raise RedeemError(f"saldo insuficiente: {points} de {reward['cost']} pontos")

    answer = miner.twitch.post_gql_request({
        "operationName": "RedeemCustomReward",
        "query": REDEEM_MUTATION,
        "variables": {"input": {
            "channelID": channel_id, "cost": reward["cost"], "prompt": reward.get("prompt"), "rewardID": reward_id,
            "title": reward["title"], "transactionID": uuid.uuid4().hex,
        }},
    })
    result = (answer.get("data") or {}).get("redeemCommunityPointsCustomReward")
    if not result:
        raise RedeemError("sem resposta da Twitch; confira o saldo antes de tentar de novo")
    if result.get("error"):
        raise RedeemError(f"a Twitch recusou o resgate ({result['error'].get('code')})")
    streamer.channel_points = points - reward["cost"]
    return {"title": reward["title"], "cost": reward["cost"], "points": streamer.channel_points}


def is_watching(streamer):
    """A Twitch só conta 2 canais por vez; o miner marca a hora de cada minuto enviado."""
    # shortcut: lê campo privado do Stream; se o miner mudar, fica sempre False
    last = getattr(streamer.stream, "_Stream__minute_watched_timestamp", 0)
    return bool(streamer.is_online and last and time.time() - last < 150)


def bridge_answer(miner, method, path, query, body):
    if method == "GET" and path == "/status":
        return 200, {"streamers": [
            {"name": s.username, "points": s.channel_points, "online": bool(s.is_online),
             "watching": is_watching(s), "chat": bool(s.is_online and chat_ok(s))}
            for s in list(miner.streamers)
        ]}
    if method == "GET" and path == "/rewards":
        return 200, list_rewards(miner, query.get("channel", [""])[0])
    if method == "POST" and path == "/redeem":
        channel, reward_id = body.get("channel"), body.get("reward_id")
        if not (isinstance(channel, str) and isinstance(reward_id, str) and reward_id):
            return 400, {"error": "channel e reward_id obrigatórios"}
        return 200, redeem_reward(miner, channel, reward_id)
    return 404, {"error": "não encontrado"}


class BridgeHandler(BaseHTTPRequestHandler):
    def _handle(self):
        # Só o painel local: navegador sempre manda Origin em POST, e site externo chegaria com outro Host
        if self.headers.get("Host") != f"127.0.0.1:{BRIDGE_PORT}" or self.headers.get("Origin"):
            return self._send(403, {"error": "origem não permitida"})
        url = urlparse(self.path)
        try:
            body = {}
            if self.command == "POST":
                if self.headers.get("Content-Type") != "application/json":
                    return self._send(415, {"error": "JSON obrigatório"})
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            self._send(*bridge_answer(self.server.miner, self.command, url.path, parse_qs(url.query), body))
        except RedeemError as e:
            self._send(400, {"error": str(e)})
        except Exception as e:
            logging.getLogger("bridge").error(f"Falha na ponte do painel: {e}")
            self._send(502, {"error": "falha ao falar com a Twitch"})

    do_GET = do_POST = _handle

    def _send(self, status, data):
        raw = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *args):
        pass


bridge = ThreadingHTTPServer(("127.0.0.1", BRIDGE_PORT), BridgeHandler)
bridge.miner = twitch_miner
threading.Thread(target=bridge.serve_forever, daemon=True).start()
threading.Thread(target=chat_watchdog, args=(twitch_miner,), daemon=True).start()

twitch_miner.mine(
    # Nome do canal como aparece em twitch.tv/<nome>. A ordem é a prioridade.
    [Streamer(name) for name in config["streamers"]],
    followers=False,                            # True minera também todos os canais que você segue
)
