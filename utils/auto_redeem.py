"""Resgate automático em rodízio: a cada rodada resgata a mesma recompensa em alguns canais,
sempre começando pelos que foram usados há mais tempo. Liga em "AutoRedeem" no config.json."""

import json
import threading
import time
from pathlib import Path

from loguru import logger

from utils.channel_rewards import RedeemError

STATE_FILE = Path(__file__).resolve().parent.parent / "auto_resgate.json"
RETRY_SECONDS = 10 * 60

_instance = None


class AutoRedeem:
    def __init__(self, manager, config: dict, state_file: Path = STATE_FILE):
        self.manager = manager
        self.display_title = config["title"]
        self.title = config["title"].strip().casefold()
        self.min_points = config.get("min_points", 300)
        # O streamer pode mudar o preço; acima disto o canal é pulado
        self.max_cost = config.get("max_cost", self.min_points)
        self.per_round = config.get("channels_per_round", 3)
        self.seconds_each = config.get("hours_per_redeem", 1) * 3600
        self.state_file = state_file
        self.state = self._load()
        self.enabled = self.state.pop("enabled", bool(config.get("enabled", False)))

    def _load(self) -> dict:
        try:
            state = json.loads(self.state_file.read_text(encoding="utf-8"))
            loaded = {"next_at": float(state["next_at"]), "last": dict(state["last"])}
            if "enabled" in state:
                loaded["enabled"] = bool(state["enabled"])
            return loaded
        except (OSError, ValueError, KeyError, TypeError):
            return {"next_at": 0.0, "last": {}}

    def set_enabled(self, enabled: bool):
        """Vale na hora, mesmo se salvar falhar; o estado guarda para o próximo início."""
        self.enabled = enabled
        self._save()
        logger.info(f"Resgate automático {'ligado' if enabled else 'desligado'}")

    def status(self) -> dict:
        return {"enabled": self.enabled, "title": self.display_title, "next_at": self.state["next_at"]}

    def _save(self):
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps({**self.state, "enabled": self.enabled}, indent=2), encoding="utf-8")
        tmp.replace(self.state_file)

    def _redeem_in(self, channel: str) -> bool:
        info = self.manager.list_rewards(channel)
        reward = next((r for r in info["rewards"] if r["title"].strip().casefold() == self.title), None)
        if reward is None or reward["paused"] or reward["needs_input"]:
            return False
        points = info["points"]
        if points is None or points < max(self.min_points, reward["cost"]):
            return False
        if reward["cost"] > self.max_cost:
            logger.warning(f"Resgate automático: {channel} cobra {reward['cost']}, acima de {self.max_cost}; pulando")
            return False
        try:
            self.manager.redeem_reward(channel, reward["id"])
        except RedeemError:
            raise
        except Exception as e:
            # Sem resposta da Kick o resgate pode ter sido cobrado: conta como feito, para não pagar duas vezes
            logger.warning(f"Resgate automático: {channel}: resultado incerto, contando como resgatado: {e}")
            return True
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
            except Exception as e:
                logger.warning(f"Resgate automático: {channel}: falha ao consultar: {e}")
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
                # Um erro nunca encurta a espera já marcada
                self.state["next_at"] = max(self.state["next_at"], time.time() + RETRY_SECONDS)
            time.sleep(30)

    def start(self):
        threading.Thread(target=self.loop, daemon=True, name="auto-redeem").start()


def start_once(manager, config: dict) -> AutoRedeem:
    """O main() pode rodar de novo no mesmo processo; duas threads resgatariam em dobro."""
    global _instance
    if _instance is None:
        _instance = AutoRedeem(manager, config)
        _instance.start()
    _instance.manager = manager
    return _instance
