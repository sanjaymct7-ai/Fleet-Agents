"""Synthetic order generator — Phase 2, step 1."""
import random
from dataclasses import dataclass
from datetime import datetime, timedelta

# --- 1) Your city's bounding box: REPLACE with numbers from bboxfinder.com ---
LAT_MIN, LAT_MAX = 0.0, 0.0     # south edge, north edge
LNG_MIN, LNG_MAX = 0.0, 0.0     # west edge, east edge

def random_point() -> tuple[float, float]:
    """A random (lat, lng) inside the city rectangle."""
    return (
        round(random.uniform(LAT_MIN, LAT_MAX), 6),
        round(random.uniform(LNG_MIN, LNG_MAX), 6),
    )

# --- 2) The shape of an order (mirrors the `orders` table) ---
@dataclass
class Order:
    customer_name: str
    customer_tier: str
    pickup_lat: float
    pickup_lng: float
    drop_lat: float
    drop_lng: float
    window_start: datetime
    window_end: datetime
    weight_kg: float
    priority: int

def make_order() -> Order:
    pickup = random_point()
    drop = random_point()
    # deliveries happen "tomorrow", in a random 3-hour window between 9:00-18:00
    day = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    start_hour = random.randint(9, 15)
    return Order(
        customer_name=f"Customer {random.randint(100, 999)}",
        customer_tier=random.choices(
            ["standard", "premium", "enterprise"], weights=[70, 20, 10]
        )[0],
        pickup_lat=pickup[0], pickup_lng=pickup[1],
        drop_lat=drop[0],   drop_lng=drop[1],
        window_start=day + timedelta(hours=start_hour),
        window_end=day + timedelta(hours=start_hour + 3),
        weight_kg=round(random.uniform(1, 80), 1),
        priority=random.choices([1, 2, 3, 4, 5], weights=[5, 15, 40, 25, 15])[0],
    )

if __name__ == "__main__":
    for _ in range(3):
        print(make_order(), "\n")