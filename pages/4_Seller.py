import sqlite3
from pathlib import Path
from datetime import datetime

import streamlit as st
import pandas as pd

# Use the existing project database
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "battery_passport.db"

st.set_page_config(
    page_title="Seller",
    page_icon="",
    layout="wide",
)


def connect_db():
    return sqlite3.connect(DB_PATH)


def get_batteries():
    with connect_db() as con:
        return pd.read_sql_query(
            """
            SELECT battery_id, chemistry, capacity_kwh, weight_kg,
                   manufacturer, current_owner, current_location
            FROM batteries
            ORDER BY battery_id
            """,
            con,
        )


st.title("Seller")
st.caption("Register batteries, view Battery Passports, and manage ownership.")

if not DB_PATH.exists():
    st.error("The existing battery database was not found. No database was created.")
    st.stop()

tab1, tab2, tab3 = st.tabs(
    ["Register Battery", "Battery Passport", "Transfer Ownership"]
)

# --------------------------------------------------
# TAB 1: REGISTER BATTERY
# --------------------------------------------------
with tab1:
    st.subheader("Register a New Battery")

    with st.form("seller_register_battery"):
        battery_id = st.text_input(
            "Unique Battery ID",
            placeholder="Example: EVB-IN-000248",
        ).strip()

        chemistry = st.selectbox("Battery Chemistry", ["LFP", "NMC", "NCA", "Other"])

        capacity_kwh = st.number_input(
            "Capacity (kWh)", min_value=0.1, value=50.0, step=1.0
        )

        weight_kg = st.number_input(
            "Weight (kg)", min_value=0.1, value=300.0, step=10.0
        )

        manufacturer = st.text_input("Manufacturer")
        owner = st.text_input("Seller / Current Owner")
        location = st.text_input("Current Location")

        submitted = st.form_submit_button("Register Battery")

    if submitted:
        if not all([battery_id, manufacturer.strip(), owner.strip(), location.strip()]):
            st.warning("Please complete the battery ID, manufacturer, owner, and location.")
        else:
            try:
                with connect_db() as con:
                    existing = con.execute(
                        "SELECT 1 FROM batteries WHERE battery_id = ?",
                        (battery_id,),
                    ).fetchone()

                    if existing:
                        st.error(
                            "This battery ID already exists. "
                            "Choose a different ID; the existing record was not changed."
                        )
                    else:
                        now = datetime.now().isoformat()

                        con.execute(
                            """
                            INSERT INTO batteries (
                                battery_id, chemistry, capacity_kwh, weight_kg,
                                manufacturer, current_owner, current_location,
                                created_at
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                battery_id,
                                chemistry,
                                capacity_kwh,
                                weight_kg,
                                manufacturer.strip(),
                                owner.strip(),
                                location.strip(),
                                now,
                            ),
                        )

                        con.execute(
                            """
                            INSERT INTO ownership (
                                battery_id, owner, role, from_date, to_date
                            )
                            VALUES (?, ?, ?, ?, NULL)
                            """,
                            (battery_id, owner.strip(), "seller", now),
                        )

                st.success(f"Battery {battery_id} registered successfully.")

            except sqlite3.Error as error:
                st.error(f"Registration failed. Database error: {error}")


# --------------------------------------------------
# TAB 2: BATTERY PASSPORT
# --------------------------------------------------
with tab2:
    st.subheader("Battery Passport")

    batteries = get_batteries()

    if batteries.empty:
        st.info("No batteries have been registered yet.")
    else:
        st.dataframe(batteries, hide_index=True, use_container_width=True)

        selected_id = st.selectbox(
            "Select Battery ID",
            batteries["battery_id"].tolist(),
            key="passport_battery",
        )

        with connect_db() as con:
            battery = con.execute(
                "SELECT * FROM batteries WHERE battery_id = ?",
                (selected_id,),
            ).fetchone()

            ownership = pd.read_sql_query(
                """
                SELECT owner, role, from_date, to_date
                FROM ownership
                WHERE battery_id = ?
                ORDER BY id
                """,
                con,
                params=(selected_id,),
            )

            health = pd.read_sql_query(
                """
                SELECT timestamp, cycle_count, soh, rul, voltage, temperature
                FROM health_snapshots
                WHERE battery_id = ?
                ORDER BY timestamp DESC
                """,
                con,
                params=(selected_id,),
            )

            decisions = pd.read_sql_query(
                """
                SELECT timestamp, action, confidence, reasons, recommended_centre
                FROM decisions
                WHERE battery_id = ?
                ORDER BY timestamp DESC
                """,
                con,
                params=(selected_id,),
            )

            materials = pd.read_sql_query(
                """
                SELECT timestamp, material, recovered_kg
                FROM material_recovery
                WHERE battery_id = ?
                ORDER BY timestamp DESC
                """,
                con,
                params=(selected_id,),
            )

        if battery:
            labels = [
                "Battery ID", "Chemistry", "Capacity (kWh)", "Weight (kg)",
                "Manufacturer", "Manufacture Date", "Current Owner",
                "Current Location", "Created At",
            ]

            st.markdown("#### Battery Information")
            st.dataframe(
                pd.DataFrame({"Field": labels, "Value": list(battery)}),
                hide_index=True,
                use_container_width=True,
            )

        st.markdown("#### Ownership History")
        if ownership.empty:
            st.info("No ownership history is recorded for this battery.")
        else:
            st.dataframe(ownership, hide_index=True, use_container_width=True)

        st.markdown("#### Health History")
        if health.empty:
            st.info("No health snapshots are recorded for this battery.")
        else:
            st.dataframe(health, hide_index=True, use_container_width=True)

        st.markdown("#### Lifecycle Decisions")
        if decisions.empty:
            st.info("No lifecycle decisions are recorded for this battery.")
        else:
            st.dataframe(decisions, hide_index=True, use_container_width=True)

        st.markdown("#### Material Recovery")
        if materials.empty:
            st.info("No material recovery records are recorded for this battery.")
        else:
            st.dataframe(materials, hide_index=True, use_container_width=True)


# --------------------------------------------------
# TAB 3: TRANSFER OWNERSHIP
# --------------------------------------------------
with tab3:
    st.subheader("Transfer Battery Ownership")

    batteries = get_batteries()

    if batteries.empty:
        st.info("Register a battery before transferring ownership.")
    else:
        with st.form("seller_transfer_ownership"):
            transfer_id = st.selectbox(
                "Battery ID",
                batteries["battery_id"].tolist(),
                key="transfer_battery",
            )

            new_owner = st.text_input("New Owner / Buyer")
            role = st.selectbox(
                "New Owner Role",
                ["buyer", "second_owner", "recycler", "recovery_centre"],
            )

            transfer_location = st.text_input(
                "New Location (optional)",
                help="Leave blank to keep the current location.",
            )

            transfer_submitted = st.form_submit_button("Transfer Ownership")

        if transfer_submitted:
            if not new_owner.strip():
                st.warning("Enter the name of the new owner.")
            else:
                try:
                    with connect_db() as con:
                        existing = con.execute(
                            "SELECT current_owner, current_location "
                            "FROM batteries WHERE battery_id = ?",
                            (transfer_id,),
                        ).fetchone()

                        if existing is None:
                            st.error("Battery not found. No changes were made.")
                        elif existing[0] == new_owner.strip():
                            st.warning(
                                "The new owner matches the current owner. "
                                "No transfer was made."
                            )
                        else:
                            now = datetime.now().isoformat()

                            con.execute(
                                """
                                UPDATE ownership
                                SET to_date = ?
                                WHERE battery_id = ? AND to_date IS NULL
                                """,
                                (now, transfer_id),
                            )

                            con.execute(
                                """
                                INSERT INTO ownership (
                                    battery_id, owner, role, from_date, to_date
                                )
                                VALUES (?, ?, ?, ?, NULL)
                                """,
                                (transfer_id, new_owner.strip(), role, now),
                            )

                            if transfer_location.strip():
                                con.execute(
                                    """
                                    UPDATE batteries
                                    SET current_owner = ?, current_location = ?
                                    WHERE battery_id = ?
                                    """,
                                    (
                                        new_owner.strip(),
                                        transfer_location.strip(),
                                        transfer_id,
                                    ),
                                )
                            else:
                                con.execute(
                                    """
                                    UPDATE batteries
                                    SET current_owner = ?
                                    WHERE battery_id = ?
                                    """,
                                    (new_owner.strip(), transfer_id),
                                )

                    if existing is not None and existing[0] != new_owner.strip():
                        st.success(
                            f"Ownership of {transfer_id} transferred successfully."
                        )

                except sqlite3.Error as error:
                    st.error(f"Transfer failed. Database error: {error}")