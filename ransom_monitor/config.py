"""Carga de configuración: config/settings.yaml + config/global.yaml +
config/countries/*.yaml. Los YAML no contienen secretos, solo el *nombre*
de la variable de entorno que trae el valor real (API key, webhooks).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class Feed:
    key: str  # "global" o código de país, p.ej. "MX"
    name: str
    enabled: bool
    webhook_url: Optional[str]
    max_items_per_run: int
    is_global: bool
    code: Optional[str] = None  # solo para feeds de país


class ConfigError(Exception):
    pass


def _read_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_settings(config_dir: Path) -> dict:
    return _read_yaml(config_dir / "settings.yaml")


def _resolve_webhook(raw: dict, label: str) -> Optional[str]:
    env_name = raw.get("webhook_url_env")
    if not env_name:
        raise ConfigError(f"Config de feed '{label}' no define 'webhook_url_env'")
    value = os.environ.get(env_name, "").strip()
    return value or None


def load_global_feed(config_dir: Path) -> Feed:
    raw = _read_yaml(config_dir / "global.yaml")
    return Feed(
        key="global",
        name=raw.get("name", "Global"),
        enabled=bool(raw.get("enabled", True)),
        webhook_url=_resolve_webhook(raw, "global"),
        max_items_per_run=int(raw.get("max_items_per_run", 20)),
        is_global=True,
    )


def load_country_feeds(config_dir: Path, order: Optional[list[str]] = None) -> list[Feed]:
    countries_dir = config_dir / "countries"
    feeds = []
    for path in sorted(countries_dir.glob("*.yaml")):
        raw = _read_yaml(path)
        code = raw.get("code")
        if not code:
            raise ConfigError(f"Config de país '{path.name}' no define 'code'")
        feeds.append(
            Feed(
                key=code.upper(),
                name=raw.get("name", code),
                enabled=bool(raw.get("enabled", False)),
                webhook_url=_resolve_webhook(raw, code),
                max_items_per_run=int(raw.get("max_items_per_run", 20)),
                is_global=False,
                code=code.upper(),
            )
        )

    if order:
        order_index = {code.upper(): i for i, code in enumerate(order)}
        feeds.sort(key=lambda f: order_index.get(f.key, len(order_index)))

    return feeds


class AppConfig:
    def __init__(self, config_dir: Path) -> None:
        self.config_dir = config_dir
        self.settings = load_settings(config_dir)
        self.global_feed = load_global_feed(config_dir)
        country_order = self.settings.get("countries", {}).get("order")
        self.country_feeds = load_country_feeds(config_dir, country_order)

    def all_feeds(self) -> list[Feed]:
        return [self.global_feed, *self.country_feeds]

    def enabled_feeds(self, only_key: Optional[str] = None) -> list[Feed]:
        feeds = self.all_feeds()
        if only_key:
            only_key = "global" if only_key.lower() == "global" else only_key.upper()
            feeds = [f for f in feeds if f.key == only_key]
        return [f for f in feeds if f.enabled]
