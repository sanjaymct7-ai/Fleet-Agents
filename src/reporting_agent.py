"""Reporting agent (8/8): end-of-day digest.
Reads history, computes stats in code, LLM writes ONE summary paragraph.
Writes a single row to reports. Touches nothing live."""
import json

from src.db import get_client
from src.llm import ask_llm

PROMPT = """You write a short end-of-day operations summary for a warehouse manager.
Use ONLY the statistics below — do not invent numbers or causes.
Be direct and useful: lead with the headline, flag anything needing attention.
4-5 sentences maximum, no greetings or sign-off.

Today's statistics:
{stats}

Reply ONLY JSON: {{"summary": "the paragraph"}}"""


def minutes(ts):
    return int(ts[11:13]) * 60 + int(ts[14:16])


def compute_stats(sb) -> dict:
    orders = sb.table("orders").select("status, customer_tier").execute().data
    stops = (sb.table("route_stops")
             .select("status, planned_arrival, actual_arrival").execute().data)
    excs = sb.table("exceptions").select("type, status").execute().data
    props = sb.table("proposals").select("risk_tier, status").execute().data
    routes = sb.table("routes").select("id, driver_id, status").execute().data

    done = [s for s in stops if s["status"] == "done" and s["actual_arrival"]]
    on_time = [s for s in done
               if minutes(s["actual_arrival"]) - minutes(s["planned_arrival"]) <= 15]
    delays = [minutes(s["actual_arrival"]) - minutes(s["planned_arrival"])
              for s in done]

    def count(rows, key):
        out = {}
        for r in rows:
            out[r[key]] = out.get(r[key], 0) + 1
        return out

    return {
        "orders_by_status": count(orders, "status"),
        "on_time_pct": round(100 * len(on_time) / len(done)) if done else None,
        "avg_delay_min": round(sum(delays) / len(delays), 1) if delays else 0,
        "worst_delay_min": max(delays) if delays else 0,
        "exceptions_by_type": count(excs, "type"),
        "exceptions_by_status": count(excs, "status"),
        "proposals_auto_executed": sum(1 for p in props
                                       if p["status"] == "executed" and p["risk_tier"] <= 1),
        "proposals_escalated_to_human": sum(1 for p in props if p["risk_tier"] == 3),
        "routes_run": sum(1 for r in routes if r["status"] == "completed"),
        "routes_unstaffed": sum(1 for r in routes if r["driver_id"] is None),
        "enterprise_orders_affected_by_exceptions": sum(
            1 for o in orders
            if o["customer_tier"] == "enterprise" and o["status"] == "failed"),
    }


def report():
    sb = get_client()
    stats = compute_stats(sb)
    raw = ask_llm(PROMPT.format(stats=json.dumps(stats, indent=2)))
    try:
        summary = json.loads(
            raw.replace("```json", "").replace("```", "").strip())["summary"]
    except (json.JSONDecodeError, KeyError):
        summary = "(LLM summary unavailable — stats recorded.)"
    row = sb.table("reports").insert(
        {"stats": stats, "summary": summary}).execute().data[0]
    print("📊 Report saved:")
    print(json.dumps(stats, indent=2))
    print("\n" + summary)
    return row


if __name__ == "__main__":
    report()