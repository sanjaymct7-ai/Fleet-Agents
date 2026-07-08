"""Shared settings access — the chaos dials and order volume,
stored in the database instead of hardcoded in scripts."""
from src.db import get_client

DEFAULTS = {
    "p_traffic_per_route": 0.30,
    "p_stop_late": 0.20,
    "p_delivery_fails": 0.10,
    "n_orders_per_day": 30,
}


def get_settings() -> dict:
    sb = get_client()
    rows = sb.table("settings").select("key, value").execute().data
    settings = dict(DEFAULTS)
    for r in rows:
        settings[r["key"]] = r["value"]
    return settings


def set_setting(key: str, value: float):
    get_client().table("settings").upsert(
        {"key": key, "value": value}).execute()