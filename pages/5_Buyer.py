
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
    page_title="Buyer",
    layout="wide",
)

st.title("Buyer")
st.caption(
    "Explore available batteries, purchase batteries, and monitor "
    "your Battery Passport."
)

if not DB_PATH.exists():
    st.error("Battery database not found. Please check the existing project data.")
    st.stop()


def read_query(query, params=()):
    with sqlite3.connect(DB_PATH) as con:
        return pd.read_sql_query(query, con, params=params)


def get_available_listings():
    return read_query(
        """
        SELECT
            l.listing_id,
            l.battery_id,
            l.seller_name,
            l.seller_city,
            l.seller_state,
            l.seller_pincode,
            l.asking_price,
            l.listed_at,
            b.chemistry,
            b.capacity_kwh,
            b.weight_kg,
            b.manufacturer,
            (
                SELECT h.soh
                FROM health_snapshots h
                WHERE h.battery_id = l.battery_id
                ORDER BY h.timestamp DESC
                LIMIT 1
            ) AS latest_soh,
            (
                SELECT h.rul
                FROM health_snapshots h
                WHERE h.battery_id = l.battery_id
                ORDER BY h.timestamp DESC
                LIMIT 1
            ) AS latest_rul
        FROM battery_listings l
            JOIN batteries b
        ON l.battery_id = b.battery_id
        WHERE l.status = 'Available'
        ORDER BY l.listed_at DESC
        """
    )


tab1, tab2 = st.tabs(
    ["Battery Marketplace", "My Battery Portfolio"]
)


