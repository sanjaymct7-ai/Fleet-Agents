"""
Single place that creates the Supabase client.

Why a helper module instead of creating the client inside app.py?
Because in later phases EVERY agent's tools will get their database
connection from here — and when we introduce per-agent least-privilege
credentials, we change it in exactly one file:

    get_client(agent="order_intake")  ->  connection that can ONLY
                                          insert into `orders`.

For Phase 1 there is just one shared, read-mostly client using the
public `anon` key. Treat that as training wheels.
"""

import streamlit as st
from supabase import Client, create_client


@st.cache_resource  # create once per app process, reuse across reruns
def get_client() -> Client:
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_ANON_KEY"],
    )
