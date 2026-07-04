"""Step 2.2 — write generated orders into Supabase."""
from dataclasses import asdict

from src.db import get_client
from src.generator import make_order

N_ORDERS = 30  # a modest "day" — enough to make routing interesting


def order_to_row(order) -> dict:
    """Dataclass -> JSON-safe dict (datetimes become ISO strings)."""
    row = asdict(order)
    row["window_start"] = order.window_start.isoformat()
    row["window_end"] = order.window_end.isoformat()
    return row


def seed():
    sb = get_client()

    # 1) Clear previous synthetic orders so re-runs don't pile up.
    #    (.neq("id", 0) means "where id != 0", i.e. every row —
    #     Supabase requires *some* filter on delete as a safety rail.)
    sb.table("orders").delete().neq("id", 0).execute()

    # 2) Generate + insert in ONE batched request.
    rows = [order_to_row(make_order()) for _ in range(N_ORDERS)]
    result = sb.table("orders").insert(rows).execute()

    print(f"Inserted {len(result.data)} orders.")
    print("Sample row as stored:", result.data[0])


if __name__ == "__main__":
    seed()