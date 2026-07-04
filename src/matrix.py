"""Step 2.4a — travel-time matrix: cache -> Geoapify -> haversine fallback."""
import math

import httpx
import streamlit as st

from src.db import get_client

DEPOT = (54.973952286846284, -1.613073169429368)        # keep YOUR depot point here
ROAD_FACTOR = 1.4
AVG_SPEED_KMH = 25


# ---------- fallback: haversine (kept from before) ----------
def haversine_km(a, b):
    R = 6371
    lat1, lng1, lat2, lng2 = map(math.radians, [a[0], a[1], b[0], b[1]])
    dlat, dlng = lat2 - lat1, lng2 - lng1
    h = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlng/2)**2
    return 2 * R * math.asin(math.sqrt(h))


def fallback_minutes(a, b):
    return round(haversine_km(a, b) * ROAD_FACTOR / AVG_SPEED_KMH * 60)


# ---------- cache helpers ----------
def pair_key(a, b):
    return f"{a[0]:.5f},{a[1]:.5f}->{b[0]:.5f},{b[1]:.5f}"


def load_cache(sb) -> dict:
    rows = sb.table("travel_cache").select("pair_key, minutes").execute().data
    return {r["pair_key"]: r["minutes"] for r in rows}


def save_cache(sb, entries: dict):
    rows = [{"pair_key": k, "minutes": v} for k, v in entries.items()]
    if rows:
        sb.table("travel_cache").upsert(rows).execute()


# ---------- the real thing: Geoapify Route Matrix ----------
def geoapify_matrix(coords: list[tuple]) -> list[list[int]]:
    """One API call: full NxN drive-time matrix, in minutes.
    NOTE Geoapify wants [lng, lat] — reversed from how we store!"""
    locations = [{"location": [c[1], c[0]]} for c in coords]
    resp = httpx.post(
        f"https://api.geoapify.com/v1/routematrix?apiKey={st.secrets['GEOAPIFY_API_KEY']}",
        json={"mode": "drive", "sources": locations, "targets": locations},
        timeout=60,
    )
    resp.raise_for_status()
    n = len(coords)
    matrix = [[0] * n for _ in range(n)]
    for cell in resp.json()["sources_to_targets"]:
        for entry in cell:
            i, j = entry["source_index"], entry["target_index"]
            secs = entry.get("time")
            matrix[i][j] = round(secs / 60) if secs is not None else fallback_minutes(
                coords[i], coords[j])
    return matrix


# ---------- orchestration: cache first, API second, fallback last ----------
def get_matrix(stops: list[dict]) -> list[list[int]]:
    sb = get_client()
    coords = [s["coord"] for s in stops]
    n = len(coords)
    cache = load_cache(sb)
    keys = [[pair_key(coords[i], coords[j]) for j in range(n)] for i in range(n)]

    if all(keys[i][j] in cache for i in range(n) for j in range(n) if i != j):
        print("[matrix] fully served from cache — 0 credits spent")
        return [[0 if i == j else cache[keys[i][j]] for j in range(n)] for i in range(n)]

    try:
        print(f"[matrix] calling Geoapify for {n}x{n} (~{max(n,n)*min(n,10)} credits)")
        matrix = geoapify_matrix(coords)
        save_cache(sb, {keys[i][j]: matrix[i][j]
                        for i in range(n) for j in range(n) if i != j})
        print("[matrix] cached for next time")
        return matrix
    except Exception as e:
        print(f"[matrix] Geoapify failed ({type(e).__name__}) — haversine fallback")
        return [[0 if i == j else fallback_minutes(coords[i], coords[j])
                 for j in range(n)] for i in range(n)]


def load_stops() -> list[dict]:
    orders = (get_client().table("orders")
              .select("id, drop_lat, drop_lng, weight_kg, window_start, window_end")
              .eq("status", "new").execute().data)
    stops = [{"order_id": None, "coord": DEPOT}]
    for o in orders:
        stops.append({"order_id": o["id"],
                      "coord": (float(o["drop_lat"]), float(o["drop_lng"])),
                      "weight_kg": float(o["weight_kg"]),
                      "window": (o["window_start"], o["window_end"])})
    return stops


if __name__ == "__main__":
    stops = load_stops()
    m = get_matrix(stops)
    print(f"{len(stops)} stops (incl. depot). Matrix is {len(m)}x{len(m)}.")
    print("Depot -> first 5 stops (minutes):", m[0][1:6])
    print("Longest single hop:", max(max(row) for row in m), "minutes")