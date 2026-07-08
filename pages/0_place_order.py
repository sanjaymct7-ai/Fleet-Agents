"""Customer-facing order placement page — structured form, no free text.
Customer picks from known locations; no LLM parsing needed."""
from datetime import date, datetime, time, timedelta

import streamlit as st

from src.intake_agent import PLACES, create_order

st.set_page_config(page_title="Place an Order", page_icon="📦", layout="centered")
st.title("📦 Place a Delivery Order")
st.caption("Fill in your delivery details below.")

place_names = sorted(PLACES.keys())

with st.form("place_order"):
    st.subheader("Your details")
    customer_name = st.text_input("Your name")
    customer_tier = st.selectbox("Account type", ["standard", "premium", "enterprise"])

    st.subheader("Delivery details")
    col1, col2 = st.columns(2)
    pickup_place = col1.selectbox("Pickup location", place_names)
    drop_place = col2.selectbox("Drop-off location", place_names)

    weight_kg = st.number_input("Package weight (kg)", min_value=0.1, max_value=500.0,
                                 value=5.0, step=0.5)

    st.subheader("Delivery window")
    col3, col4 = st.columns(2)
    delivery_date = col3.date_input("Date", value=date.today() + timedelta(days=1),
                                     min_value=date.today())
    time_slot = col4.selectbox("Preferred time window", [
        "09:00–12:00", "12:00–15:00", "15:00–18:00",
    ])

    submitted = st.form_submit_button("Submit order", type="primary")

if submitted:
    if not customer_name.strip():
        st.error("Please enter your name.")
    elif pickup_place == drop_place:
        st.error("Pickup and drop-off locations must be different.")
    else:
        start_hour, end_hour = {
            "09:00–12:00": (9, 12),
            "12:00–15:00": (12, 15),
            "15:00–18:00": (15, 18),
        }[time_slot]
        window_start = datetime.combine(delivery_date, time(start_hour, 0))
        window_end = datetime.combine(delivery_date, time(end_hour, 0))

        pickup_lat, pickup_lng = PLACES[pickup_place]
        drop_lat, drop_lng = PLACES[drop_place]

        row = {
            "customer_name": customer_name.strip(),
            "customer_tier": customer_tier,
            "pickup_lat": pickup_lat, "pickup_lng": pickup_lng,
            "drop_lat": drop_lat, "drop_lng": drop_lng,
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "weight_kg": float(weight_kg),
            "source": "manual",
        }
        saved = create_order(row)
        st.success(f"✅ Order #{saved['id']} confirmed! "
                   f"Pickup from **{pickup_place}**, drop-off at **{drop_place}**, "
                   f"on {delivery_date} between {time_slot}.")
        st.balloons()