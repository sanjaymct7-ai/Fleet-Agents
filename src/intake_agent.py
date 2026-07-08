"""Order Intake agent: messy text -> validated order row.
LLM extracts; code validates, geocodes, and inserts. """
import json
from datetime import datetime

from src.db import get_client
from src.llm import ask_llm
from src.geocoding import geocode_address

PROMPT = """You extract shipment details from a customer message.
Reply with ONLY a JSON object, no markdown, no explanation, with keys:
  customer_name (string), customer_tier ("standard"|"enterprise"),
  pickup_address (string, full address), drop_address (string, full address),
  window_start (ISO datetime), window_end (ISO datetime),
  weight_kg (number).
If a value is missing, use null. Today is {today}.

Customer message:
{message}
"""


def extract(message: str) -> dict:
    raw = ask_llm(PROMPT.format(today=datetime.now().isoformat(), message=message))
    raw = raw.replace("```json", "").replace("```", "").strip()  # de-fence
    return json.loads(raw)


def validate_and_build(data: dict) -> tuple[dict | None, list[str]]:
    """The gate: only clean rows pass. Returns (row, problems)."""
    problems = []
    
    # Geocode addresses
    pickup_coords = geocode_address(data.get("pickup_address"))
    drop_coords = geocode_address(data.get("drop_address"))
    
    if pickup_coords is None:
        problems.append(f"could not geocode pickup address: {data.get('pickup_address')!r}")
    if drop_coords is None:
        problems.append(f"could not geocode drop address: {data.get('drop_address')!r}")
    if not data.get("window_start") or not data.get("window_end"):
        problems.append("missing time window")
    
    w = data.get("weight_kg")
    if not isinstance(w, (int, float)) or not (0 < w <= 500):
        problems.append(f"implausible weight: {w!r}")
    
    if problems:
        return None, problems
    
    return {
        "customer_name": data.get("customer_name") or "Unknown customer",
        "customer_tier": data.get("customer_tier") or "standard",
        "pickup_lat": pickup_coords[0],
        "pickup_lng": pickup_coords[1],
        "drop_lat": drop_coords[0],
        "drop_lng": drop_coords[1],
        "window_start": data["window_start"],
        "window_end": data["window_end"],
        "weight_kg": w,
    }, []


def create_order(row: dict) -> dict:
    """The Intake agent's ONE write permission."""
    return get_client().table("orders").insert(row).execute().data[0]


def intake(message: str):
    data = extract(message)
    print("LLM extracted:", data)
    row, problems = validate_and_build(data)
    if problems:
        print("REJECTED -> needs human review:", problems)
        return None
    saved = create_order(row)
    print(f"Order #{saved['id']} created.")
    return saved


if __name__ == "__main__":
    intake("hi, this is Priya from TechCorp. need 25kg picked up from "
           "42 Main Street, Newcastle tomorrow 10am-1pm, "
           "drop at Central Station, Newcastle.")
    intake("pickup 15kg from Royal Victoria Infirmary tomorrow noon, "
           "drop at Grainger Street")