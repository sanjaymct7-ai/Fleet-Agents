"""Step 2.6 — the fleet map: planned routes drawn over the city."""
import folium
import streamlit as st
from streamlit_folium import st_folium

from src.db import get_client
from src.matrix import DEPOT

st.set_page_config(page_title="Fleet Map", page_icon="🗺️", layout="wide")
st.title("🗺️ Planned Routes")

COLORS = ["red", "blue", "green", "purple", "orange", "darkred", "cadetblue"]

sb = get_client()

# One query, two tables: the embedded select follows the foreign key
# route_stops.order_id -> orders, pulling coordinates along for the ride.
stops = (sb.table("route_stops")
         .select("route_id, seq, planned_arrival, order_id, "
                 "orders(drop_lat, drop_lng, customer_tier, priority)")
         .order("route_id").order("seq").execute().data)

if not stops:
    st.warning("No planned routes found — run `python -m src.planner` first.")
    st.stop()

# Group stops by route
routes: dict[int, list] = {}
for s in stops:
    routes.setdefault(s["route_id"], []).append(s)

m = folium.Map(location=DEPOT, zoom_start=12)
folium.Marker(DEPOT, tooltip="DEPOT",
              icon=folium.Icon(color="black", icon="home")).add_to(m)

for i, (route_id, r_stops) in enumerate(routes.items()):
    color = COLORS[i % len(COLORS)]
    path = [DEPOT]
    for s in r_stops:
        point = (float(s["orders"]["drop_lat"]), float(s["orders"]["drop_lng"]))
        path.append(point)
        folium.CircleMarker(
            point, radius=6, color=color, fill=True, fill_opacity=0.9,
            tooltip=(f"Route {route_id} · stop {s['seq']} · order #{s['order_id']} · "
                     f"ETA {s['planned_arrival'][11:16]} · "
                     f"{s['orders']['customer_tier']}"),
        ).add_to(m)
    path.append(DEPOT)  # and home again
    folium.PolyLine(path, color=color, weight=3, opacity=0.7,
                    tooltip=f"Route {route_id}").add_to(m)

st_folium(m, width=1100, height=600)

st.caption(f"{len(routes)} routes · {len(stops)} stops · lines are straight "
           "segments between stops (real road geometry is a later upgrade)")