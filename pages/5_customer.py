"""
📱 Customer Portal — Two-door architecture.

The same system, viewed through a customer's eyes:
- Pseudo-login (scoped to customer_name)
- Place order (agent-parsed or structured form with real addresses)
- Track live delivery (mini-map, ETA, status timeline)
- Messages inbox (delays, confirmations, etc.)
- Order history + feedback

ARCHITECTURAL LESSON: Every query on this page MUST filter by customer_name.
This teaches scoping discipline — the page never leaks data beyond the logged-in customer.
In production, Supabase Auth + RLS would enforce this. Here, it's a discipline exercise.
"""

import streamlit as st
from datetime import datetime, timedelta, date, time as dt_time
from src.db import get_client
from src.intake_agent import create_order, intake
from src.geocoding import geocode_address

st.set_page_config(page_title="My Orders", page_icon="📱", layout="centered")
st.title("📱 My Delivery Orders")

# ======================================================================
# PSEUDO-LOGIN — One door per customer
# ======================================================================

sb = get_client()

if "logged_in_customer" not in st.session_state:
    st.session_state.logged_in_customer = None

# Sidebar: login UI
with st.sidebar:
    st.subheader("Sign in")
    
    # Fetch existing customers
    try:
        existing_data = sb.table("orders").select("customer_name") \
            .order("created_at", desc=True).limit(100).execute().data
        existing_customers = sorted(set([o["customer_name"] for o in existing_data]))
    except Exception as e:
        st.error(f"Could not fetch customers: {e}")
        existing_customers = []
    
    # Dropdown or free-text
    col1, col2 = st.columns([3, 1])
    
    option = col1.selectbox(
        "Your name",
        options=["— New customer —"] + existing_customers,
        key="customer_select"
    )
    
    if option == "— New customer —":
        customer_name = col1.text_input("Enter your name (required)")
    else:
        customer_name = option
    
    # Login button
    if col2.button("Login", key="login_btn"):
        if not customer_name or customer_name.strip() == "":
            st.error("Please enter your name.")
        else:
            st.session_state.logged_in_customer = customer_name.strip()
            st.rerun()

# If not logged in, show login screen only
if not st.session_state.logged_in_customer:
    st.info("👆 Sign in above to view your orders and place new deliveries.")
    st.stop()

# ======================================================================
# LOGGED-IN: Show customer portal
# ======================================================================

customer = st.session_state.logged_in_customer
st.write(f"**Signed in as:** {customer}")

if st.sidebar.button("Logout"):
    st.session_state.logged_in_customer = None
    st.rerun()

# Tabs: Place Order | Track | Messages | History
tab1, tab2, tab3, tab4 = st.tabs(["🛒 Place Order", "📍 Track", "💬 Messages", "📋 History"])

# ======================================================================
# TAB 1: PLACE ORDER — Agent + Preview + Confirm (with real addresses)
# ======================================================================

