"""Caché en disco para la inteligencia de grupo: perfil (/group/<nombre>),
conteo de IOCs (/iocs) y conteo de reglas YARA (/yara).

Varias víctimas suelen compartir el mismo grupo (p. ej. "qilin" aparece en
decenas de víctimas), así que cachear evita pedir lo mismo una y otra vez —
clave para mantenernos discretos con el API. Todo esto cambia poco de un día
a otro, así que una entrada se reutiliza hasta que expira
(group_cache_ttl_hours).

/iocs y /yara devuelven el conteo de TODOS los grupos en una sola llamada
cada uno, así que se cachean aparte (no por grupo) y se combinan con el
perfil de cada grupo al vuelo.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

from ransom_monitor.api_client import RansomwareLiveClient, RansomwareLiveError
from ransom_monitor.state import load_state, save_state

logger = logging.getLogger(__name__)


class GroupIntelCache:
    def __init__(self, client: RansomwareLiveClient, cache_path: Path, ttl_hours: float) -> None:
        self.client = client
        self.cache_path = cache_path
        self.ttl_hours = ttl_hours
        self._cache = load_state(cache_path)
        self._cache.setdefault("groups", {})
        self._cache.setdefault("meta", {})
        self._dirty = False

    def get(self, group_name: Optional[str]) -> Optional[dict]:
        if not group_name:
            return None
        key = group_name.strip().lower()
        if not key:
            return None

        groups_cache = self._cache["groups"]
        entry = groups_cache.get(key)
        if entry and not self._is_stale(entry.get("fetched_at")):
            data = entry.get("data")
        else:
            try:
                data = self.client.group_detail(key)
            except RansomwareLiveError as exc:
                logger.warning("No se pudo obtener perfil del grupo '%s': %s", key, exc)
                data = entry.get("data") if entry else None
            else:
                groups_cache[key] = {
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "data": data,
                }
                self._dirty = True

        if not data:
            return None

        # Copia: no queremos que los conteos de IOCs/YARA (que tienen su
        # propio TTL, independiente del perfil) queden "horneados" dentro del
        # perfil cacheado.
        enriched = dict(data)
        enriched["ioc_summary"] = self._iocs_summary().get(key, {})
        enriched["yara_count"] = self._yara_summary().get(key, 0)
        return enriched

    def _iocs_summary(self) -> dict:
        return self._get_meta("iocs_summary", self.client.iocs_summary)

    def _yara_summary(self) -> dict:
        return self._get_meta("yara_summary", self.client.yara_summary)

    def _get_meta(self, key: str, fetch_fn: Callable[[], dict]) -> dict:
        meta_cache = self._cache["meta"]
        entry = meta_cache.get(key)
        if entry and not self._is_stale(entry.get("fetched_at")):
            return entry.get("data", {})

        try:
            data = fetch_fn()
        except RansomwareLiveError as exc:
            logger.warning("No se pudo refrescar '%s': %s", key, exc)
            return entry.get("data", {}) if entry else {}

        meta_cache[key] = {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }
        self._dirty = True
        return data

    def _is_stale(self, fetched_at: Optional[str]) -> bool:
        if not fetched_at:
            return True
        try:
            fetched = datetime.fromisoformat(fetched_at)
        except ValueError:
            return True
        return datetime.now(timezone.utc) - fetched > timedelta(hours=self.ttl_hours)

    def save(self) -> None:
        if self._dirty:
            save_state(self.cache_path, self._cache)
            self._dirty = False
