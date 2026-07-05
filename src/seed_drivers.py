"""Step 3.1 — synthetic driver roster."""
from src.db import get_client

DRIVERS = [
    # name,        shift_start, shift_end, max_hours
    ("Arun",       "09:00",     "18:00",   8),
    ("Meena",      "09:00",     "18:00",   8),
    ("Joseph",     "10:00",     "19:00",   8),
    ("Lakshmi",    "09:00",     "14:00",   4),   # half-shift driver
    ("Karthik",    "12:00",     "21:00",   8),   # late shift
]

def seed():
    sb = get_client()
    sb.table("drivers").delete().neq("id", 0).execute()
    rows = [{"name": n, "shift_start": s, "shift_end": e,
             "max_hours": h, "status": "available",
             "home_lat": 0.0, "home_lng": 0.0}  # home base unused for now
            for n, s, e, h in DRIVERS]
    sb.table("drivers").insert(rows).execute()
    print(f"Seeded {len(rows)} drivers.")

if __name__ == "__main__":
    seed()