# --------------------------------------------------
# TAB 1: BATTERY MARKETPLACE
# --------------------------------------------------
with tab1:
    st.subheader("Available Batteries for Purchase")

    listings = get_available_listings()

    if listings.empty:
        st.info("There are currently no batteries available for purchase.")
    else:
        st.caption(
            "Compare available batteries and their seller locations "
            "before making a purchase."
        )

        display_listings = listings[
            [
                "battery_id",
                "chemistry",
                "capacity_kwh",
                "latest_soh",
                "latest_rul",
                "manufacturer",
                "seller_name",
                "seller_city",
                "seller_state",
                "asking_price",
            ]
        ].copy()

        display_listings = display_listings.rename(
            columns={
                "battery_id": "Battery ID",
                "chemistry": "Chemistry",
                "capacity_kwh": "Capacity (kWh)",
                "latest_soh": "Latest SoH (%)",
                "latest_rul": "Latest RUL",
                "manufacturer": "Manufacturer",
                "seller_name": "Seller",
                "seller_city": "Seller City",
                "seller_state": "Seller State",
                "asking_price": "Asking Price (₹)",
            }
        )

        st.dataframe(
            display_listings,
            hide_index=True,
            use_container_width=True,
        )

        st.markdown("---")
        st.subheader("Purchase a Battery")

        listing_options = listings["listing_id"].tolist()

        selected_listing_id = st.selectbox(
            "Select a Battery Listing",
            listing_options,
            format_func=lambda listing_id: (
                f"{listings.loc[listings['listing_id'] == listing_id, 'battery_id'].iloc[0]}"
                f" | ₹{listings.loc[listings['listing_id'] == listing_id, 'asking_price'].iloc[0]:,.0f}"
                f" | {listings.loc[listings['listing_id'] == listing_id, 'seller_city'].iloc[0]}"
            ),
        )

        selected_listing = listings[
            listings["listing_id"] == selected_listing_id
            ].iloc[0]

        st.markdown("#### Selected Battery Details")

        c1, c2, c3 = st.columns(3)

        c1.metric("Battery ID", selected_listing["battery_id"])
        c2.metric("Chemistry", selected_listing["chemistry"])
        c3.metric(
            "Capacity",
            f"{selected_listing['capacity_kwh']:.1f} kWh",
        )

        c4, c5, c6 = st.columns(3)

        c4.metric(
            "Seller Asking Price",
            f"₹{selected_listing['asking_price']:,.0f}",
        )

        c5.metric(
            "Latest SoH",
            (
                f"{selected_listing['latest_soh']:.1f}%"
                if pd.notna(selected_listing["latest_soh"])
                else "Not available"
            ),
        )

        c6.metric(
            "Latest RUL",
            (
                f"{selected_listing['latest_rul']:,.0f}"
                if pd.notna(selected_listing["latest_rul"])
                else "Not available"
            ),
        )

        st.write(
            f"**Seller:** {selected_listing['seller_name']}"
        )
        st.write(
            f"**Seller Location:** "
            f"{selected_listing['seller_city']}, "
            f"{selected_listing['seller_state']} - "
            f"{selected_listing['seller_pincode']}"
        )

        st.caption(
            "The health figures shown here are the latest records "
            "stored in the Battery Passport. They are not a substitute "
            "for an independent battery inspection."
        )
        battery_needs_inspection = (
                (
                        pd.notna(selected_listing["latest_soh"])
                        and selected_listing["latest_soh"] < 70
                )
                or (
                        pd.notna(selected_listing["latest_rul"])
                        and selected_listing["latest_rul"] <= 0
                )
        )

        if battery_needs_inspection:
            st.error(
                "HEALTH ALERT: This battery has a low recorded health level "
                "or zero remaining useful life. A qualified professional "
                "must assess it before purchase."
    )

        st.markdown("---")

        with st.form("buyer_purchase_form"):
            st.markdown("#### Buyer Information")

            buyer_name = st.text_input("Buyer Name")
            buyer_city = st.text_input("Buyer City")
            buyer_state = st.text_input("Buyer State")
            buyer_pincode = st.text_input("Buyer PIN Code")

            st.markdown("#### Purchase Price")

            st.write(
                f"Seller's asking price: "
                f"₹{selected_listing['asking_price']:,.2f}"
            )

            selling_price = st.number_input(
                "Agreed Purchase Price (₹)",
                min_value=1.0,
                value=float(selected_listing["asking_price"]),
                step=1000.0,
            )

            purchase_submitted = st.form_submit_button(
                "Complete Purchase",
                disabled=battery_needs_inspection,
            )

        if purchase_submitted:
            if not all(
                    [
                        buyer_name.strip(),
                        buyer_city.strip(),
                        buyer_state.strip(),
                        buyer_pincode.strip(),
                    ]
            ):
                st.warning("Please complete all buyer details.")

            elif (
                    not buyer_pincode.isdigit()
                    or len(buyer_pincode) != 6
            ):
                st.warning("Enter a valid 6-digit Indian PIN code.")

            elif (
                    buyer_name.strip().casefold()
                    == str(selected_listing["seller_name"]).strip().casefold()
            ):
                st.warning("The seller cannot purchase their own listing.")

            else:
                try:
                    with sqlite3.connect(DB_PATH) as con:
                        con.execute("PRAGMA foreign_keys = ON")

                        now = datetime.now().isoformat()

                        current_listing = con.execute(
                            """
                            SELECT
                                l.battery_id,
                                l.seller_name,
                                l.status,
                                b.current_owner
                            FROM battery_listings l
                                     JOIN batteries b
                                          ON l.battery_id = b.battery_id
                            WHERE l.listing_id = ?
                            """,
                            (selected_listing_id,),
                        ).fetchone()

                        if current_listing is None:
                            st.error("Listing not found.")

                        elif current_listing[2] != "Available":
                            st.error(
                                "This battery is no longer available."
                            )

                        elif current_listing[1] != current_listing[3]:
                            st.error(
                                "The seller is no longer the current "
                                "battery owner. This listing cannot be purchased."
                            )

                        else:
                            # Mark the listing as sold only if it is
                            # still available.
                            updated = con.execute(
                                """
                                UPDATE battery_listings
                                SET status = 'Sold'
                                WHERE listing_id = ?
                                  AND status = 'Available'
                                """,
                                (selected_listing_id,),
                            )

                            if updated.rowcount != 1:
                                st.error(
                                    "This listing has already been purchased. "
                                    "Please refresh the page."
                                )

                            else:
                                con.execute(
                                    """
                                    INSERT INTO transactions (
                                        listing_id,
                                        battery_id,
                                        seller_name,
                                        buyer_name,
                                        buyer_city,
                                        buyer_state,
                                        buyer_pincode,
                                        selling_price,
                                        transaction_date,
                                        status
                                    )
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Completed')
                                    """,
                                    (
                                        selected_listing_id,
                                        current_listing[0],
                                        current_listing[1],
                                        buyer_name.strip(),
                                        buyer_city.strip(),
                                        buyer_state.strip(),
                                        buyer_pincode,
                                        selling_price,
                                        now,
                                    ),
                                )

                                con.execute(
                                    """
                                    UPDATE ownership
                                    SET to_date = ?
                                    WHERE battery_id = ?
                                      AND to_date IS NULL
                                    """,
                                    (now, current_listing[0]),
                                )

                                con.execute(
                                    """
                                    INSERT INTO ownership (
                                        battery_id,
                                        owner,
                                        role,
                                        from_date,
                                        to_date
                                    )
                                    VALUES (?, ?, 'buyer', ?, NULL)
                                    """,
                                    (
                                        current_listing[0],
                                        buyer_name.strip(),
                                        now,
                                    ),
                                )

                                con.execute(
                                    """
                                    UPDATE batteries
                                    SET current_owner = ?,
                                        current_location = ?
                                    WHERE battery_id = ?
                                    """,
                                    (
                                        buyer_name.strip(),
                                        buyer_city.strip(),
                                        current_listing[0],
                                    ),
                                )

                                st.success(
                                    "Purchase completed successfully!"
                                )

                                st.write(
                                    f"**Battery:** {current_listing[0]}"
                                )
                                st.write(
                                    f"**Seller:** {current_listing[1]}"
                                )
                                st.write(
                                    f"**Buyer:** {buyer_name.strip()}"
                                )
                                st.write(
                                    f"**Actual Purchase Price:** "
                                    f"₹{selling_price:,.2f}"
                                )

                                st.info(
                                    "The listing is now marked as Sold, "
                                    "and the ownership history has been updated."
                                )

                except sqlite3.Error as error:
                    st.error(
                        f"Purchase failed. Database error: {error}"
                    )


