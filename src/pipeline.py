"""
Module 7a - Unified inference pipeline.

Loads the trained RUL model and exposes a single function that
takes a battery and returns the full analysis:
  chemistry -> SoH -> RUL -> decision -> materials -> centre -> carbon
"""

import joblib
import numpy as np
from pathlib import Path

from decision_engine import BatteryState, decide
from material_extraction import extract_materials
from routing import recommend_centres
from carbon import carbon_avoided, carbon_breakdown

MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "rul_model.pkl"
_model = None
_meta = None


def load_model():
    global _model, _meta
    if _model is None:
        payload = joblib.load(MODEL_PATH)
        _model = payload["model"]
        _meta = {"features": payload["features"], "name": payload["name"]}
    return _model, _meta


def predict_rul(cycle, voltage, temperature, capacity, soh):
    """
    Physics-informed RUL estimate.

    The Random Forest model was trained on a small (34-battery) dataset
    with a narrow feature range and does not extrapolate to real-world
    battery cycle counts. This function uses a degradation curve instead.
    """
    soh = float(soh)
    if soh >= 80.0:
        rul = 1000 + (soh - 80.0) * 50.0
    elif soh >= 60.0:
        rul = (soh - 60.0) * 50.0
    elif soh >= 40.0:
        rul = (soh - 40.0) * 10.0
    else:
        rul = 0.0

    temp = float(temperature)
    if temp > 40.0:
        rul *= max(0.5, 1.0 - (temp - 40.0) * 0.02)

    return max(0, int(round(rul)))


# Mapping from material_extraction.py keys to carbon factor keys
KEY_MAP = {
    "Li":       "li_kg",
    "Co":       "co_kg",
    "Ni":       "ni_kg",
    "Cu":       "cu_kg",
    "Al":       "al_kg",
    "Graphite": "graphite_kg",
}


def analyse_battery(battery_id, chemistry, capacity_kwh, weight_kg,
                    cycle, voltage, temperature, capacity, soh,
                    safe=True, damaged=False,
                    lat=13.0827, lon=80.2707):
    rul = predict_rul(cycle, voltage, temperature, capacity, soh)

    state = BatteryState(
        battery_id=battery_id,
        chemistry=chemistry,
        soh=soh,
        rul=rul,
        cycle_count=cycle,
        safe=safe,
        damaged=damaged,
    )
    decision = decide(state)

    materials = None
    centres = []
    carbon_kg = 0.0
    carbon_rows = []

    if decision.action.startswith("RECYCLE"):
        materials = extract_materials(chemistry, weight_kg)
        centres = recommend_centres(lat, lon, chemistry, weight_kg, top_n=3)

        # Build a {carbon_key: recovered_kg} map, skipping materials not
        # present in this chemistry (e.g. LFP has no Co or Ni)
        recovered_map = {}
        for mat_name, data in materials["recoverable"].items():
            carbon_key = KEY_MAP.get(mat_name)
            if carbon_key:
                recovered_map[carbon_key] = data["recovered_kg"]

        carbon_kg = carbon_avoided(recovered_map)
        carbon_rows = carbon_breakdown(recovered_map)

    return {
        "battery_id": battery_id,
        "chemistry": chemistry,
        "capacity_kwh": capacity_kwh,
        "weight_kg": weight_kg,
        "cycle": cycle,
        "voltage": voltage,
        "temperature": temperature,
        "capacity": capacity,
        "soh": soh,
        "rul": rul,
        "decision": decision.action,
        "confidence": decision.confidence,
        "reasons": decision.reasons,
        "materials": materials,
        "centres": centres,
        "carbon_avoided_kg": carbon_kg,
        "carbon_breakdown": carbon_rows,
        "model_name": "Physics-based (SoH curve)",
    }


if __name__ == "__main__":
    import json
    r = analyse_battery(
        battery_id="EVB-IN-000245",
        chemistry="LFP",
        capacity_kwh=45,
        weight_kg=320,
        cycle=1420, voltage=3.75, temperature=28,
        capacity=32, soh=30,
    )
    print(json.dumps(r, indent=2, default=str))