"""The warehouse manager's single screen: everything, live."""
import folium
import streamlit as st
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command
from streamlit_autorefresh import st_autorefresh
from streamlit_folium import st_folium

from src.db import get_client
from src.escalation_graph import build_graph, summarize
from src.executor import run as run_executor
from src.matrix import DEPOT
from src.run_day import run_day

st.set_page_config(page_title="Command Center", page_icon="🚚", layout="wide")

# ---------- autorefresh, paused while a day is running ----------
if "running_day" not in st.session_state:
    st.session_state.running_day = False
if not st.session_state.running_day:
    st_autorefresh(interval=10_000, key="live")

sb = get_client()


@st.cache_resource
def get_graph():
    return build_graph(MemorySaver())


graph = get_graph()

# ---------- 1) THE BANNER: escalations are unmissable ----------
t3 = (sb.table("proposals").select("*, exceptions(id, type, detail, order_id)")
      .eq("status", "pending").eq("risk_tier", 3).execute().data)
if t3:
    st.error(f"🔴 {len(t3)} ESCALATION(S) NEED YOUR DECISION — see Approvals panel below")

st.title("🚚 Fleet Command Center")

# ---------- 2) THE BUTTON: run the whole day from here ----------
if st.button("▶ Run a full day", type="primary",
             disabled=st.session_state.running_day):
    st.session_state.running_day = True
    try:
        with st.status("Running the day…", expanded=True) as s:
            run_day(log=st.write)
            s.update(label="Day finished", state="complete")
    finally:
        st.session_state.running_day = False
    st.rerun()

# ---------- 3) KPI TILES ----------
orders = sb.table("orders").select("status").execute().data
stops = (sb.table("route_stops")
         .select("status, planned_arrival, actual_arrival").execute().data)


def minutes(ts):
    return int(ts[11:13]) * 60 + int(ts[14:16])


done = [s for s in stops if s["status"] == "done" and s["actual_arrival"]]
on_time = [s for s in done
           if minutes(s["actual_arrival"]) - minutes(s["planned_arrival"]) <= 15]
counts = {}
for o in orders:
    counts[o["status"]] = counts.get(o["status"], 0) + 1

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Delivered", counts.get("delivered", 0))
k2.metric("Failed", counts.get("failed", 0))
k3.metric("In transit", counts.get("assigned", 0))
k4.metric("On-time %", f"{round(100 * len(on_time) / len(done)) if done else 100}%")
open_exc = (sb.table("exceptions").select("id", count="exact", head=True)
            .eq("status", "open").execute().count)
k5.metric("Open exceptions", open_exc)

# ---------- 4) LIVE MAP + FEEDS ----------
left, right = st.columns([3, 2])

with left:
    st.subheader("Live map")
    m = folium.Map(location=DEPOT, zoom_start=12)
    folium.Marker(DEPOT, tooltip="DEPOT",
                  icon=folium.Icon(color="black", icon="home")).add_to(m)
    COLORS = ["red", "blue", "green", "purple", "orange"]

    route_stops = (sb.table("route_stops")
                   .select("route_id, seq, status, orders(drop_lat, drop_lng)")
                   .order("route_id").order("seq").execute().data)
    routes: dict[int, list] = {}
    for s in route_stops:
        routes.setdefault(s["route_id"], []).append(s)
    for i, (rid, r_stops) in enumerate(routes.items()):
        color = COLORS[i % len(COLORS)]
        path = [DEPOT] + [(float(s["orders"]["drop_lat"]),
                           float(s["orders"]["drop_lng"])) for s in r_stops] + [DEPOT]
        folium.PolyLine(path, color=color, weight=2, opacity=0.6).add_to(m)
        for s in r_stops:
            pt = (float(s["orders"]["drop_lat"]), float(s["orders"]["drop_lng"]))
            folium.CircleMarker(pt, radius=4, color=color, fill=True,
                                fill_opacity=1 if s["status"] == "done" else 0.3,
                                tooltip=f"route {rid} · stop {s['seq']} · {s['status']}"
                                ).add_to(m)

    vans = sb.table("vehicle_positions").select("*").execute().data
    for v in vans:
        folium.Marker((float(v["lat"]), float(v["lng"])),
                      tooltip=f"🚚 {v['driver_name']} @ {v['sim_time']}",
                      icon=folium.Icon(color="darkblue", icon="truck", prefix="fa")
                      ).add_to(m)
    st_folium(m, width=650, height=450, key="map")
    if vans:
        st.caption(f"Vans last seen at sim-time {max(v['sim_time'] for v in vans)}")

with right:
    st.subheader("Exception feed")
    exc = (sb.table("exceptions").select("id, type, detail, status, order_id")
           .order("id", desc=True).limit(8).execute().data)
    for e in exc:
        icon = {"open": "🔴", "proposed": "🟡",
                "resolved": "🟢", "escalated": "🟠"}[e["status"]]
        who = f"#{e['order_id']}" if e["order_id"] else "route-level"
        st.write(f"{icon} **{who}** {e['type']} — {e['detail']} `{e['status']}`")

    st.subheader("Customer notifications")
    notes = (sb.table("notifications").select("order_id, kind, status, body")
             .order("id", desc=True).limit(6).execute().data)
    for nt in notes:
        with st.expander(f"✉️ order #{nt['order_id']} — {nt['kind']} `{nt['status']}`"):
            st.write(nt.get("body") or "_not written yet_")

# ---------- 5) APPROVALS: the human-in-the-loop, embedded ----------
st.divider()
st.subheader("⚖️ Approvals")
if not t3:
    st.success("Nothing waiting on you.")
for p in t3:
    config = {"configurable": {"thread_id": str(p["id"])}}
    if not graph.get_state(config).next:
        graph.invoke({"proposal_id": p["id"], "exception_id": p["exceptions"]["id"],
                      "summary": summarize(sb, p), "verdict": ""}, config)
    with st.container(border=True):
        st.write(summarize(sb, p))
        c1, c2, _ = st.columns([1, 1, 4])
        if c1.button("✅ Approve", key=f"a{p['id']}"):
            graph.invoke(Command(resume="approve"), config)
            st.rerun()
        if c2.button("❌ Reject", key=f"r{p['id']}"):
            graph.invoke(Command(resume="reject"), config)
            st.rerun()

if st.button("▶ Run executor (apply approved actions)"):
    run_executor()
    st.rerun()