"""Geocoding helper using Geoapify API.
Converts addresses to lat/lng coordinates."""
import requests
import streamlit as st

GEOAPIFY_API_KEY = st.secrets.get("GEOAPIFY_API_KEY")
GEOAPIFY_URL = "https://api.geoapify.com/v1/geocode/search"


def geocode_address(address: str) -> tuple[float, float] | None:
    """Convert address string to (lat, lng) using Geoapify.
    Returns None if geocoding fails."""
    if not address or not address.strip():
        return None
    
    try:
        response = requests.get(
            GEOAPIFY_URL,
            params={
                "text": address.strip(),
                "apiKey": GEOAPIFY_API_KEY,
                "limit": 1
            },
            timeout=5
        )
        response.raise_for_status()
        data = response.json()
        
        if data.get("features") and len(data["features"]) > 0:
            feature = data["features"][0]
            lat = feature["properties"]["lat"]
            lng = feature["properties"]["lon"]
            return (lat, lng)
        return None
    except Exception as e:
        print(f"Geocoding error for '{address}': {e}")
        return None


def reverse_geocode(lat: float, lng: float) -> str | None:
    """Convert (lat, lng) to human-readable address using Geoapify.
    Returns None if reverse geocoding fails."""
    try:
        response = requests.get(
            "https://api.geoapify.com/v1/geocode/reverse",
            params={
                "lat": lat,
                "lon": lng,
                "apiKey": GEOAPIFY_API_KEY
            },
            timeout=5
        )
        response.raise_for_status()
        data = response.json()
        
        if data.get("features") and len(data["features"]) > 0:
            feature = data["features"][0]
            return feature["properties"]["formatted"]
        return None
    except Exception as e:
        print(f"Reverse geocoding error for ({lat}, {lng}): {e}")
        return None