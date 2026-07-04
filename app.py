"""
Phase 1 — Setup Check dashboard.

One page that proves every piece of the free stack is wired up:
secrets present, Supabase reachable, tables created, Gemini answering.
Later phases will add real pages (map, exceptions, approvals) alongside this.
"""

import streamlit as st

st.set_page_config(page_title="Fleet Agents — Setup Check", page_icon="🚚", layout="wide")
st.title("🚚 Fleet Agents — Phase 1 Setup Check")
st.caption("If everything below is green, the foundation is ready for the agents.")

# ----------------------------------------------------------------------
# 1) Secrets check — are the keys configured?
#    Locally these come from .streamlit/secrets.toml
#    On Streamlit Cloud they come from the app's Secrets panel.
# ----------------------------------------------------------------------
st.header("1. Secrets")

REQUIRED_SECRETS = {
    "SUPABASE_URL": "Supabase → Project Settings → API → Project URL",
    "SUPABASE_ANON_KEY": "Supabase → Project Settings → API → anon public key",
    "GEMINI_API_KEY": "https://aistudio.google.com → Get API key",
    "GROQ_API_KEY": "https://console.groq.com → API Keys",
}

missing = []
for key, where in REQUIRED_SECRETS.items():
    if key in st.secrets and st.secrets[key] and "PASTE_" not in str(st.secrets[key]):
        st.success(f"✅ `{key}` found")
    else:
        st.error(f"❌ `{key}` missing — get it from: {where}")
        missing.append(key)

# ----------------------------------------------------------------------
# 2) Database check — can we reach Supabase and see our tables?
# ----------------------------------------------------------------------
st.header("2. Supabase database")

if "SUPABASE_URL" in missing or "SUPABASE_ANON_KEY" in missing:
    st.warning("Add the Supabase secrets first, then reload this page.")
else:
    try:
        from src.db import get_client

        sb = get_client()
        tables = ["drivers", "orders", "routes", "route_stops"]
        cols = st.columns(len(tables))
        for col, table in zip(cols, tables):
            try:
                # count='exact', head=True asks only for the row count — cheap.
                res = sb.table(table).select("*", count="exact", head=True).execute()
                col.metric(label=f"table: {table}", value=f"{res.count} rows")
            except Exception as e:  # table missing or RLS issue
                col.error(f"❌ {table}")
                col.caption(str(e)[:120])

        st.subheader("Seed data read test")
        drivers = sb.table("drivers").select("id, name, status").limit(5).execute()
        if drivers.data:
            st.success("✅ Read from `drivers` works:")
            st.table(drivers.data)
        else:
            st.warning(
                "Connected, but `drivers` is empty. Did you run db/schema_phase1.sql "
                "in the Supabase SQL Editor (it seeds one test driver)?"
            )
    except Exception as e:
        st.error(f"❌ Could not connect to Supabase: {e}")
        st.caption(
            "Check the URL/key, and note free Supabase projects pause after "
            "~7 days idle — open the Supabase dashboard and click Resume."
        )

# ----------------------------------------------------------------------
# 3) LLM check — one manual test call to Gemini.
#    Behind a button on purpose: free tiers have daily quotas and we
#    never want a page refresh to silently burn them.
# ----------------------------------------------------------------------
st.header("3. Gemini (free tier)")

if "GEMINI_API_KEY" in missing:
    st.warning("Add GEMINI_API_KEY first.")
else:
    st.caption("Press once to verify — don't spam it, the free tier has daily limits.")
    if st.button("Test Gemini"):
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI

            llm = ChatGoogleGenerativeAI(
                model="gemini-2.5-flash",
                google_api_key=st.secrets["GEMINI_API_KEY"],
                temperature=0,
            )
            reply = llm.invoke(
                "Reply with exactly one short sentence confirming you are reachable."
            )
            st.success(f"✅ Gemini replied: {reply.content}")
        except Exception as e:
            st.error(f"❌ Gemini call failed: {e}")
            st.caption(
                "If this is a quota error (429), wait a bit — and this is exactly "
                "why we also have a Groq key as fallback for later phases."
            )

st.divider()
st.info(
    "**All green?** Phase 1 complete. Next up (Phase 2): the synthetic order "
    "generator, the Order Intake agent (first real LLM tool use), and the "
    "OR-Tools route planner drawing routes on a map."
)
