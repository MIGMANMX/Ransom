"""Orquestador: por cada feed habilitado (global + países LATAM), consulta
ransomware.live, calcula qué víctimas son nuevas desde la última corrida,
arma Adaptive Cards y las publica en el webhook de Teams correspondiente.

Pensado para ejecutarse periódicamente vía un programador externo (Task
Scheduler / cron), NO como proceso en loop infinito — así evitamos golpear
la API más seguido de lo necesario.
"""

from __future__ import annotations

import argparse
import logging
import os
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

from ransom_monitor.api_client import RansomwareLiveClient, RansomwareLiveError
from ransom_monitor.cards import build_omitted_notice_card, build_victim_card
from ransom_monitor.config import AppConfig, ConfigError, Feed
from ransom_monitor.group_intel import GroupIntelCache
from ransom_monitor.state import load_state, save_state, update_feed_state
from ransom_monitor.teams import TeamsPostError, post_card

ROOT = Path(__file__).resolve().parent.parent
logger = logging.getLogger("ransom_monitor")


def _sort_desc(victims: list[dict]) -> list[dict]:
    return sorted(victims, key=lambda v: v.get("discovered") or "", reverse=True)


def select_new_victims(
    feed_state: dict,
    victims: list[dict],
    initial_backfill: int,
    max_lookback_hours: float,
) -> list[dict]:
    """Devuelve las víctimas nuevas, en orden cronológico (más vieja primero),
    listas para publicarse.

    El "checkpoint" es feed_state['last_discovered']: solo se consideran
    nuevas las víctimas con discovered > ese valor. Además, como red de
    seguridad, nunca se mira más atrás de max_lookback_hours — así, si el
    checkpoint se pierde o el script estuvo mucho tiempo sin correr, no se
    inunda el canal con todo el histórico de golpe.
    """
    victims_desc = _sort_desc(victims)
    last_discovered = feed_state.get("last_discovered")
    seen_ids = set(feed_state.get("seen_ids", []))

    lookback_cutoff = (
        datetime.now(timezone.utc) - timedelta(hours=max_lookback_hours)
    ).isoformat()

    if last_discovered is None:
        candidates = [v for v in victims_desc if (v.get("discovered") or "") >= lookback_cutoff]
        new_victims = candidates[:initial_backfill]
    else:
        effective_cutoff = max(last_discovered, lookback_cutoff)
        new_victims = [
            v
            for v in victims_desc
            if v.get("id") not in seen_ids and (v.get("discovered") or "") > effective_cutoff
        ]

    return list(reversed(new_victims)), victims_desc


def _fetch_country_victims(
    client: RansomwareLiveClient, code: str, victims_cache: dict[str, list[dict]]
) -> list[dict]:
    """Trae víctimas de un país, reutilizando el resultado si ya se pidió en
    esta misma corrida — así un país que tiene su propio feed Y participa en
    'general' no se consulta dos veces."""
    if code not in victims_cache:
        victims_cache[code] = client.victims_by_country(code)
    return victims_cache[code]