with tab1:
    st.subheader("Place a New Order")
    
    # Two input modes
    mode = st.radio("How would you like to order?", ["Tell us what you need (AI)", "Quick form"])
    
    if mode == "Tell us what you need (AI)":
        st.caption("Describe your delivery in plain English. Our agent will parse it.")
        
        message = st.text_area(
            "What do you need delivered?",
            placeholder="E.g., 'Pick up 25kg from Central Station, Newcastle tomorrow 10am-1pm, drop at Grey's Monument'",
            height=100
        )
        
        if st.button("Parse with AI", key="parse_ai"):
            if not message.strip():
                st.error("Please describe your delivery.")
            else:
                with st.spinner("Parsing your order..."):
                    try:
                        # intake() parses, validates, and creates the order
                        result = intake(message)
                        if result:
                            st.success(f"✅ Order #{result['id']} confirmed!")
                            st.balloons()
                            st.write(f"""
                            **Order Details:**
                            - **Customer:** {result.get('customer_name', 'Unknown')}
                            - **Account:** {result.get('customer_tier', 'standard')}
                            - **Weight:** {result.get('weight_kg')} kg
                            - **Window:** {result.get('window_start', 'N/A')} to {result.get('window_end', 'N/A')}
                            """)
                        else:
                            st.error("❌ Couldn't parse your order. Please try the quick form or call us.")
                    except Exception as e:
                        st.error(f"Error: {str(e)[:200]}")
    
    else:  # Quick form with real addresses
        st.caption("Fill in the details below.")
        
        with st.form("quick_order"):
            col1, col2 = st.columns(2)
            
            pickup_address = col1.text_input("Pickup address (full address)")
            drop_address = col2.text_input("Drop-off address (full address)")
            
            weight_kg = st.number_input("Package weight (kg)", min_value=0.1, max_value=500.0,
                                        value=5.0, step=0.5)
            
            col3, col4 = st.columns(2)
            delivery_date = col3.date_input("Date", value=date.today() + timedelta(days=1),
                                            min_value=date.today())
            time_slot = col4.selectbox("Time window", [
                "09:00–12:00", "12:00–15:00", "15:00–18:00",
            ])
            
            submitted = st.form_submit_button("Place Order", type="primary")
        
        if submitted:
            if not pickup_address.strip() or not drop_address.strip():
                st.error("Please enter both pickup and drop-off addresses.")
            else:
                with st.spinner("Geocoding addresses..."):
                    pickup_coords = geocode_address(pickup_address)
                    drop_coords = geocode_address(drop_address)
                
                if not pickup_coords:
                    st.error(f"Could not find pickup address: {pickup_address}")
                elif not drop_coords:
                    st.error(f"Could not find drop-off address: {drop_address}")
                elif pickup_coords == drop_coords:
                    st.error("Pickup and drop-off addresses must be different.")
                else:
                    try:
                        start_hour, end_hour = {
                            "09:00–12:00": (9, 12),
                            "12:00–15:00": (12, 15),
                            "15:00–18:00": (15, 18),
                        }[time_slot]
                        
                        window_start = datetime.combine(delivery_date, dt_time(start_hour, 0))
                        window_end = datetime.combine(delivery_date, dt_time(end_hour, 0))
                        
                        row = {
                            "customer_name": customer,
                            "customer_tier": "standard",
                            "pickup_lat": pickup_coords[0],
                            "pickup_lng": pickup_coords[1],
                            "drop_lat": drop_coords[0],
                            "drop_lng": drop_coords[1],
                            "window_start": window_start.isoformat(),
                            "window_end": window_end.isoformat(),
                            "weight_kg": float(weight_kg),
                        }
                        
                        saved = create_order(row)
                        st.success(f"✅ Order #{saved['id']} confirmed!")
                        st.balloons()
                    except Exception as e:
                        st.error(f"Error creating order: {str(e)[:200]}")

# ======================================================================
# TAB 2: TRACK ORDER — Status Timeline + Mini-Map + ETA
# ======================================================================

