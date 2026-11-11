
import sqlite3
import re
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
    conn = connect_db()
    try:
        return pd.read_sql_query(
            """
            SELECT battery_id, chemistry, capacity_kwh, weight_kg,
                   manufacturer, current_owner, current_location
            FROM batteries
            ORDER BY battery_id
            """,
            conn,
        )
    finally:
        conn.close()


def get_seller_batteries(seller_name):
    conn = connect_db()
    try:
        return pd.read_sql_query(
            """
            SELECT b.battery_id, b.chemistry, b.capacity_kwh,
                   b.weight_kg, b.manufacturer
            FROM batteries b
            WHERE b.current_owner = ?
              AND NOT EXISTS (
                SELECT 1
                FROM battery_listings l
                WHERE l.battery_id = b.battery_id
                  AND l.status = 'Available'
            )
            ORDER BY b.battery_id
            """,
            conn,
            params=(seller_name,),
        )
    finally:
        conn.close()


def get_listings(seller_name=None):
    conn = connect_db()
    try:
        query = """
                SELECT listing_id, battery_id, seller_name,
                       seller_city, seller_state, seller_pincode,
                       asking_price, status, listed_at
                FROM battery_listings \
                """
        params = ()

        if seller_name:
            query += " WHERE seller_name = ?"
            params = (seller_name,)

        query += " ORDER BY listed_at DESC"

        return pd.read_sql_query(query, conn, params=params)
    finally:
        conn.close()


st.title("Seller Dashboard")
st.caption(
    "Register batteries, view Battery Passports, manage ownership, "
    "and list batteries for sale."
)

if not DB_PATH.exists():
    st.error("Battery database not found. Please initialise the database first.")
    st.stop()


tab1, tab2, tab3, tab4, tab5 = st.tabs(
    [
        "Register Battery",
        "Sell Battery",
        "Battery Passport",
        "Transfer Ownership",
        "Edit Battery",
    ]
)


# ---------------------------------------------------------
# TAB 1: REGISTER BATTERY
# ---------------------------------------------------------

with tab1:
    st.subheader("Register a New Battery")

    with st.form("seller_register_battery"):
        battery_id = st.text_input("Battery ID")

        chemistry = st.selectbox(
            "Battery Chemistry",
            ["LFP", "NMC", "NCA", "Other"],
        )

        capacity_kwh = st.number_input(
            "Capacity (kWh)",
            min_value=0.1,
            value=50.0,
            step=1.0,
        )

        weight_kg = st.number_input(
            "Weight (kg)",
            min_value=0.1,
            value=300.0,
            step=10.0,
        )

        manufacturer = st.text_input("Manufacturer")
        owner = st.text_input("Current Owner")
        location = st.text_input("Current Location")

        submitted = st.form_submit_button("Register Battery")

    if submitted:
        if not all([battery_id.strip(), manufacturer.strip(),
                    owner.strip(), location.strip()]):
            st.error("Please fill in all required fields.")
        else:
            conn = connect_db()
            try:
                existing = conn.execute(
                    "SELECT battery_id FROM batteries WHERE battery_id = ?",
                    (battery_id.strip(),),
                ).fetchone()

                if existing:
                    st.error("This Battery ID is already registered.")
                else:
                    now = datetime.now().isoformat()

                    conn.execute(
                        """
                        INSERT INTO batteries (
                            battery_id, chemistry, capacity_kwh,
                            weight_kg, manufacturer, current_owner,
                            current_location, created_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            battery_id.strip(),
                            chemistry,
                            capacity_kwh,
                            weight_kg,
                            manufacturer.strip(),
                            owner.strip(),
                            location.strip(),
                            now,
                        ),
                    )

                    conn.execute(
                        """
                        INSERT INTO ownership (
                            battery_id, owner, role, from_date
                        )
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            battery_id.strip(),
                            owner.strip(),
                            "seller",
                            now,
                        ),
                    )

                    conn.commit()
                    st.success("Battery registered successfully!")

            except sqlite3.Error as e:
                conn.rollback()
                st.error(f"Database error: {e}")
            finally:
                conn.close()


