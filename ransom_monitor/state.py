"""Persistencia simple en JSON: por cada feed guardamos la fecha 'discovered'
más reciente ya notificada y un caché acotado de IDs vistos (para no duplicar
si dos víctimas comparten el mismo timestamp).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_SEEN_IDS = 1000


def load_state(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("No se pudo leer el estado en %s (%s) — se empieza de cero", path, exc)
        return {}


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, ensure_ascii=False)
    tmp_path.replace(path)


def update_feed_state(feed_state: dict, victims_sorted_desc: list, posted_ids: list[str]) -> None:
    """Actualiza in-place el estado de un feed tras procesar una corrida.

    victims_sorted_desc: TODAS las víctimas obtenidas en esta corrida, ya
        ordenadas por 'discovered' descendente (la más nueva primero).
    posted_ids: IDs que efectivamente se consideraron "nuevos" en esta corrida
        (se hayan mostrado en Teams o se hayan omitido por límite de cupo).
    """
    if victims_sorted_desc:
        newest = victims_sorted_desc[0].get("discovered")
        if newest:
            feed_state["last_discovered"] = newest

    seen = list(feed_state.get("seen_ids", []))
    seen_set = set(seen)
    for vid in posted_ids:
        if vid and vid not in seen_set:
            seen.append(vid)
            seen_set.add(vid)
    feed_state["seen_ids"] = seen[-MAX_SEEN_IDS:]
