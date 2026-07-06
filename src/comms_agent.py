"""Customer Comms agent (7/8): renders queued notifications into messages.
Reads notifications+orders, writes notifications.body ONLY. Template-constrained."""
import json

from src.db import get_client
from src.llm import ask_llm

TONE = {
    "standard":  "brief and friendly, 1-2 sentences",
    "premium":   "warm and professional, 2-3 sentences",
    "enterprise": "detailed and formal, 3-4 sentences, mention that their "
                  "account team has been informed",
}

TEMPLATE = {
    "delay":       "Inform the customer their delivery (order #{oid}) is running "
                   "late but still arriving today.",
    "reschedule":  "Inform the customer that delivery of order #{oid} could not "
                   "be completed today and is rescheduled for tomorrow in the "
                   "same time window.",
    "confirmation": "Confirm that order #{oid} was delivered successfully.",
}

PROMPT = """You write customer notifications for a delivery company.
Write the message described below. Tone: {tone}.
Rules: do NOT promise refunds, compensation, or anything not stated below.
Do NOT invent reasons or details. Sign off as "Fleet Operations".

Message to write: {instruction}
Customer name: {name}

Reply ONLY JSON: {{"body": "the message text"}}"""


def render():
    sb = get_client()
    queued = (sb.table("notifications")
              .select("*, orders(customer_name, customer_tier)")
              .eq("status", "queued").execute().data)
    print(f"{len(queued)} notifications to write.")
    for nt in queued:
        order = nt["orders"]
        raw = ask_llm(PROMPT.format(
            tone=TONE[order["customer_tier"]],
            instruction=TEMPLATE[nt["kind"]].format(oid=nt["order_id"]),
            name=order["customer_name"]))
        try:
            body = json.loads(raw.replace("```json", "").replace("```", "").strip())["body"]
        except (json.JSONDecodeError, KeyError):
            print(f"  notification {nt['id']}: unusable answer — left queued for retry")
            continue
        sb.table("notifications").update(
            {"body": body, "status": "written"}).eq("id", nt["id"]).execute()
        print(f"  ✉️ #{nt['order_id']} ({order['customer_tier']}, {nt['kind']}): {body[:60]}…")


if __name__ == "__main__":
    render()