# ---------------------------------------------------------
# TAB 2: SELL BATTERY
# ---------------------------------------------------------

with tab2:
    st.subheader("List Your Battery for Sale")

    batteries_df = get_batteries()

    if batteries_df.empty:
        st.info("Register a battery before creating a sale listing.")
    else:
        owners = sorted(
            batteries_df["current_owner"].dropna().unique().tolist()
        )

        if not owners:
            st.info("No registered battery owners were found.")
        else:
            seller_name = st.selectbox(
                "Seller / Current Owner",
                owners,
                key="listing_seller",
            )

            seller_batteries = get_seller_batteries(seller_name)

            if seller_batteries.empty:
                st.info(
                    "This owner has no batteries available to list. "
                    "A battery already listed for sale cannot be listed again."
                )
            else:
                st.write("**Battery available for listing**")

                battery_options = seller_batteries["battery_id"].tolist()

                selected_battery = st.selectbox(
                    "Select Battery",
                    battery_options,
                    key="listing_battery",
                )

                selected_details = seller_batteries[
                    seller_batteries["battery_id"] == selected_battery
                    ].iloc[0]

                st.write(
                    f"Chemistry: **{selected_details['chemistry']}**"
                )
                st.write(
                    f"Capacity: **{selected_details['capacity_kwh']} kWh**"
                )
                st.write(
                    f"Weight: **{selected_details['weight_kg']} kg**"
                )

                st.divider()
                st.write("**Seller Location**")

                col1, col2 = st.columns(2)

                with col1:
                    seller_city = st.text_input("City", key="seller_city")
                    seller_state = st.text_input("State", key="seller_state")

                with col2:
                    seller_pincode = st.text_input(
                        "PIN Code",
                        max_chars=6,
                        key="seller_pincode",
                    )

                    asking_price = st.number_input(
                        "Asking Price (₹)",
                        min_value=1.0,
                        value=50000.0,
                        step=1000.0,
                        key="seller_asking_price",
                    )

                if st.button("Create Sale Listing"):
                    if not seller_city.strip() or not seller_state.strip():
                        st.error("Please enter the seller's city and state.")

                    elif not re.fullmatch(r"\d{6}", seller_pincode.strip()):
                        st.error("Please enter a valid 6-digit Indian PIN code.")

                    elif asking_price <= 0:
                        st.error("Asking price must be greater than zero.")

                    else:
                        conn = connect_db()

                        try:
                            current = conn.execute(
                                """
                                SELECT current_owner
                                FROM batteries
                                WHERE battery_id = ?
                                """,
                                (selected_battery,),
                            ).fetchone()

                            if not current or current[0] != seller_name:
                                st.error(
                                    "The selected seller is no longer "
                                    "the current owner of this battery."
                                )

                            else:
                                active_listing = conn.execute(
                                    """
                                    SELECT listing_id
                                    FROM battery_listings
                                    WHERE battery_id = ?
                                      AND status = 'Available'
                                    """,
                                    (selected_battery,),
                                ).fetchone()

                                if active_listing:
                                    st.error(
                                        "This battery already has an active listing."
                                    )
                                else:
                                    conn.execute(
                                        """
                                        INSERT INTO battery_listings (
                                            battery_id, seller_name,
                                            seller_city, seller_state,
                                            seller_pincode, asking_price,
                                            status, listed_at
                                        )
                                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                        """,
                                        (
                                            selected_battery,
                                            seller_name,
                                            seller_city.strip(),
                                            seller_state.strip(),
                                            seller_pincode.strip(),
                                            asking_price,
                                            "Available",
                                            datetime.now().isoformat(),
                                        ),
                                    )

                                    conn.commit()
                                    st.success(
                                        "Battery successfully listed for sale!"
                                    )

                        except sqlite3.Error as e:
                            conn.rollback()
                            st.error(f"Database error: {e}")

                        finally:
                            conn.close()

    st.divider()
    st.subheader("Marketplace Listing Status")

    all_listings = get_listings()

    if all_listings.empty:
        st.info("No marketplace listings have been created yet.")
    else:
        st.dataframe(
            all_listings,
            use_container_width=True,
            hide_index=True,
        )

        available_count = (
                all_listings["status"] == "Available"
        ).sum()

        sold_count = (
                all_listings["status"] == "Sold"
        ).sum()

        col1, col2 = st.columns(2)

        col1.metric("Available Listings", int(available_count))
        col2.metric("Sold Listings", int(sold_count))


