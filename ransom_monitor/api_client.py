"""Cliente HTTP para ransomware.live PRO.

Diseñado para ser "discreto": una sola petición a la vez (nunca en paralelo),
espera aleatoria (jitter) entre peticiones consecutivas, y backoff exponencial
con jitter ante HTTP 429/5xx o errores de red, respetando Retry-After cuando
el servidor lo envía.
"""

from __future__ import annotations

import logging
import random
import time
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)


class RansomwareLiveError(Exception):
    """Error irrecuperable al hablar con la API de ransomware.live."""


class RansomwareLiveClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        timeout: int = 20,
        user_agent: str = "LatamRansomMonitor/1.0",
        min_delay: float = 3.0,
        max_delay: float = 8.0,
        max_retries: int = 5,
        backoff_base: float = 5.0,
        backoff_max: float = 120.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.backoff_max = backoff_max
        self._last_request_at: Optional[float] = None

        self.session = requests.Session()
        self.session.headers.update(
            {
                "X-Api-Key": api_key,
                "User-Agent": user_agent,
                "Accept": "application/json",
            }
        )

    # -- throttling ---------------------------------------------------

    def _throttle(self) -> None:
        """Garantiza al menos un delay aleatorio [min_delay, max_delay] entre peticiones."""
        if self._last_request_at is not None:
            elapsed = time.monotonic() - self._last_request_at
            wait = random.uniform(self.min_delay, self.max_delay) - elapsed
            if wait > 0:
                time.sleep(wait)

    def _backoff_delay(self, attempt: int) -> float:
        delay = min(self.backoff_max, self.backoff_base * (2 ** (attempt - 1)))
        return delay * random.uniform(0.8, 1.2)

    # -- core request ---------------------------------------------------

    def get(self, path: str, params: Optional[dict] = None) -> Any:
        url = f"{self.base_url}{path}"
        attempt = 0
        while True:
            self._throttle()
            self._last_request_at = time.monotonic()
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
            except requests.RequestException as exc:
                attempt += 1
                if attempt > self.max_retries:
                    raise RansomwareLiveError(
                        f"GET {path} falló tras {attempt} intentos: {exc}"
                    ) from exc
                sleep_for = self._backoff_delay(attempt)
                logger.warning(
                    "Error de red en %s (intento %d/%d): %s — reintentando en %.1fs",
                    path, attempt, self.max_retries, exc, sleep_for,
                )
                time.sleep(sleep_for)
                continue

            if resp.status_code == 200:
                try:
                    return resp.json()
                except ValueError as exc:
                    raise RansomwareLiveError(f"Respuesta no-JSON de {path}: {exc}") from exc

            if resp.status_code == 429 or resp.status_code >= 500:
                attempt += 1
                if attempt > self.max_retries:
                    raise RansomwareLiveError(
                        f"GET {path} falló tras {attempt} intentos: HTTP {resp.status_code}"
                    )
                retry_after = resp.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    sleep_for = float(retry_after)
                else:
                    sleep_for = self._backoff_delay(attempt)
                logger.warning(
                    "HTTP %d en %s (intento %d/%d) — esperando %.1fs",
                    resp.status_code, path, attempt, self.max_retries, sleep_for,
                )
                time.sleep(sleep_for)
                continue

            raise RansomwareLiveError(
                f"GET {path} devolvió HTTP {resp.status_code}: {resp.text[:300]}"
            )

    # -- endpoints ---------------------------------------------------

    def validate_key(self) -> dict:
        return self.get("/validate")

    def recent_victims(self, order: str = "discovered") -> list:
        """Las ~100 víctimas más recientes a nivel global."""
        data = self.get("/victims/recent", params={"order": order})
        return data.get("victims", [])

    def victims_by_country(self, country_code: str) -> list:
        """Todas las víctimas conocidas de un país (ISO 3166-1 alpha-2)."""
        data = self.get("/victims/", params={"country": country_code})
        return data.get("victims", [])

    def group_detail(self, group_name: str) -> dict:
        """Inteligencia del grupo: descripción, TTPs MITRE ATT&CK, CVEs
        explotadas, herramientas, negociaciones/notas de rescate filtradas."""
        return self.get(f"/group/{group_name}")

    def iocs_summary(self) -> dict:
        """Conteo de IOCs por tipo, por grupo — todo en UNA llamada a /iocs
        (no se piden los valores individuales, solo los conteos)."""
        data = self.get("/iocs")
        return {g["group"].lower(): g.get("ioc_types", {}) for g in data.get("groups", [])}

    def yara_summary(self) -> dict:
        """Conteo de reglas YARA por grupo — todo en UNA llamada a /yara."""
        data = self.get("/yara")
        return {g["group"].lower(): g.get("yara_count", 0) for g in data.get("groups", [])}
