"""Envío de Adaptive Cards a un webhook de Microsoft Teams (Workflows)."""

from __future__ import annotations

import requests


class TeamsPostError(Exception):
    pass


def post_card(webhook_url: str, card: dict, *, timeout: int = 15) -> None:
    resp = requests.post(webhook_url, json=card, timeout=timeout)
    if resp.status_code not in (200, 201, 202):
        raise TeamsPostError(
            f"El webhook de Teams devolvió HTTP {resp.status_code}: {resp.text[:300]}"
        )
