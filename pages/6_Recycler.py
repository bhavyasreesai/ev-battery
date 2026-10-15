
import sqlite3
from pathlib import Path
from datetime import datetime

import pandas as pd
import streamlit as st

DB_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "battery_passport.db"
)

st.set_page_config(
    page_title="Recycler",
    layout="wide",
)

st.title("Recycler")
st.caption("Manage incoming batteries, recycling progress, and recovered materials.")

if not DB_PATH.exists():
    st.error("Battery database not found. No new database was created.")
    st.stop()


def read_query(query, params=()):
    with sqlite3.connect(DB_PATH) as con:
        return pd.read_sql_query(query, con, params=params)


# Add a separate table for recycler workflow tracking.
# Existing tables and records are not dropped or replaced.
with sqlite3.connect(DB_PATH) as con:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS recycling_process (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            battery_id TEXT NOT NULL UNIQUE,
            stage TEXT NOT NULL DEFAULT 'Received',
            safety_status TEXT NOT NULL DEFAULT 'Pending inspection',
            notes TEXT,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (battery_id) REFERENCES batteries(battery_id)
        )
        """
    )

batteries = read_query(
    """
    SELECT battery_id, chemistry, manufacturer, current_owner,
           current_location
    FROM batteries
    ORDER BY battery_id
    """
)

if batteries.empty:
    st.info("No registered batteries are available.")
    st.stop()

st.subheader("Recycler Overview")

with sqlite3.connect(DB_PATH) as con:
    total_batteries = con.execute(
        "SELECT COUNT(*) FROM batteries"
    ).fetchone()[0]

    total_processes = con.execute(
        "SELECT COUNT(*) FROM recycling_process"
    ).fetchone()[0]

    completed = con.execute(
        "SELECT COUNT(*) FROM recycling_process WHERE stage = 'Completed'"
    ).fetchone()[0]

    total_material_records = con.execute(
        "SELECT COUNT(*) FROM material_recovery"
    ).fetchone()[0]

k1, k2, k3, k4 = st.columns(4)
k1.metric("Registered Batteries", total_batteries)
k2.metric("Batteries in Tracking", total_processes)
k3.metric("Completed Processes", completed)
k4.metric("Material Recovery Records", total_material_records)

st.markdown("---")
st.subheader("Incoming Batteries")

st.dataframe(batteries, hide_index=True, use_container_width=True)

st.markdown("---")
st.subheader("Safety Assessment")

selected_id = st.selectbox(
    "Select Battery",
    batteries["battery_id"].tolist(),
)

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

if health.empty:
    st.info("No health snapshot recorded. Complete an inspection before processing.")
else:
    h = health.iloc[0]

    a, b, c = st.columns(3)
    a.metric(
        "Latest SoH",
        f"{h['soh']:.1f}%" if pd.notna(h["soh"]) else "N/A",
    )
    b.metric(
        "Temperature",
        f"{h['temperature']:.1f} °C"
        if pd.notna(h["temperature"]) else "N/A",
    )
    c.metric(
        "Cycle Count",
        f"{int(h['cycle_count']):,}"
        if pd.notna(h["cycle_count"]) else "N/A",
    )

    st.caption(
        "These are recorded readings, not a live safety test. "
        "A qualified person must assess battery safety before handling or processing."
    )

st.markdown("---")
st.subheader("Update Recycling Progress")

stages = [
    "Received",
    "Inspection",
    "Approved for Processing",
    "Dismantling",
    "Material Recovery",
    "Residual Waste Management",
    "Completed",
]

safety_options = [
    "Pending inspection",
    "Inspection required",
    "Approved by qualified inspector",
    "Quarantined",
]

with st.form("recycling_progress_form"):
    stage = st.selectbox("Current Stage", stages)
    safety_status = st.selectbox("Safety Status", safety_options)
    notes = st.text_area("Inspection / Processing Notes")

    update_process = st.form_submit_button("Save Recycling Progress")

if update_process:
    now = datetime.now().isoformat()

    try:
        with sqlite3.connect(DB_PATH) as con:
            exists = con.execute(
                "SELECT 1 FROM batteries WHERE battery_id = ?",
                (selected_id,),
            ).fetchone()

            if not exists:
                st.error("Battery not found. No changes were made.")
            else:
                con.execute(
                    """
                    INSERT INTO recycling_process (
                        battery_id, stage, safety_status, notes, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(battery_id) DO UPDATE SET
                        stage = excluded.stage,
                        safety_status = excluded.safety_status,
                        notes = excluded.notes,
                        updated_at = excluded.updated_at
                    """,
                    (selected_id, stage, safety_status, notes.strip(), now),
                )

        st.success("Recycling progress saved.")

    except sqlite3.Error as error:
        st.error(f"Could not save progress: {error}")

st.markdown("---")
st.subheader("Material Recovery Records")

materials = read_query(
    """
    SELECT battery_id, timestamp, material, recovered_kg
    FROM material_recovery
    ORDER BY timestamp DESC
    """
)

if materials.empty:
    st.info("No recovered material records have been entered yet.")
else:
    st.dataframe(materials, hide_index=True, use_container_width=True)

st.markdown("---")
st.subheader("Record Recovered Material")

with st.form("material_recovery_form"):
    material_battery = st.selectbox(
        "Battery ID for Material Recovery",
        batteries["battery_id"].tolist(),
        key="material_battery",
    )

    material_name = st.selectbox(
        "Material",
        ["Lithium", "Cobalt", "Nickel", "Copper", "Aluminium", "Graphite", "Other"],
    )

    recovered_kg = st.number_input(
        "Recovered Mass (kg)",
        min_value=0.0,
        value=0.0,
        step=0.1,
    )

    record_material = st.form_submit_button("Record Material")

if record_material:
    if recovered_kg <= 0:
        st.warning("Enter a recovered mass greater than zero.")
    else:
        now = datetime.now().isoformat()

        try:
            with sqlite3.connect(DB_PATH) as con:
                exists = con.execute(
                    "SELECT 1 FROM batteries WHERE battery_id = ?",
                    (material_battery,),
                ).fetchone()

                if not exists:
                    st.error("Battery not found. No changes were made.")
                else:
                    con.execute(
                        """
                        INSERT INTO material_recovery (
                            battery_id, timestamp, material, recovered_kg
                        )
                        VALUES (?, ?, ?, ?)
                        """,
                        (material_battery, now, material_name, recovered_kg),
                    )

            st.success("Material recovery record added.")

        except sqlite3.Error as error:
            st.error(f"Could not record material: {error}")

st.markdown("---")
st.subheader("Recycling Progress Summary")

progress = read_query(
    """
    SELECT battery_id, stage, safety_status, notes, updated_at
    FROM recycling_process
    ORDER BY updated_at DESC
    """
)

if progress.empty:
    st.info("No recycling processes have been started.")
else:
    st.dataframe(progress, hide_index=True, use_container_width=True)