with tab2:
    st.subheader("Track Your Deliveries")
    
    # Get customer's active orders (status != delivered, failed, cancelled)
    try:
        active_orders = sb.table("orders") \
            .select("id, customer_name, status, window_start, weight_kg, created_at") \
            .eq("customer_name", customer) \
            .in_("status", ["new", "planned", "assigned", "in_transit"]) \
            .order("created_at", desc=True) \
            .execute().data
    except Exception as e:
        st.error(f"Could not load orders: {e}")
        active_orders = []
    
    if not active_orders:
        st.info("✅ No active deliveries. Place a new order above!")
    else:
        # Select which order to track
        order_options = {
            f"Order #{o['id']} — {o['status'].replace('_', ' ').title()}": o['id']
            for o in active_orders
        }
        
        selected_order_label = st.selectbox("Select an order to track", order_options.keys())
        selected_order_id = order_options[selected_order_label]
        
        # Fetch order details
        try:
            order = sb.table("orders") \
                .select("*") \
                .eq("id", selected_order_id) \
                .eq("customer_name", customer) \
                .execute().data[0]
        except IndexError:
            st.error("Order not found.")
            st.stop()
        
        # Status mapping: human-readable
        status_map = {
            "new": "📋 Order Received",
            "planned": "🤖 Being Planned",
            "assigned": "📍 Assigned to Driver",
            "in_transit": "🚚 Out for Delivery",
            "delivered": "✅ Delivered",
            "failed": "❌ Delivery Failed",
            "cancelled": "🚫 Cancelled",
        }
        
        current_status = status_map.get(order["status"], order["status"])
        
        # Timeline
        st.markdown("### 📍 Delivery Timeline")
        
        status_sequence = ["new", "planned", "assigned", "in_transit", "delivered"]
        current_idx = status_sequence.index(order["status"]) if order["status"] in status_sequence else 0
        
        col1, col2, col3, col4, col5 = st.columns(5)
        statuses_display = [
            (col1, "📋 Placed"),
            (col2, "🤖 Planned"),
            (col3, "📍 Assigned"),
            (col4, "🚚 Out"),
            (col5, "✅ Delivered"),
        ]
        
        for i, (col, label) in enumerate(statuses_display):
            if i <= current_idx:
                col.success(label)
            else:
                col.info(label)
        
        # ETA and order details
        st.markdown("### 📦 Order Details")
        col1, col2, col3 = st.columns(3)
        col1.metric("Status", current_status)
        col2.metric("Weight", f"{order['weight_kg']} kg")
        col3.metric("Account", order["customer_tier"].title())
        
        window_start = order.get("window_start", "N/A")
        window_end = order.get("window_end", "N/A")
        st.write(f"**Delivery Window:** {window_start} to {window_end}")
        
        # Mini-map: only show if order is in_transit or assigned
        if order["status"] in ["in_transit", "assigned"]:
            st.markdown("### 🗺️ Live Location")
            
            try:
                # Find the route assigned to this order
                route_stops = sb.table("route_stops") \
                    .select("route_id, planned_arrival") \
                    .eq("order_id", selected_order_id) \
                    .execute().data
                
                if route_stops:
                    route_id = route_stops[0]["route_id"]
                    planned_eta = route_stops[0]["planned_arrival"]
                    
                    # Get vehicle position for this route
                    positions = sb.table("vehicle_positions") \
                        .select("lat, lng, driver_name, sim_time") \
                        .eq("route_id", route_id) \
                        .order("updated_at", desc=True) \
                        .limit(1) \
                        .execute().data
                    
                    if positions:
                        pos = positions[0]
                        st.write(f"**Driver:** {pos.get('driver_name', 'Unknown')}")
                        st.write(f"**Last update:** {pos.get('sim_time', 'N/A')}")
                        st.write(f"**Estimated arrival:** {planned_eta}")
                        
                        # Simple map (Streamlit's native st.map)
                        import pandas as pd
                        map_data = pd.DataFrame(
                            {
                                "lat": [float(pos["lat"]), float(order["drop_lat"])],
                                "lon": [float(pos["lng"]), float(order["drop_lng"])],
                                "name": [f"{pos['driver_name']}'s Van", "Your Drop Point"],
                            }
                        )
                        st.map(map_data, zoom=13)
                    else:
                        st.info("🚚 Van is on route — position will appear soon.")
                else:
                    st.info("📍 Order is being planned. Map will appear once dispatched.")
            except Exception as e:
                st.warning(f"Could not load location: {str(e)[:100]}")
        
        # Live delay banner (if applicable)
        try:
            route_stops = sb.table("route_stops") \
                .select("planned_arrival, actual_arrival") \
                .eq("order_id", selected_order_id) \
                .execute().data
            
            if route_stops and route_stops[0].get("actual_arrival"):
                planned = datetime.fromisoformat(route_stops[0]["planned_arrival"])
                actual = datetime.fromisoformat(route_stops[0]["actual_arrival"])
                delay = (actual - planned).total_seconds() / 60
                
                if delay > 5:
                    st.warning(f"⚠️ Running ~{int(delay)} min behind — sorry!")
                elif delay < -5:
                    st.success(f"✅ Early by ~{int(abs(delay))} min — we're ahead!")
        except:
            pass

