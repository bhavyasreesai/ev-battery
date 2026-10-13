"""
Module C - Batch processing page.

Upload a CSV of batteries -> analyse each one -> download results CSV.

CSV columns required:
  battery_id, chemistry, capacity_kwh, weight_kg, cycle, voltage,
  temperature, capacity, soh, safe, damaged

Also provides a "Download template CSV" button that generates a small
sample file with the correct format.
"""

import sys
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import streamlit as st
import pandas as pd

from pipeline import analyse_battery
from history import log_analysis

st.set_page_config(
    page_title="Batch Processing",
    page_icon="B",
    layout="wide",
)

st.title("Batch Processing - Analyse Many Batteries at Once")
st.caption("Upload a CSV of batteries. Get decisions, RUL, CO2 avoided and "
           "recommended centres for each one.")

# ------------------------------------------------------------
# Template CSV
# ------------------------------------------------------------
TEMPLATE_ROWS = [
    {
        "battery_id":    "EVB-IN-000001",
        "chemistry":     "LFP",
        "capacity_kwh":  45.0,
        "weight_kg":     320.0,
        "cycle":         1420,
        "voltage":       3.75,
        "temperature":   28,
        "capacity":      32.0,
        "soh":           30.0,
        "safe":          True,
        "damaged":       False,
    },
    {
        "battery_id":    "EVB-IN-000002",
        "chemistry":     "NMC",
        "capacity_kwh":  60.0,
        "weight_kg":     400.0,
        "cycle":         800,
        "voltage":       3.85,
        "temperature":   30,
        "capacity":      45.0,
        "soh":           72.0,
        "safe":          True,
        "damaged":       False,
    },
    {
        "battery_id":    "EVB-IN-000003",
        "chemistry":     "LFP",
        "capacity_kwh":  50.0,
        "weight_kg":     350.0,
        "cycle":         500,
        "voltage":       3.95,
        "temperature":   26,
        "capacity":      44.0,
        "soh":           88.0,
        "safe":          True,
        "damaged":       False,
    },
]

template_df = pd.DataFrame(TEMPLATE_ROWS)
template_csv = template_df.to_csv(index=False).encode("utf-8")

st.download_button(
    label="Download template CSV",
    data=template_csv,
    file_name="batch_template.csv",
    mime="text/csv",
    help="Grab this first. Fill in your own rows, then upload.",
)

st.markdown("---")

# ------------------------------------------------------------
# Upload
# ------------------------------------------------------------
uploaded = st.file_uploader("Upload battery CSV", type=["csv"])

if uploaded is None:
    st.info("Upload a CSV to get started. Use the template above if unsure.")
    st.stop()

try:
    df_in = pd.read_csv(uploaded)
except Exception as e:
    st.error(f"Could not read CSV: {e}")
    st.stop()

REQUIRED_COLS = [
    "battery_id", "chemistry", "capacity_kwh", "weight_kg",
    "cycle", "voltage", "temperature", "capacity", "soh",
]
missing = [c for c in REQUIRED_COLS if c not in df_in.columns]
if missing:
    st.error(f"CSV missing required columns: {missing}")
    st.stop()

# Normalize boolean-ish columns
for col in ["safe", "damaged"]:
    if col not in df_in.columns:
        df_in[col] = False

def to_bool(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in ("true", "1", "yes", "y", "t")
    return bool(v)

st.success(f"Loaded {len(df_in)} batteries from {uploaded.name}")

# ------------------------------------------------------------
# Process each row
# ------------------------------------------------------------
st.subheader("Processing...")

results = []
progress = st.progress(0.0)
total = len(df_in)

for i, row in df_in.iterrows():
    try:
        r = analyse_battery(
            battery_id=str(row["battery_id"]),
            chemistry=str(row["chemistry"]),
            capacity_kwh=float(row["capacity_kwh"]),
            weight_kg=float(row["weight_kg"]),
            cycle=int(row["cycle"]),
            voltage=float(row["voltage"]),
            temperature=float(row["temperature"]),
            capacity=float(row["capacity"]),
            soh=float(row["soh"]),
            safe=to_bool(row.get("safe", True)),
            damaged=to_bool(row.get("damaged", False)),
        )
        log_analysis(r, source="batch")
        top_centre = r["centres"][0]["centre_name"] if r.get("centres") else "-"
        results.append({
            "battery_id":   r["battery_id"],
            "chemistry":    r["chemistry"],
            "soh":          round(r["soh"], 1),
            "rul":          r["rul"],
            "decision":     r["decision"],
            "confidence":   round(r["confidence"], 2),
            "carbon_kg":    r["carbon_avoided_kg"],
            "top_centre":   top_centre,
        })
    except Exception as e:
        results.append({
            "battery_id":   row.get("battery_id", "-"),
            "chemistry":    row.get("chemistry", "-"),
            "soh":          None,
            "rul":          None,
            "decision":     f"ERROR: {e}",
            "confidence":   None,
            "carbon_kg":    None,
            "top_centre":   "-",
        })
    progress.progress((i + 1) / total)

progress.empty()
st.success(f"Processed {total} batteries.")

out_df = pd.DataFrame(results)

# ------------------------------------------------------------
# Summary stats
# ------------------------------------------------------------
st.markdown("---")
st.subheader("Summary")

counts = out_df["decision"].value_counts().to_dict()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total batteries", f"{total:,}")
c2.metric("CONTINUE_EV",    f"{counts.get('CONTINUE_EV', 0):,}")
c3.metric("RECYCLE",        f"{counts.get('RECYCLE', 0) + counts.get('RECYCLE_HAZARDOUS', 0):,}")
c4.metric("Total CO2 avoided", f"{out_df['carbon_kg'].fillna(0).sum():,.0f} kg")

st.markdown("**Full decision breakdown:**")
for d, n in sorted(counts.items()):
    st.write(f"- {d}: {n}")

# ------------------------------------------------------------
# Results table + download
# ------------------------------------------------------------
st.markdown("---")
st.subheader("Results")
st.dataframe(out_df, width="stretch", hide_index=True)

results_csv = out_df.to_csv(index=False).encode("utf-8")
st.download_button(
    label="Download results CSV",
    data=results_csv,
    file_name="batch_results.csv",
    mime="text/csv",
)
st.caption(
    "Columns: battery_id, chemistry, soh, rul, decision, confidence, "
    "carbon_kg, top_centre."
)