def process_feed(
    feed: Feed,
    client: RansomwareLiveClient,
    state: dict,
    settings: dict,
    group_cache: GroupIntelCache | None,
    victims_cache: dict[str, list[dict]],
    latam_codes: list[str],
    *,
    dry_run: bool,
) -> None:
    if not feed.webhook_url and not dry_run:
        logger.info("[%s] deshabilitado o sin webhook configurado — se omite", feed.key)
        return

    logger.info("[%s] consultando ransomware.live...", feed.key)
    try:
        if feed.is_global:
            victims = client.recent_victims()
        elif feed.is_general:
            victims = []
            for code in latam_codes:
                victims.extend(_fetch_country_victims(client, code, victims_cache))
        else:
            victims = _fetch_country_victims(client, feed.code, victims_cache)
    except RansomwareLiveError as exc:
        logger.error("[%s] error consultando la API: %s", feed.key, exc)
        return

    total_fetched = len(victims)
    victims = [v for v in victims if v.get("country")]
    dropped = total_fetched - len(victims)
    if dropped:
        logger.info("[%s] %d víctima(s) sin país detectado, se excluyen", feed.key, dropped)

    feed_state = state.setdefault(feed.key, {})
    new_victims, victims_desc = select_new_victims(
        feed_state,
        victims,
        settings["run"]["initial_backfill"],
        settings["run"]["max_lookback_hours"],
    )

    if not new_victims:
        logger.info("[%s] sin víctimas nuevas (%d totales revisadas)", feed.key, len(victims))
        return

    total_new = len(new_victims)
    shown = new_victims[: feed.max_items_per_run]
    omitted_total = total_new - len(shown)

    logger.info("[%s] %d víctima(s) nueva(s), publicando %d (una tarjeta cada una)", feed.key, total_new, len(shown))

    teams_cfg = settings["teams"]

    def _pause() -> None:
        time.sleep(random.uniform(teams_cfg["min_delay_seconds"], teams_cfg["max_delay_seconds"]))

    for idx, victim in enumerate(shown):
        group_intel = group_cache.get(victim.get("group")) if group_cache else None
        card = build_victim_card(
            victim,
            feed_name=feed.name,
            country_code=feed.code,
            multi_country=feed.is_global or feed.is_general,
            group_intel=group_intel,
        )
        if dry_run:
            logger.info(
                "[%s] (dry-run) tarjeta %d/%d para '%s' NO enviada",
                feed.key, idx + 1, len(shown), victim.get("victim") or victim.get("website"),
            )
        else:
            try:
                post_card(feed.webhook_url, card, timeout=teams_cfg["timeout_seconds"])
                logger.info(
                    "[%s] tarjeta %d/%d publicada en Teams ('%s')",
                    feed.key, idx + 1, len(shown), victim.get("victim") or victim.get("website"),
                )
            except TeamsPostError as exc:
                logger.error("[%s] fallo publicando en Teams: %s", feed.key, exc)
                continue

        if idx < len(shown) - 1:
            _pause()

    if omitted_total > 0:
        notice = build_omitted_notice_card(feed_name=feed.name, omitted=omitted_total, total_new=total_new)
        if dry_run:
            logger.info("[%s] (dry-run) aviso de %d omitidas NO enviado", feed.key, omitted_total)
        else:
            _pause()
            try:
                post_card(feed.webhook_url, notice, timeout=teams_cfg["timeout_seconds"])
                logger.info("[%s] aviso de %d omitidas publicado en Teams", feed.key, omitted_total)
            except TeamsPostError as exc:
                logger.error("[%s] fallo publicando aviso de omitidas: %s", feed.key, exc)

    # Todas las "new_victims" (mostradas u omitidas por cupo) quedan marcadas
    # como vistas para no reintentarlas infinitamente en la próxima corrida.
    all_new_ids = [v.get("id") for v in new_victims if v.get("id")]
    if not dry_run:
        update_feed_state(feed_state, victims_desc, all_new_ids)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Monitor de víctimas de ransomware LATAM -> Teams")
    parser.add_argument(
        "--dry-run", action="store_true", help="No publica en Teams ni actualiza el estado; solo muestra qué haría"
    )
    parser.add_argument(
        "--feed", help="Procesar solo este feed ('global', 'general' o código de país, p.ej. MX)"
    )
    parser.add_argument(
        "--reset-state", action="store_true", help="Ignora el estado previo (recalcula todo como primera corrida)"
    )
    parser.add_argument(
        "--max-lookback-hours",
        type=float,
        help="Sobrescribe run.max_lookback_hours de settings.yaml solo para esta corrida (útil para pruebas puntuales)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    load_dotenv(ROOT / ".env")

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    try:
        cfg = AppConfig(ROOT / "config")
    except ConfigError as exc:
        print(f"Error de configuración: {exc}", file=sys.stderr)
        return 2

    settings = cfg.settings
    if args.max_lookback_hours is not None:
        settings["run"]["max_lookback_hours"] = args.max_lookback_hours
    log_dir = (ROOT / settings["run"]["log_file"]).parent
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, settings["run"]["log_level"].upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(ROOT / settings["run"]["log_file"], encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )

    api_key_env = settings["api"]["api_key_env"]
    api_key = os.environ.get(api_key_env, "").strip()
    if not api_key:
        logger.error("Falta la variable de entorno %s (API key) — revisa tu .env", api_key_env)
        return 2

    client = RansomwareLiveClient(
        base_url=settings["api"]["base_url"],
        api_key=api_key,
        timeout=settings["api"]["timeout_seconds"],
        user_agent=settings["api"]["user_agent"],
        min_delay=settings["network"]["min_delay_seconds"],
        max_delay=settings["network"]["max_delay_seconds"],
        max_retries=settings["network"]["max_retries"],
        backoff_base=settings["network"]["backoff_base_seconds"],
        backoff_max=settings["network"]["backoff_max_seconds"],
    )

    try:
        info = client.validate_key()
        logger.info("API key válida (cliente: %s)", info.get("client"))
    except RansomwareLiveError as exc:
        logger.error("La API key no es válida o la API no respondió: %s", exc)
        return 1

    state_path = ROOT / settings["run"]["state_file"]
    state = load_state(state_path)
    if args.reset_state:
        if args.feed:
            # Solo se resetea el feed pedido — si tocáramos todo el dict,
            # save_state luego sobrescribiría el checkpoint de los demás
            # feeds (que ni se procesan en esta corrida) con la nada.
            lowered = args.feed.lower()
            reset_key = lowered if lowered in ("global", "general") else args.feed.upper()
            state.pop(reset_key, None)
        else:
            state = {}

    group_cache = None
    if settings["enrichment"]["group_intel"]:
        group_cache = GroupIntelCache(
            client,
            ROOT / settings["enrichment"]["group_cache_file"],
            settings["enrichment"]["group_cache_ttl_hours"],
        )

    feeds = cfg.enabled_feeds(args.feed)
    if not feeds:
        logger.warning("No hay feeds habilitados que coincidan con los criterios — nada que hacer")
        return 0

    # Compartida entre feeds de país y el feed 'general' dentro de esta misma
    # corrida: si un país tiene su propio feed Y participa en 'general', solo
    # se consulta una vez.
    victims_cache: dict[str, list[dict]] = {}
    latam_codes = [f.code for f in cfg.country_feeds]

    for feed in feeds:
        process_feed(feed, client, state, settings, group_cache, victims_cache, latam_codes, dry_run=args.dry_run)
        if not args.dry_run:
            save_state(state_path, state)
            if group_cache:
                group_cache.save()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
