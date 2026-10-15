
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

DB_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "battery_passport.db"
)

st.set_page_config(
    page_title="Buyer",
    layout="wide",
)

st.title("Buyer")
st.caption("Monitor your batteries, health, maintenance, and lifecycle.")

if not DB_PATH.exists():
    st.error("Battery database not found. Please check the existing project data.")
    st.stop()


def read_query(query, params=()):
    with sqlite3.connect(DB_PATH) as con:
        return pd.read_sql_query(query, con, params=params)


# Read-only view of the existing battery records
batteries = read_query(
    """
    SELECT battery_id, chemistry, capacity_kwh, weight_kg,
           manufacturer, current_owner, current_location
    FROM batteries
    ORDER BY battery_id
    """
)

if batteries.empty:
    st.info("No batteries are registered yet.")
    st.stop()

# Select a buyer based on existing ownership data
owners = sorted(
    batteries["current_owner"].dropna().astype(str).unique().tolist()
)

selected_owner = st.selectbox("Select Buyer / Current Owner", owners)

owned = batteries[
    batteries["current_owner"].astype(str) == selected_owner
].copy()

st.subheader("Your Battery Portfolio")

k1, k2 = st.columns(2)
k1.metric("Batteries Owned", len(owned))
k2.metric(
    "Battery Types",
    owned["chemistry"].nunique() if not owned.empty else 0,
)

st.dataframe(owned, hide_index=True, use_container_width=True)

if owned.empty:
    st.info("No batteries are assigned to this owner.")
    st.stop()

selected_id = st.selectbox(
    "Select Battery Passport",
    owned["battery_id"].tolist(),
)

# Latest health snapshot for selected battery
health = read_query(
    """
    SELECT timestamp, cycle_count, soh, rul, voltage, temperature
    FROM health_snapshots
    WHERE battery_id = ?
    ORDER BY timestamp DESC
    LIMIT 1
    """,
    (selected_id,),
)

st.markdown("---")
st.subheader("Battery Health")

if health.empty:
    st.info("No health snapshot is available for this battery.")
else:
    h = health.iloc[0]

    m1, m2, m3 = st.columns(3)
    m1.metric(
        "State of Health (SoH)",
        f"{h['soh']:.1f}%" if pd.notna(h["soh"]) else "N/A",
    )
    m2.metric(
        "Remaining Useful Life (RUL)",
        f"{int(h['rul']):,}" if pd.notna(h["rul"]) else "N/A",
    )
    m3.metric(
        "Cycle Count",
        f"{int(h['cycle_count']):,}"
        if pd.notna(h["cycle_count"]) else "N/A",
    )

    m4, m5 = st.columns(2)
    m4.metric(
        "Voltage",
        f"{h['voltage']:.2f} V" if pd.notna(h["voltage"]) else "N/A",
    )
    m5.metric(
        "Temperature",
        f"{h['temperature']:.1f} °C"
        if pd.notna(h["temperature"]) else "N/A",
    )

    st.caption(f"Latest recorded health snapshot: {h['timestamp']}")

    # Simple informational alert based on recorded SoH.
    # This is not a replacement for a professional battery safety assessment.
    if pd.notna(h["soh"]) and h["soh"] < 70:
        st.warning(
            "Recorded SoH is below 70%. Arrange a qualified battery inspection."
        )
    elif pd.notna(h["soh"]) and h["soh"] < 80:
        st.info(
            "Recorded SoH is below 80%. Consider scheduling a maintenance check."
        )
    else:
        st.success("No low-SoH alert triggered by this simple threshold check.")

st.markdown("---")
st.subheader("Health History")

history = read_query(
    """
    SELECT timestamp, cycle_count, soh, rul, voltage, temperature
    FROM health_snapshots
    WHERE battery_id = ?
    ORDER BY timestamp DESC
    """,
    (selected_id,),
)

if history.empty:
    st.info("No health history is available.")
else:
    st.dataframe(history, hide_index=True, use_container_width=True)

st.markdown("---")
st.subheader("Lifecycle Recommendations")

decisions = read_query(
    """
    SELECT timestamp, action, confidence, reasons, recommended_centre
    FROM decisions
    WHERE battery_id = ?
    ORDER BY timestamp DESC
    """,
    (selected_id,),
)

if decisions.empty:
    st.info(
        "No stored lifecycle decision is available for this battery yet. "
        "Run the existing lifecycle analysis in your main application."
    )
else:
    st.dataframe(decisions, hide_index=True, use_container_width=True)

st.markdown("---")
st.subheader("Ownership History")

ownership = read_query(
    """
    SELECT owner, role, from_date, to_date
    FROM ownership
    WHERE battery_id = ?
    ORDER BY id
    """,
    (selected_id,),
)

if ownership.empty:
    st.info("No ownership history is recorded.")
else:
    st.dataframe(ownership, hide_index=True, use_container_width=True)