# ---------------------------------------------------------
# TAB 3: BATTERY PASSPORT
# ---------------------------------------------------------

with tab3:
    st.subheader("Battery Passport")

    batteries_df = get_batteries()

    if batteries_df.empty:
        st.info("No batteries registered yet.")
    else:
        st.dataframe(
            batteries_df,
            use_container_width=True,
            hide_index=True,
        )

        selected_id = st.selectbox(
            "Select Battery ID",
            batteries_df["battery_id"].tolist(),
            key="passport_battery",
        )

        conn = connect_db()

        try:
            battery = pd.read_sql_query(
                "SELECT * FROM batteries WHERE battery_id = ?",
                conn,
                params=(selected_id,),
            )

            ownership = pd.read_sql_query(
                """
                SELECT * FROM ownership
                WHERE battery_id = ?
                ORDER BY from_date
                """,
                conn,
                params=(selected_id,),
            )

            health = pd.read_sql_query(
                """
                SELECT * FROM health_snapshots
                WHERE battery_id = ?
                ORDER BY timestamp DESC
                """,
                conn,
                params=(selected_id,),
            )

            decisions = pd.read_sql_query(
                """
                SELECT * FROM decisions
                WHERE battery_id = ?
                ORDER BY timestamp DESC
                """,
                conn,
                params=(selected_id,),
            )

            materials = pd.read_sql_query(
                """
                SELECT * FROM material_recovery
                WHERE battery_id = ?
                """,
                conn,
                params=(selected_id,),
            )

        finally:
            conn.close()

        st.write("**Battery Details**")
        st.dataframe(battery, use_container_width=True, hide_index=True)

        st.write("**Ownership History**")
        st.dataframe(ownership, use_container_width=True, hide_index=True)

        st.write("**Health Snapshots**")
        st.dataframe(health, use_container_width=True, hide_index=True)

        st.write("**Lifecycle Decisions**")
        st.dataframe(decisions, use_container_width=True, hide_index=True)

        st.write("**Material Recovery Records**")
        st.dataframe(materials, use_container_width=True, hide_index=True)


# ---------------------------------------------------------
# TAB 4: TRANSFER OWNERSHIP
# ---------------------------------------------------------

with tab4:
    st.subheader("Transfer Battery Ownership")

    batteries_df = get_batteries()

    if batteries_df.empty:
        st.info("No batteries available for ownership transfer.")
    else:
        with st.form("seller_transfer_ownership"):
            battery_id = st.selectbox(
                "Select Battery",
                batteries_df["battery_id"].tolist(),
                key="transfer_battery",
            )

            new_owner = st.text_input("New Owner")

            role = st.selectbox(
                "New Owner Role",
                ["buyer", "second_owner", "recycler", "recovery_centre"],
            )

            new_location = st.text_input(
                "New Location (optional)"
            )

            transfer_submitted = st.form_submit_button(
                "Transfer Ownership"
            )

        if transfer_submitted:
            if not new_owner.strip():
                st.error("Please enter the new owner's name.")
            else:
                conn = connect_db()

                try:
                    current = conn.execute(
                        """
                        SELECT current_owner
                        FROM batteries
                        WHERE battery_id = ?
                        """,
                        (battery_id,),
                    ).fetchone()

                    if not current:
                        st.error("Battery not found.")

                    elif current[0] == new_owner.strip():
                        st.warning(
                            "The selected person is already the current owner."
                        )

                    else:
                        now = datetime.now().isoformat()

                        conn.execute(
                            """
                            UPDATE ownership
                            SET to_date = ?
                            WHERE battery_id = ?
                              AND to_date IS NULL
                            """,
                            (now, battery_id),
                        )

                        conn.execute(
                            """
                            INSERT INTO ownership (
                                battery_id, owner, role, from_date
                            )
                            VALUES (?, ?, ?, ?)
                            """,
                            (
                                battery_id,
                                new_owner.strip(),
                                role,
                                now,
                            ),
                        )



                        if new_location.strip():
                            conn.execute(
                                """
                                UPDATE batteries
                                SET current_owner = ?,
                                    current_location = ?
                                WHERE battery_id = ?
                                """,
                                (
                                    new_owner.strip(),
                                    new_location.strip(),
                                    battery_id,
                                ),
                            )
                        else:
                            conn.execute(
                                """
                                UPDATE batteries
                                SET current_owner = ?
                                WHERE battery_id = ?
                                """,
                                (new_owner.strip(), battery_id),
                            )

                        conn.commit()
                        st.success("Ownership transferred successfully!")

                except sqlite3.Error as e:
                    conn.rollback()
                    st.error(f"Database error: {e}")

                finally:
                    conn.close()


