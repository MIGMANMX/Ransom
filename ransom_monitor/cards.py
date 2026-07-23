"""Construye Adaptive Cards (v1.4) para publicar en Microsoft Teams via
Workflows ("Post to a channel when a webhook request is received").

El body del POST al webhook es directamente el objeto Adaptive Card — es el
formato que espera la plantilla estándar de Teams Workflows. El conector
clásico "Incoming Webhook" (MessageCard) está deprecado por Microsoft.

Cada llamada a build_victim_card produce UNA tarjeta para UNA víctima (no se
agrupan varias víctimas en un mismo mensaje).
"""

from __future__ import annotations

from datetime import datetime, timezone

from ransom_monitor.countries import country_name_es

ADAPTIVE_SCHEMA = "http://adaptivecards.io/schemas/adaptive-card.json"
DESCRIPTION_MAX_CHARS = 500
GROUP_DESCRIPTION_MAX_CHARS = 350
MAX_VULNERABILITIES_SHOWN = 5

_SENTINEL_VALUES = {None, "", "N/A", "Not Found", "n/a", "not found"}


def _fmt_date(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except ValueError:
        return raw


def _truncate(text: str | None, limit: int) -> str | None:
    if not text:
        return None
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _flag_emoji(country_code: str | None) -> str:
    """Bandera a partir de un código ISO 3166-1 alpha-2 (regional indicator
    symbols de Unicode). Sin código válido (p. ej. el feed global) usa 🌎."""
    if not country_code or len(country_code) != 2 or not country_code.isalpha():
        return "🌎"
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in country_code.upper())


def _format_infostealer(value) -> str | None:
    if not value:
        return None
    if isinstance(value, dict):
        parts = []
        for label, key in (
            ("empleados", "employees"),
            ("usuarios", "users"),
            ("terceros", "thirdparties"),
        ):
            count = value.get(key)
            if count:
                parts.append(f"{label}: {count}")
        return ", ".join(parts) if parts else None
    return _truncate(str(value), 200)


def _victim_facts(victim: dict) -> list[dict]:
    facts = []

    def add(title: str, value):
        if value not in _SENTINEL_VALUES:
            facts.append({"title": title, "value": str(value)})

    add("Grupo", victim.get("group"))
    add("País", victim.get("country"))
    add("Sector", victim.get("activity"))
    add("Sitio web", victim.get("website"))
    add("Fecha de ataque", _fmt_date(victim.get("attackdate")))
    add("Descubierto", _fmt_date(victim.get("discovered")))
    add("Rescate", victim.get("ransom"))
    add("Tamaño de datos", victim.get("data_size"))
    if victim.get("press"):
        add("Cobertura de prensa", victim.get("press"))
    add("Infostealer (HudsonRock)", _format_infostealer(victim.get("infostealer")))

    return facts


def _group_intel_items(intel: dict | None) -> list[dict]:
    """Sección opcional con inteligencia del grupo (/group/<nombre>): historial,
    TTPs de MITRE ATT&CK y CVEs conocidas que explota. intel puede ser None si
    el enriquecimiento está desactivado o la consulta falló."""
    if not intel:
        return []

    items: list[dict] = [
        {
            "type": "TextBlock",
            "text": "Perfil del grupo",
            "weight": "Bolder",
            "wrap": True,
            "spacing": "Medium",
        }
    ]

    description = intel.get("description")
    if description and description not in _SENTINEL_VALUES:
        items.append(
            {
                "type": "TextBlock",
                "text": _truncate(description, GROUP_DESCRIPTION_MAX_CHARS),
                "wrap": True,
                "isSubtle": True,
                "spacing": "Small",
            }
        )

    facts = []

    def add(title: str, value):
        if value not in _SENTINEL_VALUES and value != 0:
            facts.append({"title": title, "value": str(value)})

    add("Víctimas históricas del grupo", intel.get("victims"))
    add("Activo desde", _fmt_date(intel.get("firstseen")))
    add("Última actividad conocida", _fmt_date(intel.get("lastseen")))

    ttps = intel.get("ttps") or []
    if ttps:
        technique_count = sum(len(t.get("techniques", [])) for t in ttps)
        add("TTPs MITRE ATT&CK", f"{technique_count} técnicas en {len(ttps)} tácticas")

    if intel.get("has_negotiations"):
        add("Chats de negociación filtrados", intel.get("negotiation_count"))
    if intel.get("has_ransomnote"):
        add("Notas de rescate disponibles", intel.get("ransomnotes_count"))

    ioc_summary = intel.get("ioc_summary")
    if ioc_summary:
        total = sum(ioc_summary.values())
        breakdown = ", ".join(
            f"{count} {ioc_type.upper()}"
            for ioc_type, count in sorted(ioc_summary.items(), key=lambda kv: -kv[1])
        )
        add("IOCs publicados", f"{total} ({breakdown})")

    add("Reglas YARA publicadas", intel.get("yara_count"))

    if facts:
        items.append({"type": "FactSet", "facts": facts, "spacing": "Small"})

    group_url = intel.get("url")
    if group_url:
        items.append(
            {
                "type": "TextBlock",
                "text": f"[Ver perfil completo del grupo]({group_url}) (IOCs, YARA, TTPs, negociaciones)",
                "wrap": True,
                "spacing": "Small",
            }
        )

    vulns = sorted(
        (v for v in (intel.get("vulnerabilities") or []) if v.get("CVE")),
        key=lambda v: v.get("CVSS") or 0,
        reverse=True,
    )[:MAX_VULNERABILITIES_SHOWN]
    if vulns:
        items.append(
            {
                "type": "TextBlock",
                "text": "CVEs conocidas explotadas por este grupo",
                "weight": "Bolder",
                "wrap": True,
                "spacing": "Medium",
            }
        )
        lines = []
        for v in vulns:
            cvss = v.get("CVSS")
            severity = v.get("severity")
            tag = f" ({severity}, CVSS {cvss})" if cvss else ""
            product = " ".join(p for p in (v.get("Vendor"), v.get("Product")) if p)
            lines.append(f"- **{v.get('CVE')}**{tag} — {product}".strip())
        items.append(
            {"type": "TextBlock", "text": "\n\n".join(lines), "wrap": True, "spacing": "Small"}
        )

    return items


