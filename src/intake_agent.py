"""Order Intake agent: messy text -> validated order row.
LLM extracts; code validates, geocodes, and inserts. """
import json
from datetime import datetime

from src.db import get_client
from src.llm import ask_llm

# --- The geocoding dictionary: REPLACE with ~10 landmarks in YOUR city ---
# (name in lowercase -> (lat, lng); get coords by right-clicking Google Maps)
PLACES = {
    "Merz court":      (54.98107575171029, -1.6155179996522366),
    "central station": (54.969319033998374, -1.614732864383876),
    "Kings gate":      (54.978699500299584, -1.6136062519123033),
    "osborne road":    (54.99597938019582, -1.606041959227096),
    "Iq stephenson ":      (54.97701626998197, -1.5984801444690884),
    "quay side":      (54.97012528015351, -1.6013334658103857),
    "byker morrisons":      (54.97662755414253, -1.5865909586063731),
    "chillingham road":      (54.99198453632017, -1.578933693203524),
    "heaton road":      (54.98374364406854, -1.581789902953335),
    "fehnam":      (54.97558349751474, -1.6536501529903682),
    # ... add more
}

PROMPT = """You extract shipment details from a customer message.
Reply with ONLY a JSON object, no markdown, no explanation, with keys:
  customer_name (string), customer_tier ("standard"|"premium"|"enterprise"),
  pickup_place (string, a short place name), drop_place (string),
  window_start (ISO datetime), window_end (ISO datetime),
  weight_kg (number), priority (integer 1-5, 1 = most urgent).
If a value is missing, use null. Today is {today}.

Customer message:
{message}
"""


def extract(message: str) -> dict:
    raw = ask_llm(PROMPT.format(today=datetime.now().isoformat(), message=message))
    raw = raw.replace("```json", "").replace("```", "").strip()  # de-fence
    return json.loads(raw)


def geocode(place: str | None) -> tuple[float, float] | None:
    if not place:
        return None
    return PLACES.get(place.lower().strip())  # None if unknown -> flagged


def validate_and_build(data: dict) -> tuple[dict | None, list[str]]:
    """The gate: only clean rows pass. Returns (row, problems)."""
    problems = []
    pickup = geocode(data.get("pickup_place"))
    drop = geocode(data.get("drop_place"))
    if pickup is None:
        problems.append(f"unknown pickup place: {data.get('pickup_place')!r}")
    if drop is None:
        problems.append(f"unknown drop place: {data.get('drop_place')!r}")
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
        "pickup_lat": pickup[0], "pickup_lng": pickup[1],
        "drop_lat": drop[0], "drop_lng": drop[1],
        "window_start": data["window_start"], "window_end": data["window_end"],
        "weight_kg": w,
        "priority": data.get("priority") or 3,
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
    intake("hi, this is Priya from TechCorp (enterprise acct). need 25kg "
           "picked up near the airport tomorrow between 10am and 1pm, "
           "drop at central station. quite urgent!")
    intake("pickup 15kg from the moon base at noon tomorrow, drop at harbour")