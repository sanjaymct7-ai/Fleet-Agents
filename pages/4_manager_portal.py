"""Manager Portal — where the warehouse manager acts, not just watches.
Orders tab: monitor all orders (table + filters), rules-based cancel.
Fleet tab: drivers + vehicles CRUD, with soft delete (deactivate/retire).
Customers place orders via the separate Place Order page — manager only monitors."""
import streamlit as st

from src.db import get_client

st.set_page_config(page_title="Manager Portal", page_icon="🗂️", layout="wide")
st.title("🗂️ Manager Portal")

sb = get_client()

tab_orders, tab_fleet, tab_settings, tab_analytics = st.tabs(
    ["📦 Orders", "🚚 Fleet", "⚙️ Settings", "📈 Analytics"])

# ══════════════════════════ ORDERS TAB ══════════════════════════
with tab_orders:
    st.subheader("All orders")
    g1, g2, g3 = st.columns(3)
    f_status = g1.multiselect("Status", ["new", "planned", "assigned",
                                         "delivered", "failed", "cancelled"])
    f_source = g2.selectbox("Source", ["all", "manual", "generator"])
    f_search = g3.text_input("Search customer")

    q = sb.table("orders").select(
        "id, customer_name, customer_tier, priority, weight_kg, "
        "window_start, window_end, status, source").order("id", desc=True)
    if f_status:
        q = q.in_("status", f_status)
    if f_source != "all":
        q = q.eq("source", f_source)
    if f_search.strip():
        q = q.ilike("customer_name", f"%{f_search.strip()}%")
    rows = q.limit(200).execute().data
    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.caption(f"{len(rows)} orders shown")

    st.divider()
    st.subheader("Cancel an order")
    cancellable = [r for r in rows if r["status"] == "new"]
    if not cancellable:
        st.caption("Only orders still in status 'new' can be cancelled — "
                   "none match the current filter.")
    else:
        pick = st.selectbox("Order", cancellable,
                            format_func=lambda r: f"#{r['id']} — "
                            f"{r['customer_name']} ({r['weight_kg']}kg)")
        if st.button("🚫 Cancel this order"):
            sb.table("orders").update({"status": "cancelled"}) \
              .eq("id", pick["id"]).eq("status", "new").execute()
            sb.table("notifications").insert(
                {"order_id": pick["id"], "kind": "cancellation"}).execute()
            st.success(f"Order #{pick['id']} cancelled — customer "
                       "notification queued.")
            st.rerun()

# ══════════════════════════ FLEET TAB ══════════════════════════
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

# ══════════════════════════ SETTINGS TAB (placeholder) ══════════════════════════
with tab_settings:
    from src.settings_helper import get_settings, set_setting

    st.subheader("Simulation settings")
    st.caption("These control tomorrow's simulated day. Changes apply on the next Run-day.")

    current = get_settings()

    traffic = st.slider("Chance of traffic jam per route", 0.0, 1.0,
                        float(current["p_traffic_per_route"]), 0.05)
    late = st.slider("Chance an individual stop runs late", 0.0, 1.0,
                     float(current["p_stop_late"]), 0.05)
    fails = st.slider("Chance a delivery fails (nobody home)", 0.0, 0.5,
                      float(current["p_delivery_fails"]), 0.01)
    n_orders = st.slider("Orders per day", 5, 100,
                         int(current["n_orders_per_day"]), 5)

    if st.button("💾 Save settings"):
        set_setting("p_traffic_per_route", traffic)
        set_setting("p_stop_late", late)
        set_setting("p_delivery_fails", fails)
        set_setting("n_orders_per_day", n_orders)
        st.success("Settings saved — will apply on the next Run-day.")

# ══════════════════════════ ANALYTICS TAB (placeholder) ══════════════════════════
with tab_analytics:
    st.info("Trends from report history coming next.")