# --------------------------------------------------
# TAB 2: EXISTING BUYER BATTERY PORTFOLIO
# --------------------------------------------------
with tab2:
    st.subheader("Your Battery Portfolio")

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

    else:
        owners = sorted(
            batteries["current_owner"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )

        if not owners:
            st.info("No current battery owners are recorded.")

        else:
            selected_owner = st.selectbox(
                "Select Buyer / Current Owner",
                owners,
                key="portfolio_owner",
            )

            owned = batteries[
                batteries["current_owner"].astype(str)
                == selected_owner
                ].copy()

            k1, k2 = st.columns(2)

            k1.metric("Batteries Owned", len(owned))

            k2.metric(
                "Battery Types",
                owned["chemistry"].nunique()
                if not owned.empty
                else 0,
            )

            st.dataframe(
                owned,
                hide_index=True,
                use_container_width=True,
            )

            if owned.empty:
                st.info("No batteries are assigned to this owner.")

            else:
                selected_id = st.selectbox(
                    "Select Battery Passport",
                    owned["battery_id"].tolist(),
                    key="portfolio_battery",
                )

                # Latest health snapshot
                health = read_query(
                    """
                    SELECT timestamp, cycle_count, soh, rul,
                        voltage, temperature
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
                    st.info(
                        "No health snapshot is available for this battery."
                    )

                else:
                    h = health.iloc[0]

                    m1, m2, m3 = st.columns(3)

                    m1.metric(
                        "State of Health (SoH)",
                        (
                            f"{h['soh']:.1f}%"
                            if pd.notna(h["soh"])
                            else "N/A"
                        ),
                    )

                    m2.metric(
                        "Remaining Useful Life (RUL)",
                        (
                            f"{int(h['rul']):,}"
                            if pd.notna(h["rul"])
                            else "N/A"
                        ),
                    )

                    m3.metric(
                        "Cycle Count",
                        (
                            f"{int(h['cycle_count']):,}"
                            if pd.notna(h["cycle_count"])
                            else "N/A"
                        ),
                    )

                    m4, m5 = st.columns(2)

                    m4.metric(
                        "Voltage",
                        (
                            f"{h['voltage']:.2f} V"
                            if pd.notna(h["voltage"])
                            else "N/A"
                        ),
                    )

                    m5.metric(
                        "Temperature",
                        (
                            f"{h['temperature']:.1f} °C"
                            if pd.notna(h["temperature"])
                            else "N/A"
                        ),
                    )

                    st.caption(
                        f"Latest recorded health snapshot: {h['timestamp']}"
                    )

                    if pd.notna(h["soh"]) and h["soh"] < 70:
                        st.warning(
                            "Recorded SoH is below 70%. "
                            "Arrange a qualified battery inspection."
                        )

                    elif pd.notna(h["soh"]) and h["soh"] < 80:
                        st.info(
                            "Recorded SoH is below 80%. "
                            "Consider scheduling a maintenance check."
                        )

                    else:
                        st.success(
                            "No low-SoH alert triggered by this simple threshold check."
                        )

                st.markdown("---")
                st.subheader("Health History")

                history = read_query(
                    """
                    SELECT timestamp, cycle_count, soh, rul,
                        voltage, temperature
                    FROM health_snapshots
                    WHERE battery_id = ?
                    ORDER BY timestamp DESC
                    """,
                    (selected_id,),
                )

                if history.empty:
                    st.info("No health history is available.")
                else:
                    st.dataframe(
                        history,
                        hide_index=True,
                        use_container_width=True,
                    )

                st.markdown("---")
                st.subheader("Lifecycle Recommendations")

                decisions = read_query(
                    """
                    SELECT timestamp, action, confidence,
                        reasons, recommended_centre
                    FROM decisions
                    WHERE battery_id = ?
                    ORDER BY timestamp DESC
                    """,
                    (selected_id,),
                )

                if decisions.empty:
                    st.info(
                        "No stored lifecycle decision is available for "
                        "this battery yet. Run the existing lifecycle "
                        "analysis in your main application."
                    )
                else:
                    st.dataframe(
                        decisions,
                        hide_index=True,
                        use_container_width=True,
                    )

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
                    st.dataframe(
                        ownership,
                        hide_index=True,
                        use_container_width=True,
                    )