# ---------------------------------------------------------
# TAB 5: EDIT REGISTERED BATTERY
# ---------------------------------------------------------

with tab5:
    st.subheader("Edit Registered Battery")

    batteries_df = get_batteries()

    if batteries_df.empty:
        st.info("No registered batteries available.")
    else:
        selected_id = st.selectbox(
            "Select Battery ID to Edit",
            batteries_df["battery_id"].tolist(),
            key="edit_battery_id",
        )

        conn = connect_db()

        try:
            battery = conn.execute(
                """
                SELECT chemistry, capacity_kwh, weight_kg,
                       manufacturer, current_owner, current_location
                FROM batteries
                WHERE battery_id = ?
                """,
                (selected_id,),
            ).fetchone()
        finally:
            conn.close()

        if battery:
            chemistry, capacity, weight, manufacturer, owner, location = battery

            with st.form("edit_registered_battery"):

                st.text_input(
                    "Battery ID",
                    value=selected_id,
                    disabled=True,
                )

                new_chemistry = st.selectbox(
                    "Battery Chemistry",
                    ["LFP", "NMC", "NCA", "Other"],
                    index=["LFP", "NMC", "NCA", "Other"].index(chemistry)
                    if chemistry in ["LFP", "NMC", "NCA", "Other"]
                    else 0,
                )

                new_capacity = st.number_input(
                    "Capacity (kWh)",
                    min_value=0.1,
                    value=float(capacity or 50.0),
                    step=1.0,
                )

                new_weight = st.number_input(
                    "Weight (kg)",
                    min_value=0.1,
                    value=float(weight or 300.0),
                    step=10.0,
                )

                new_manufacturer = st.text_input(
                    "Manufacturer",
                    value=manufacturer or "",
                )

                st.text_input(
                    "Current Owner",
                    value=owner or "",
                    disabled=True,
                )

                new_location = st.text_input(
                    "Current Location",
                    value=location or "",
                )

                update = st.form_submit_button("Update Battery Details")

            if update:
                if not new_manufacturer.strip() or not new_location.strip():
                    st.error("Manufacturer and location cannot be empty.")
                else:
                    conn = connect_db()

                    try:
                        conn.execute(
                            """
                            UPDATE batteries
                            SET chemistry = ?,
                                capacity_kwh = ?,
                                weight_kg = ?,
                                manufacturer = ?,
                                current_location = ?
                            WHERE battery_id = ?
                            """,
                            (
                                new_chemistry,
                                new_capacity,
                                new_weight,
                                new_manufacturer.strip(),
                                new_location.strip(),
                                selected_id,
                            ),
                        )

                        conn.commit()
                        st.success("Battery details updated successfully!")

                    except sqlite3.Error as e:
                        conn.rollback()
                        st.error(f"Database error: {e}")

                    finally:
                        conn.close()
