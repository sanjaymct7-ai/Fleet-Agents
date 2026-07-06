"""Step 5.2 — the human-in-the-loop escalation graph.
One graph per T3 proposal: present -> [FREEZE until human] -> apply verdict."""
from typing import TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from src.db import get_client


class EscalationState(TypedDict):
    proposal_id: int
    exception_id: int
    summary: str
    verdict: str


def present_to_human(state: EscalationState):
    # The graph STOPS on this line until someone resumes it.
    answer = interrupt({
        "proposal_id": state["proposal_id"],
        "summary": state["summary"],
        "options": ["approve", "reject"],
    })
    return {"verdict": answer}


def apply_verdict(state: EscalationState):
    sb = get_client()
    if state["verdict"] == "approve":
        sb.table("proposals").update({"status": "approved"}) \
          .eq("id", state["proposal_id"]).execute()
    else:
        sb.table("proposals").update({"status": "rejected"}) \
          .eq("id", state["proposal_id"]).execute()
        sb.table("exceptions").update({"status": "open"}) \
          .eq("id", state["exception_id"]).execute()  # Recovery rethinks
    return {}


def build_graph(checkpointer):
    g = StateGraph(EscalationState)
    g.add_node("present", present_to_human)
    g.add_node("apply", apply_verdict)
    g.add_edge(START, "present")
    g.add_edge("present", "apply")
    g.add_edge("apply", END)
    return g.compile(checkpointer=checkpointer)


def summarize(sb, p) -> str:
    exc = p["exceptions"]
    if exc["order_id"] is None:
        return (f"[T3] {exc['type']}: {exc['detail']} | affects an entire route "
                f"| proposed: {p['action']} — {p['reasoning']}")
    order = (sb.table("orders").select("customer_name, customer_tier, priority")
             .eq("id", exc["order_id"]).single().execute().data)
    return (f"[T3] {exc['type']}: {exc['detail']} | order #{exc['order_id']} "
            f"({order['customer_name']}, {order['customer_tier']}, "
            f"prio {order['priority']}) | proposed: {p['action']} — {p['reasoning']}")


def run_terminal():
    """You are the dispatcher. Each frozen T3 becomes a question at your prompt."""
    sb = get_client()
    graph = build_graph(MemorySaver())
    t3 = (sb.table("proposals").select("*, exceptions(id, type, detail, order_id)")
          .eq("status", "pending").eq("risk_tier", 3).execute().data)
    print(f"{len(t3)} T3 proposals need a human.\n")

    for p in t3:
        config = {"configurable": {"thread_id": str(p["id"])}}
        result = graph.invoke({
            "proposal_id": p["id"], "exception_id": p["exceptions"]["id"],
            "summary": summarize(sb, p), "verdict": "",
        }, config)

        payload = result["__interrupt__"][0].value   # the frozen graph's question
        print("⏸  GRAPH PAUSED — needs your decision:")
        print("   " + payload["summary"])
        answer = ""
        while answer not in ("approve", "reject"):
            answer = input("   approve / reject > ").strip().lower()

        graph.invoke(Command(resume=answer), config)  # thaw from the same line
        print(f"   ▶ resumed, verdict '{answer}' applied.\n")


if __name__ == "__main__":
    run_terminal()