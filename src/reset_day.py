"""Reset the world for a fresh simulated day. Deletes children before parents."""
from src.db import get_client
from src.seed_orders import seed as seed_orders


def reset():
    sb = get_client()
    for table, key in [("notifications", "id"), ("proposals", "id"),
                       ("exceptions", "id"), ("vehicle_positions", "route_id"),
                       ("route_stops", "id"), ("routes", "id")]:
        sb.table(table).delete().neq(key, 0).execute()
        print(f"cleared {table}")
    sb.table("drivers").update({"status": "available"}).neq("id", 0).execute()
    seed_orders()   # wipes old orders, inserts a fresh 30
    print("World reset. Ready for a new day.")


if __name__ == "__main__":
    reset()