# ======================================================================
# TAB 3: MESSAGES INBOX — Comms from agents
# ======================================================================

with tab3:
    st.subheader("Your Messages")
    
    try:
        messages = sb.table("comms_agent") \
            .select("*") \
            .eq("customer_name", customer) \
            .order("created_at", desc=True) \
            .limit(50) \
            .execute().data
    except Exception as e:
        st.error(f"Could not load messages: {e}")
        messages = []
    
    if not messages:
        st.info("📭 No messages yet. You'll get alerts here for delays, confirmations, etc.")
    else:
        for msg in messages:
            msg_type = msg.get("message_type", "info").upper()
            text = msg.get("message_text", "")
            created = msg.get("created_at", "")
            
            # Color by type
            if msg_type == "DELAY":
                st.warning(f"⚠️ **Delay Alert** — {text}\n\n*{created}*")
            elif msg_type == "DELIVERED":
                st.success(f"✅ **Delivered** — {text}\n\n*{created}*")
            elif msg_type == "CANCELLED":
                st.error(f"🚫 **Cancelled** — {text}\n\n*{created}*")
            else:
                st.info(f"ℹ️ **Message** — {text}\n\n*{created}*")

# ======================================================================
# TAB 4: ORDER HISTORY — Past orders + Reorder + Feedback
# ======================================================================

with tab4:
    st.subheader("Order History")
    
    try:
        past_orders = sb.table("orders") \
            .select("id, status, created_at, weight_kg, window_start") \
            .eq("customer_name", customer) \
            .in_("status", ["delivered", "failed", "cancelled"]) \
            .order("created_at", desc=True) \
            .execute().data
    except Exception as e:
        st.error(f"Could not load history: {e}")
        past_orders = []
    
    if not past_orders:
        st.info("No past orders yet.")
    else:
        for order in past_orders:
            status_emoji = {
                "delivered": "✅",
                "failed": "❌",
                "cancelled": "🚫",
            }.get(order["status"], "❓")
            
            with st.expander(
                f"{status_emoji} Order #{order['id']} — {order['status'].title()} "
                f"({order['created_at'][:10]})"
            ):
                col1, col2 = st.columns(2)
                col1.write(f"**Weight:** {order['weight_kg']} kg")
                col2.write(f"**Window:** {order['window_start']}")
                
                # Reorder button
                if order["status"] == "delivered":
                    if st.button(f"Reorder #{order['id']}", key=f"reorder_{order['id']}"):
                        st.info("✅ Same order set for tomorrow. Check 'Place Order' tab to confirm.")
                
                # Feedback (only for delivered orders)
                if order["status"] == "delivered":
                    st.markdown("---")
                    st.write("**How was your delivery?**")
                    
                    col1, col2 = st.columns([1, 3])
                    rating = col1.slider("Rating", 1, 5, 4, key=f"rating_{order['id']}")
                    comment = col2.text_area(
                        "Comment (optional)",
                        key=f"comment_{order['id']}",
                        height=60
                    )
                    
                    if st.button("Submit feedback", key=f"feedback_{order['id']}"):
                        try:
                            # Check if feedback already exists
                            existing = sb.table("feedback") \
                                .select("id") \
                                .eq("order_id", order["id"]) \
                                .eq("customer_name", customer) \
                                .execute().data
                            
                            if existing:
                                st.info("Feedback already submitted for this order.")
                            else:
                                sb.table("feedback").insert({
                                    "order_id": order["id"],
                                    "customer_name": customer,
                                    "rating": int(rating),
                                    "comment": comment.strip(),
                                }).execute()
                                st.success("✅ Thank you for your feedback!")
                        except Exception as e:
                            st.error(f"Could not save feedback: {str(e)[:100]}")

# ======================================================================
# FOOTER
# ======================================================================

st.divider()
st.caption(
    "**Privacy note:** This demo scopes your data by name only (not secure). "
    "In production, Supabase Auth + RLS would enforce real access control. "
    "Even here, the page never fetches another customer's orders—it's a scoping discipline exercise."
)