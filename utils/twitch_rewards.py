"""Recompensas de pontos de canal da Twitch: listar e resgatar várias vezes seguidas.

Reaproveita o login do miner da Twitch (twitch/Twitch-Channel-Points-Miner-v2/cookies/<usuário>.pkl)
e fala com a mesma API GraphQL que ele usa (gql.twitch.tv, não documentada):
  ChannelPointsContext          saldo e recompensas do canal (consulta salva, a mesma do miner)
  RedeemCustomReward            resgata uma recompensa (mutação escrita por extenso)
"""

import json
import os
import pickle
import threading
import time
import urllib.error
import urllib.request
import uuid

from utils.channel_rewards import RedeemError

TWITCH_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "twitch", "Twitch-Channel-Points-Miner-v2")
GQL_URL = "https://gql.twitch.tv/gql"
CLIENT_ID = "ue6666qo983tsx6so1t0vnawi233wa"  # o mesmo do miner (app de TV)
USER_AGENT = ("Mozilla/5.0 (Linux; Android 7.1; Smart Box C1) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36")
CHANNEL_POINTS_CONTEXT = "7fe050e3761eb2cf258d70ee1a21cbd76fa8cf3d7e7b12fc437e7029d446b5e3"
REDEEM_MUTATION = (
    "mutation RedeemCustomReward($input: RedeemCommunityPointsCustomRewardInput!) {"
    " redeemCommunityPointsCustomReward(input: $input) { error { code } redemption { id } } }"
)
MAX_COUNT = 50       # teto de resgates por clique
REDEEM_GAP = 0.6     # segundos entre um resgate e o próximo

ERRORS = {
    "NOT_ENOUGH_POINTS": "saldo insuficiente",
    "GLOBAL_COOLDOWN": "a recompensa está em tempo de espera",
    "MAX_PER_STREAM": "a recompensa chegou ao limite desta live",
    "MAX_PER_USER_PER_STREAM": "você chegou ao limite desta recompensa nesta live",
    "OUT_OF_STOCK": "a recompensa esgotou",
    "PROPERTIES_MISMATCH": "o canal mudou a recompensa; abra a lista de novo",
    "NOT_FOUND": "essa recompensa não existe mais",
    "DISABLED": "a recompensa está desativada",
    "STREAM_NOT_LIVE": "a live não está no ar",
    "FORBIDDEN": "a Twitch não deixou resgatar esta recompensa",
}


class _NoClasses(pickle.Unpickler):
    # O arquivo de login é só uma lista de dicionários; nada de carregar objetos de fora
    def find_class(self, module, name):
        raise pickle.UnpicklingError("arquivo de login inesperado")


