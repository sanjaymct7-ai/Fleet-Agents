"""Manager Portal — where the warehouse manager acts, not just watches.
Tab 1: Fleet (drivers + vehicles), with soft delete (deactivate/retire)."""
import streamlit as st

from src.db import get_client

st.set_page_config(page_title="Manager Portal", page_icon="🧰", layout="wide")
st.title("🧰 Manager Portal")

sb = get_client()

tab_fleet, tab_orders, tab_settings, tab_analytics = st.tabs(
    ["🚚 Fleet", "📦 Orders", "⚙️ Settings", "📈 Analytics"])

# =========================================================
# FLEET TAB — drivers + vehicles CRUD
# =========================================================
with tab_fleet:
    st.subheader("Drivers")

    drivers = sb.table("drivers").select("*").order("id").execute().data
    for d in drivers:
        with st.container(border=True):
            c1, c2, c3, c4, c5 = st.columns([2, 1, 1, 1, 1])
            c1.write(f"**{d['name']}**  (id {d['id']})")
            c2.write(f"{d['shift_start']}–{d['shift_end']}")
            c3.write(f"{d['max_hours']}h max")
            c4.write(f"`{d['status']}`")
            with c5:
                if d["status"] != "unavailable":
                    if st.button("Deactivate", key=f"tog_driver_{d['id']}"):
                        sb.table("drivers").update({"status": "unavailable"}) \
                          .eq("id", d["id"]).execute()
                        st.rerun()
                else:
                    if st.button("Reactivate", key=f"tog_driver_{d['id']}"):
                        sb.table("drivers").update({"status": "available"}) \
                          .eq("id", d["id"]).execute()
                        st.rerun()

    with st.expander("➕ Add a new driver"):
        with st.form("add_driver", clear_on_submit=True):
            name = st.text_input("Name")
            col1, col2, col3 = st.columns(3)
            shift_start = col1.time_input("Shift start")
            shift_end = col2.time_input("Shift end")
            max_hours = col3.number_input("Max hours", min_value=1, max_value=12, value=8)
            if st.form_submit_button("Add driver"):
                if name.strip():
                    sb.table("drivers").insert({
                        "name": name.strip(),
                        "shift_start": shift_start.strftime("%H:%M"),
                        "shift_end": shift_end.strftime("%H:%M"),
                        "max_hours": int(max_hours),
                        "status": "available",
                        "home_lat": 0.0, "home_lng": 0.0,
                    }).execute()
                    st.success(f"Added driver {name}")
                    st.rerun()
                else:
                    st.error("Name is required.")

    st.divider()
    st.subheader("Vehicles")

    vehicles = sb.table("vehicles").select("*").order("id").execute().data
    for v in vehicles:
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
            c1.write(f"**{v['name']}**  (id {v['id']})")
            c2.write(f"{v['capacity_kg']}kg capacity")
            c3.write(f"`{v['status']}`")
            with c4:
                if v["status"] != "retired":
                    if st.button("Maintenance" if v["status"] == "active" else "Reactivate",
                                 key=f"tog_vehicle_{v['id']}"):
                        new_status = "maintenance" if v["status"] == "active" else "active"
                        sb.table("vehicles").update({"status": new_status}) \
                          .eq("id", v["id"]).execute()
                        st.rerun()
                    if st.button("Retire", key=f"retire_vehicle_{v['id']}"):
                        sb.table("vehicles").update({"status": "retired"}) \
                          .eq("id", v["id"]).execute()
                        st.rerun()

    with st.expander("➕ Add a new vehicle"):
        with st.form("add_vehicle", clear_on_submit=True):
            vname = st.text_input("Name / plate")
            cap = st.number_input("Capacity (kg)", min_value=1, value=400)
            if st.form_submit_button("Add vehicle"):
                if vname.strip():
                    try:
                        sb.table("vehicles").insert({
                            "name": vname.strip(),
                            "capacity_kg": float(cap),
                            "status": "active",
                        }).execute()
                        st.success(f"Added vehicle {vname}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Could not add vehicle: {e}")
                else:
                    st.error("Name is required.")

# =========================================================
# ORDERS TAB — placeholder for now
# =========================================================
with tab_orders:
    st.info("Orders browser + Intake textbox coming next.")

# =========================================================
# SETTINGS TAB — placeholder for now
# =========================================================
with tab_settings:
    st.info("Chaos dials + depot settings coming next.")

# =========================================================
# ANALYTICS TAB — placeholder for now
# =========================================================
with tab_analytics:
    st.info("Trends from report history coming next.")