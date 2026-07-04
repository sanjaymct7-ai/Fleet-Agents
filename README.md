# Fleet Agents — Multi-Agent Logistics Dispatcher (₹0 stack)

A learning project: 8 AI agents that plan delivery routes, dispatch drivers,
handle live exceptions, and escalate risky decisions to a human — built entirely
on free tiers (Streamlit Cloud + Supabase + Gemini/Groq free APIs + OR-Tools).

**Phase 1 (this scaffold):** deploy a hello-world dashboard, create the database,
and verify every connection works — before writing any agent.

---

## Setup steps (do these in order)

### Step 1 — Get your free API keys (no credit card for any of these)
1. **Gemini**: go to https://aistudio.google.com → "Get API key" → create key. Copy it.
2. **Groq**: go to https://console.groq.com → API Keys → create. Copy it.
3. **OpenRouteService** (for travel times, used in Phase 2): https://openrouteservice.org
   → sign up → get a free token. Copy it.

Keep these in a private note for now. NEVER paste them into any file in this repo.

### Step 2 — Create the Supabase database
1. Log in at https://supabase.com → New project (free tier).
   Pick a strong DB password and save it somewhere safe.
2. In the left sidebar open **SQL Editor** → New query.
3. Open `db/schema_phase1.sql` from this repo, read the comments (this is your
   first SQL lesson), paste the whole file into the editor, press **Run**.
4. Sidebar → **Table Editor** → you should now see 4 tables:
   `drivers`, `orders`, `routes`, `route_stops`.
5. Sidebar → **Project Settings → API**. Copy two values:
   - `Project URL`
   - `anon public` API key
   (We'll switch to stricter per-agent credentials in a later phase.)

### Step 3 — Put this code on GitHub
1. Create a GitHub account if you don't have one → New repository →
   name it `fleet-agents` → **Public** (Streamlit's free hosting requires public).
2. On your laptop (install git + Python 3.11+ first):
   ```bash
   cd fleet-agents
   git init
   git add .
   git commit -m "Phase 1 scaffold"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/fleet-agents.git
   git push -u origin main
   ```
3. IMPORTANT: check on github.com that there is NO `secrets.toml` file visible.
   Only `secrets.toml.example` should be there. The real one is blocked by
   `.gitignore`.

### Step 4 — Deploy on Streamlit Community Cloud
1. Go to https://share.streamlit.io → sign in with GitHub → **New app**.
2. Pick your `fleet-agents` repo, branch `main`, main file `app.py` → Deploy.
3. While it builds: open the app's **Settings → Secrets** and paste the contents
   of `.streamlit/secrets.toml.example`, replacing the placeholder values with
   your real keys from Steps 1–2. Save.
4. Reboot the app. You now have a live URL you can open from your phone.

### Step 5 — Verify everything
Open your deployed app. The Setup Check page should show:
- ✅ for all four secrets found
- ✅ Supabase connected, 4 tables reachable, seed driver row visible
- Press "Test Gemini" once → you should get a one-line reply.
  (Don't spam it — free tier has daily limits.)

When everything is green, Phase 1 is done. Phase 2 = order generator +
Intake agent + OR-Tools route planner.

---

## Run locally too (recommended for development)
```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # then fill in real keys
streamlit run app.py
```
Local workflow: edit code → test at http://localhost:8501 → `git push` →
Streamlit Cloud redeploys automatically in ~1 minute.

## Repo layout
```
app.py                        Streamlit entry point (Setup Check page)
requirements.txt              Python dependencies (kept minimal for Phase 1)
db/schema_phase1.sql          The 4 starter tables, commented line by line
src/db.py                     Supabase connection helper
.streamlit/secrets.toml.example  Template for secrets (real file is git-ignored)
.gitignore                    Blocks secrets + junk from reaching GitHub
```

## Security rules for this repo (read once, follow forever)
1. Real keys live ONLY in `.streamlit/secrets.toml` (local) and the Streamlit
   Cloud Secrets panel (hosted). Nowhere else.
2. If a key ever lands in a git commit, treat it as leaked: delete the key in
   the provider's console and create a new one. (Deleting the commit is not enough.)
3. The `anon` Supabase key is temporary training wheels. A later phase replaces
   it with least-privilege credentials per agent.



## Stretch goals (not on critical path)

- **Vector memory (Chroma + HuggingFace)** — planned for a later phase.
  Goal: let the Recovery agent recall how similar past exceptions were
  resolved. Not required for Phase 1 or Phase 2 to work.