def build_victim_card(
    victim: dict,
    *,
    feed_name: str,
    country_code: str | None = None,
    is_global: bool = False,
    group_intel: dict | None = None,
) -> dict:
    """Arma una Adaptive Card para UNA sola víctima.

    En feeds de país el header muestra el nombre del feed + su bandera
    (p. ej. "— México 🇲🇽"). En el feed global, que mezcla víctimas de
    cualquier país, se muestra en cambio el país de ESA víctima en particular
    (p. ej. "— Global — Brasil").
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    name = victim.get("victim") or victim.get("website") or "Víctima desconocida"

    if is_global:
        header_text = f"🚨 Nueva víctima de ransomware 🚨 — Global — {country_name_es(victim.get('country'))}"
    else:
        header_text = f"🚨 Nueva víctima de ransomware 🚨 — {feed_name} {_flag_emoji(country_code)}"

    header_items = [
        {
            "type": "TextBlock",
            "text": header_text,
            "weight": "Bolder",
            "size": "Large",
            "wrap": True,
        },
        {
            "type": "TextBlock",
            "text": f"generado {now}",
            "isSubtle": True,
            "spacing": "None",
            "wrap": True,
        },
        {
            "type": "TextBlock",
            "text": f"**{name}**",
            "wrap": True,
            "size": "Medium",
            "spacing": "Medium",
        },
    ]

    raw_description = victim.get("description")
    description = (
        _truncate(raw_description, DESCRIPTION_MAX_CHARS)
        if raw_description not in _SENTINEL_VALUES
        else None
    )
    if description:
        header_items.append(
            {"type": "TextBlock", "text": description, "wrap": True, "isSubtle": True, "spacing": "Small"}
        )

    body = list(header_items)

    screenshot = victim.get("screenshot")
    if screenshot:
        # A ancho completo (no en una columna "auto", que la reduce a un
        # thumbnail): "Stretch" hace que ocupe todo el ancho de la tarjeta.
        body.append(
            {
                "type": "Image",
                "url": screenshot,
                "size": "Stretch",
                "altText": f"Captura de la publicación de {name}",
                "spacing": "Medium",
            }
        )

    facts = _victim_facts(victim)
    if facts:
        body.append({"type": "FactSet", "facts": facts, "spacing": "Medium"})

    permalink = victim.get("permalink")
    if permalink:
        body.append(
            {
                "type": "TextBlock",
                "text": f"[Ver ficha completa en ransomware.live]({permalink})",
                "wrap": True,
                "spacing": "Small",
            }
        )

    body.extend(_group_intel_items(group_intel))

    body.append(
        {
            "type": "TextBlock",
            "text": "Fuente: ransomware.live (API PRO)",
            "wrap": True,
            "isSubtle": True,
            "size": "Small",
            "spacing": "Medium",
        }
    )

    return {
        "type": "AdaptiveCard",
        "$schema": ADAPTIVE_SCHEMA,
        "version": "1.4",
        "body": body,
    }


def build_omitted_notice_card(*, feed_name: str, omitted: int, total_new: int) -> dict:
    """Tarjeta corta cuando una corrida detecta más víctimas nuevas que
    feed.max_items_per_run: se avisa cuántas quedaron fuera en vez de
    mandarlas todas de golpe."""
    return {
        "type": "AdaptiveCard",
        "$schema": ADAPTIVE_SCHEMA,
        "version": "1.4",
        "body": [
            {
                "type": "TextBlock",
                "text": f"⚠️ {feed_name}: se detectaron {total_new} víctimas nuevas en esta corrida, "
                f"se omitieron {omitted} adicionales por límite de cupo por corrida "
                f"(max_items_per_run). Consulta ransomware.live para el listado completo.",
                "wrap": True,
            }
        ],
    }
