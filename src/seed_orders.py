"""Step 2.2 — write generated orders into Supabase.
Order volume is read from settings, not hardcoded."""
from dataclasses import asdict

from src.db import get_client
from src.generator import make_order
from src.settings_helper import get_settings


def order_to_row(order) -> dict:
    """Dataclass -> JSON-safe dict (datetimes become ISO strings)."""
    row = asdict(order)
    row["window_start"] = order.window_start.isoformat()
    row["window_end"] = order.window_end.isoformat()
    return row


def seed():
    sb = get_client()
    n_orders = int(get_settings()["n_orders_per_day"])

    # 1) Clear previous synthetic orders so re-runs don't pile up.
    sb.table("orders").delete().neq("id", 0).execute()

    # 2) Generate + insert in ONE batched request.
    rows = [order_to_row(make_order()) for _ in range(n_orders)]
    result = sb.table("orders").insert(rows).execute()
    print(f"Inserted {len(result.data)} orders.")
    print("Sample row as stored:", result.data[0])


if __name__ == "__main__":
    seed()