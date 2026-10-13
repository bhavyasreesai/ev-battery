"""
Module 5 - Recycling centre routing.

Given a battery's location + chemistry, rank candidate recycling
centres by a weighted score combining:
  - chemistry capability match
  - distance
  - available capacity
  - cost factor
"""

import math
from dataclasses import dataclass
from typing import List, Dict


# Sample recycling centres (would be a real DB in production)
CENTRES = [
    {
        "id": "RC-001", "name": "Mumbai Li-Cycle Hub",
        "lat": 19.0760, "lon": 72.8777,
        "chemistries": ["NMC", "NCA", "LMO"],
        "capacity_kg_day": 5000, "current_load_kg": 1200,
        "cost_factor": 1.0,
    },
    {
        "id": "RC-002", "name": "Chennai LFP Recovery",
        "lat": 13.0827, "lon": 80.2707,
        "chemistries": ["LFP", "LMO"],
        "capacity_kg_day": 3000, "current_load_kg": 800,
        "cost_factor": 0.9,
    },
    {
        "id": "RC-003", "name": "Delhi NCR Battery Recyclers",
        "lat": 28.7041, "lon": 77.1025,
        "chemistries": ["NMC", "LFP", "NCA", "LMO"],
        "capacity_kg_day": 8000, "current_load_kg": 5000,
        "cost_factor": 1.1,
    },
    {
        "id": "RC-004", "name": "Bengaluru Attero Facility",
        "lat": 12.9716, "lon": 77.5946,
        "chemistries": ["NMC", "NCA"],
        "capacity_kg_day": 4000, "current_load_kg": 600,
        "cost_factor": 1.0,
    },
    {
        "id": "RC-005", "name": "Pune Lohum Plant",
        "lat": 18.5204, "lon": 73.8567,
        "chemistries": ["NMC", "LFP", "NCA", "LMO"],
        "capacity_kg_day": 6000, "current_load_kg": 3000,
        "cost_factor": 0.95,
    },
]

# Weights (tune per policy: environmental vs cost priority)
W_DISTANCE = 0.5
W_CAPABILITY = 0.3
W_CAPACITY = 0.1
W_COST = 0.1

MAX_DISTANCE_KM = 2000.0   # normalisation reference


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = (math.sin(dp/2)**2 +
         math.cos(p1) * math.cos(p2) * math.sin(dl/2)**2)
    return 2 * R * math.asin(math.sqrt(a))


def score_centre(battery_lat, battery_lon, chemistry,
                 weight_kg, centre):
    # Capability
    capability = 1.0 if chemistry.upper() in centre["chemistries"] else 0.0

    # Distance
    dist_km = haversine_km(battery_lat, battery_lon,
                           centre["lat"], centre["lon"])
    distance_score = max(0.0, 1.0 - dist_km / MAX_DISTANCE_KM)

    # Capacity (available fraction)
    available = centre["capacity_kg_day"] - centre["current_load_kg"]
    if available < weight_kg:
        capacity_score = 0.0   # cannot fit today
    else:
        capacity_score = min(1.0, available / centre["capacity_kg_day"])

    # Cost (lower factor is better; invert)
    cost_score = 1.0 / centre["cost_factor"]

    total = (W_DISTANCE * distance_score +
             W_CAPABILITY * capability +
             W_CAPACITY * capacity_score +
             W_COST * cost_score)

    # Hard rule: if chemistry not supported, disqualify
    if capability == 0.0:
        total = 0.0

    return {
        "centre_id": centre["id"],
        "centre_name": centre["name"],
        "distance_km": round(dist_km, 1),
        "capability": capability,
        "capacity_score": round(capacity_score, 3),
        "cost_factor": centre["cost_factor"],
        "score": round(total, 3),
    }


def recommend_centres(battery_lat, battery_lon, chemistry,
                      weight_kg, top_n=3):
    scored = [score_centre(battery_lat, battery_lon, chemistry,
                           weight_kg, c) for c in CENTRES]
    scored = [s for s in scored if s["score"] > 0]
    scored.sort(key=lambda s: s["score"], reverse=True)
    return scored[:top_n]


def format_recommendations(chemistry, weight_kg, battery_lat, battery_lon,
                           recs):
    print(f"\nBattery at ({battery_lat}, {battery_lon}) | "
          f"chemistry={chemistry} | weight={weight_kg} kg")
    print("-" * 70)
    if not recs:
        print("No suitable centre found (chemistry unsupported).")
        return
    print(f"{'Rank':<5}{'Centre':<30}{'Dist(km)':>10}"
          f"{'Cap':>6}{'Cost':>6}{'Score':>8}")
    print("-" * 70)
    for i, r in enumerate(recs, 1):
        print(f"{i:<5}{r['centre_name']:<30}"
              f"{r['distance_km']:>10.1f}"
              f"{r['capability']:>6.1f}"
              f"{r['cost_factor']:>6.2f}"
              f"{r['score']:>8.3f}")


if __name__ == "__main__":
    # Chennai-based NMC battery
    recs = recommend_centres(13.0827, 80.2707, "NMC", 300)
    format_recommendations("NMC", 300, 13.0827, 80.2707, recs)

    # Delhi-based LFP battery
    recs = recommend_centres(28.7041, 77.1025, "LFP", 200)
    format_recommendations("LFP", 200, 28.7041, 77.1025, recs)

    # Random location NCA
    recs = recommend_centres(21.1458, 79.0882, "NCA", 350)
    format_recommendations("NCA", 350, 21.1458, 79.0882, recs)
