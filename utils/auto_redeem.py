"""Resgate automático em rodízio: a cada rodada resgata a mesma recompensa em alguns canais,
sempre começando pelos que foram usados há mais tempo. Liga em "AutoRedeem" no config.json."""

import json
import threading
import time
from pathlib import Path

from loguru import logger

from utils.channel_rewards import RedeemError

STATE_FILE = Path(__file__).resolve().parent.parent / "auto_resgate.json"
CONFIG_FILE = STATE_FILE.with_name("config.json")
RETRY_SECONDS = 10 * 60


class AutoRedeem:
    def __init__(self, manager, config: dict, state_file: Path = STATE_FILE):
        self.manager = manager
        self.enabled = bool(config.get("enabled", False))
        self.display_title = config["title"]
        self.title = config["title"].strip().casefold()
        self.min_points = config.get("min_points", 300)
        self.per_round = config.get("channels_per_round", 3)
        self.seconds_each = config.get("hours_per_redeem", 1) * 3600
        self.state_file = state_file
        self.state = self._load()

    def _load(self) -> dict:
        try:
            state = json.loads(self.state_file.read_text(encoding="utf-8"))
            return {"next_at": float(state["next_at"]), "last": dict(state["last"])}
        except (OSError, ValueError, KeyError, TypeError):
            return {"next_at": 0.0, "last": {}}

    def set_enabled(self, enabled: bool):
        """Vale na hora e fica gravado no config.json para o próximo início."""
        config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        config["AutoRedeem"]["enabled"] = enabled
        tmp = CONFIG_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(CONFIG_FILE)
        self.enabled = enabled
        logger.info(f"Resgate automático {'ligado' if enabled else 'desligado'}")

    def status(self) -> dict:
        return {"enabled": self.enabled, "title": self.display_title, "next_at": self.state["next_at"]}

    def _save(self):
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, indent=2), encoding="utf-8")
        tmp.replace(self.state_file)

    def _redeem_in(self, channel: str) -> bool:
        info = self.manager.list_rewards(channel)
        reward = next((r for r in info["rewards"] if r["title"].strip().casefold() == self.title), None)
        if reward is None or reward["paused"] or reward["needs_input"]:
            return False
        points = info["points"]
        if points is None or points < max(self.min_points, reward["cost"]):
            return False
        self.manager.redeem_reward(channel, reward["id"])
        logger.success(f"Resgate automático: {reward['title']} em {channel} ({points} pontos antes)")
        return True

    def run_round(self, now: float) -> int:
        channels = self.manager.get_all_streamers_flat()
        # sorted é estável: empate (nunca usados) segue a ordem da lista de canais
        queue = sorted(channels, key=lambda c: self.state["last"].get(c, 0))
        done = 0
        for channel in queue:
            if done >= self.per_round or not self.enabled:
                break
            try:
                redeemed = self._redeem_in(channel)
            except RedeemError as e:
                logger.warning(f"Resgate automático: {channel}: {e}")
                redeemed = False
            if redeemed:
                done += 1
                self.state["last"][channel] = now
                # Salva a cada resgate: reiniciar no meio da rodada não gasta pontos a mais
                self.state["next_at"] = now + done * self.seconds_each
                self._save()
            time.sleep(2)
        if not self.enabled:
            return done
        if not done:
            self.state["next_at"] = now + RETRY_SECONDS
            self._save()
            logger.warning("Resgate automático: nenhum canal disponível; tentando de novo em 10 min")
        elif done < self.per_round:
            logger.warning(f"Resgate automático: só {done} de {self.per_round} canais disponíveis")
        return done

    def loop(self):
        while True:
            try:
                if self.enabled and time.time() >= self.state["next_at"]:
                    self.run_round(time.time())
            except Exception as e:
                logger.error(f"Resgate automático falhou nesta rodada: {e}")
                self.state["next_at"] = time.time() + RETRY_SECONDS
            time.sleep(30)

    def start(self):
        threading.Thread(target=self.loop, daemon=True, name="auto-redeem").start()