class TwitchRewards:
    """Chamada pela thread do painel; o lock evita dois resgates em lote ao mesmo tempo."""

    def __init__(self):
        self.lock = threading.Lock()
        self.device_id = uuid.uuid4().hex

    def _config(self) -> dict:
        try:
            with open(os.path.join(TWITCH_DIR, "config_twitch.json"), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            raise RedeemError("a Twitch não está configurada; use o botão Configurar")

    def _token(self) -> str:
        user = self._config().get("username", "")
        try:
            with open(os.path.join(TWITCH_DIR, "cookies", f"{user}.pkl"), "rb") as f:
                cookies = _NoClasses(f).load()
        except (OSError, pickle.UnpicklingError, EOFError):
            raise RedeemError("falta o login da Twitch; clique em Login da Twitch")
        token = next((c.get("value") for c in cookies
                      if isinstance(c, dict) and c.get("name") == "auth-token"), None)
        if not token:
            raise RedeemError("falta o login da Twitch; clique em Login da Twitch")
        return token

    def channels(self) -> list:
        return [c for c in self._config().get("streamers", []) if isinstance(c, str)]

    def _gql(self, body: dict) -> dict:
        req = urllib.request.Request(GQL_URL, data=json.dumps(body).encode(), method="POST", headers={
            "Authorization": f"OAuth {self._token()}",
            "Client-Id": CLIENT_ID,
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
            "X-Device-Id": self.device_id,
        })
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise RedeemError("o login da Twitch venceu; clique em Login da Twitch")
            raise RedeemError(f"a Twitch respondeu {e.code}")
        except (urllib.error.URLError, ValueError):
            raise RedeemError("não foi possível falar com a Twitch")
        if data.get("errors"):
            msg = data["errors"][0].get("message", "")
            if "unauthenticated" in msg.lower():
                raise RedeemError("o login da Twitch venceu; clique em Login da Twitch")
            raise RedeemError(f"a Twitch recusou o pedido ({msg})")
        return data.get("data") or {}

    def _context(self, channel: str):
        data = self._gql({
            "operationName": "ChannelPointsContext",
            "variables": {"channelLogin": channel},
            "extensions": {"persistedQuery": {"version": 1, "sha256Hash": CHANNEL_POINTS_CONTEXT}},
        })
        chan = (data.get("community") or {}).get("channel")
        if not chan:
            raise RedeemError("canal não encontrado na Twitch")
        points = ((chan.get("self") or {}).get("communityPoints") or {}).get("balance")
        rewards = (chan.get("communityPointsSettings") or {}).get("customRewards") or []
        return chan["id"], points, rewards

    @staticmethod
    def _limit(r: dict) -> int:
        """Quantas vezes dá para resgatar seguido, pelos limites que a Twitch mostra.
        O limite por pessoa conta resgates que a Twitch não informa aqui; se estourar, o lote para."""
        limit = MAX_COUNT
        per_stream = r.get("maxPerStreamSetting") or {}
        if per_stream.get("isEnabled"):
            limit = min(limit, per_stream.get("maxPerStream", 0) - (r.get("redemptionsRedeemedCurrentStream") or 0))
        per_user = r.get("maxPerUserPerStreamSetting") or {}
        if per_user.get("isEnabled"):
            limit = min(limit, per_user.get("maxPerUserPerStream", 0))
        if (r.get("globalCooldownSetting") or {}).get("isEnabled"):
            limit = min(limit, 1)  # com tempo de espera, só um por vez
        if r.get("cooldownExpiresAt"):
            limit = 0
        return max(limit, 0)

    def list(self, channel: str) -> dict:
        with self.lock:
            _, points, rewards = self._context(channel)
        return {
            "points": points,
            "rewards": [
                {
                    "id": r.get("id"),
                    "title": r.get("title", ""),
                    "description": r.get("prompt") or "",
                    "cost": r.get("cost", 0),
                    "color": r.get("backgroundColor") or "",
                    "paused": bool(r.get("isPaused")) or not r.get("isInStock", True),
                    "needs_input": bool(r.get("isUserInputRequired")),
                    "max_count": self._limit(r),
                    "cooldown": bool(r.get("cooldownExpiresAt")),
                }
                for r in rewards
                if r.get("isEnabled") and not r.get("isSubOnly")
            ],
        }

    def redeem(self, channel: str, reward_id: str, count: int) -> dict:
        with self.lock:
            # Confere de novo na Twitch: a recompensa tem que estar ativa e o lote inteiro caber no saldo
            channel_id, points, rewards = self._context(channel)
            reward = next((r for r in rewards if r.get("id") == reward_id), None)
            if reward is None or not reward.get("isEnabled"):
                raise RedeemError("essa recompensa não está ativa agora")
            if reward.get("isPaused") or not reward.get("isInStock", True):
                raise RedeemError("essa recompensa está pausada ou esgotada")
            if reward.get("isUserInputRequired"):
                raise RedeemError("essa recompensa pede um texto; resgate pelo site da Twitch")
            cost = reward.get("cost", 0)
            if points is None:
                raise RedeemError("não foi possível ler o saldo")
            if points < cost * count:
                raise RedeemError(f"saldo insuficiente: {points} de {cost * count} pontos")
            if count > self._limit(reward):
                raise RedeemError(f"esta recompensa permite no máximo {self._limit(reward)} agora")

            done, stop = 0, None
            for i in range(count):
                if i:
                    time.sleep(REDEEM_GAP)
                try:
                    data = self._gql({
                        "operationName": "RedeemCustomReward",
                        "query": REDEEM_MUTATION,
                        "variables": {"input": {
                            "channelID": channel_id, "cost": cost, "prompt": None,
                            "rewardID": reward_id, "title": reward.get("title", ""),
                            # Um id por resgate: a Twitch não cobra duas vezes o mesmo
                            "transactionID": uuid.uuid4().hex,
                        }},
                    })
                except RedeemError as e:
                    stop = str(e)
                    break
                result = data.get("redeemCommunityPointsCustomReward") or {}
                code = (result.get("error") or {}).get("code")
                if code or not result.get("redemption"):
                    stop = ERRORS.get(code, f"a Twitch recusou ({code or 'sem resposta'})")
                    break
                done += 1
            try:
                _, points, _ = self._context(channel)
            except RedeemError:
                pass
        return {"title": reward.get("title", ""), "cost": cost, "done": done,
                "requested": count, "points": points, "stopped": stop}
