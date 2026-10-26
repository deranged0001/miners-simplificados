"""Recompensas de pontos de canal da Kick: listar e resgatar.

Usa as mesmas rotas do site da Kick (API interna v2, não documentada):
  GET  /api/v2/channels/<canal>/rewards
  POST /api/v2/channels/<canal>/rewards/<id>/redeem  {"transaction_id": ULID, "message": ""}
"""

import json
import os
import threading
import time

from utils.get_points_amount import PointsAmount

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def new_ulid() -> str:
    """ULID como o site gera: 10 caracteres de tempo (ms) + 16 aleatórios.
    A Kick usa isto como transaction_id, para um mesmo clique não ser cobrado duas vezes."""
    ms = int(time.time() * 1000)
    head = ""
    for _ in range(10):
        ms, r = divmod(ms, 32)
        head = _CROCKFORD[r] + head
    tail = "".join(_CROCKFORD[b % 32] for b in os.urandom(16))
    return head + tail


class RedeemError(Exception):
    pass


class ChannelRewards:
    """Uma por conta. Chamada pela thread do painel; o lock serializa os pedidos
    (a sessão do curl_cffi não é segura entre threads, e evita dois resgates ao mesmo tempo)."""

    def __init__(self, token: str, proxy: str = None):
        self.token = token
        self.client = PointsAmount(proxy=proxy)
        self.lock = threading.Lock()

    def _prepare(self, channel: str):
        self.client._ensure_session()
        self.client.session.headers["Authorization"] = f"Bearer {self.token}"
        self.client.session.headers["Referer"] = f"https://kick.com/{channel}"

    def _json(self, resp) -> dict:
        try:
            return json.loads(resp.content.decode("utf-8", errors="ignore"))
        except ValueError:
            return {}

    def _list(self, channel: str) -> list:
        resp = self.client.session.get(
            f"https://kick.com/api/v2/channels/{channel}/rewards",
            params={"is_enabled": "true"}, timeout=15,
        )
        if resp.status_code != 200:
            raise RedeemError(f"a Kick respondeu {resp.status_code} ao listar as recompensas")
        return self._json(resp).get("data") or []

    def list(self, channel: str) -> dict:
        with self.lock:
            self._prepare(channel)
            rewards = self._list(channel)
            points = self.client.get_amount(channel, self.token)
        return {
            "points": points,
            "rewards": [
                {
                    "id": r.get("id"),
                    "title": r.get("title", ""),
                    "description": r.get("description", ""),
                    "cost": r.get("cost", 0),
                    "color": r.get("background_color") or "",
                    "paused": bool(r.get("is_paused")),
                    # Recompensas que pedem texto não são suportadas pelo painel
                    "needs_input": bool(r.get("is_user_input_required")),
                }
                for r in rewards
            ],
        }

    def redeem(self, channel: str, reward_id: str) -> dict:
        with self.lock:
            self._prepare(channel)
            # Confere de novo na Kick: o id tem que existir, estar ativo e caber no saldo
            reward = next((r for r in self._list(channel) if r.get("id") == reward_id), None)
            if reward is None:
                raise RedeemError("essa recompensa não existe mais neste canal")
            if reward.get("is_paused"):
                raise RedeemError("essa recompensa está pausada")
            if reward.get("is_user_input_required"):
                raise RedeemError("essa recompensa pede um texto; resgate pelo site da Kick")
            points = self.client.get_amount(channel, self.token)
            if points is not None and points < reward.get("cost", 0):
                raise RedeemError(f"saldo insuficiente: {points} de {reward.get('cost')} pontos")

            resp = self.client.session.post(
                f"https://kick.com/api/v2/channels/{channel}/rewards/{reward_id}/redeem",
                json={"transaction_id": new_ulid(), "message": ""},
                timeout=15,
            )
            if resp.status_code not in (200, 201):
                msg = self._json(resp).get("message") or ""
                raise RedeemError(f"a Kick recusou o resgate ({resp.status_code}) {msg}".strip())
            new_points = self.client.get_amount(channel, self.token)
        return {"title": reward.get("title", ""), "cost": reward.get("cost", 0), "points": new_points}
