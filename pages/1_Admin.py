"""
Module 8 - Admin Dashboard.
India-wide view of battery inflow, material recovery, and recycling capacity.

Data sources:
  - data/districts.csv : synthetic district-level inflow (placeholder for
    real CPCB / MoRTH data). Every coefficient documented in write_data.py.
  - Facilities list   : real operational Indian battery recyclers (2026).

Currency: INR (Indian Rupee). Metal prices approximate 2026 LME + Indian spot.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import json
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from carbon import CO2_FACTORS, MATERIAL_LABELS

st.set_page_config(
    page_title="Admin Dashboard",
    page_icon="A",
    layout="wide",
)

# ---------- Load district data ----------
DATA = Path(__file__).resolve().parent.parent / "data" / "districts.csv"
if not DATA.exists():
    st.error(f"Missing data file: {DATA}. Run write_data.py first.")
    st.stop()

df = pd.read_csv(DATA)

DB_PATH = (
        Path(__file__).resolve().parent.parent
        / "data"
        / "battery_passport.db"
)
# ---------- Real Indian battery recycling facilities (2026) ----------
FACILITIES = pd.DataFrame([
    {"name": "Bridge Green Upcycle", "state": "Tamil Nadu",     "lat": 13.418, "lon": 80.119, "capacity_tpa": 7200,  "type": "Formal"},
    {"name": "Rocklink India",        "state": "Uttar Pradesh",  "lat": 28.451, "lon": 77.701, "capacity_tpa": 10000, "type": "Formal"},
    {"name": "LICO Materials",        "state": "Karnataka",      "lat": 12.971, "lon": 77.594, "capacity_tpa": 25000, "type": "Formal"},
    {"name": "Lohum",                 "state": "Uttar Pradesh",  "lat": 28.474, "lon": 77.504, "capacity_tpa": 20000, "type": "Formal"},
    {"name": "Epic Energy / REFNIC",  "state": "Maharashtra",    "lat": 19.657, "lon": 73.135, "capacity_tpa": 4000,  "type": "Formal"},
])

# ---------- Material prices (INR per kg, 2026 approximations) ----------
PRICES_INR = {
    "Li": 6500,
    "Co": 3200,
    "Ni": 1450,
    "Cu": 780,
    "Al": 220,
    "Graphite": 60,
}

# ============================================================
# HEADER
# ============================================================
st.title("Admin Dashboard - National Battery Recycling Overview")
st.caption(
    "India-wide view of battery inflow, material recovery and recycling capacity. "
    "Market data as of 2026."
)

# ============================================================
# KPI ROW
# ============================================================
total_batteries = int(df["batteries"].sum())
total_kg = float(df["total_kg"].sum())

recovered_cols = ["li_kg", "co_kg", "ni_kg", "cu_kg", "al_kg", "graphite_kg"]
total_recovered_kg = float(df[recovered_cols].sum().sum())

value_li = float(df["li_kg"].sum()) * PRICES_INR["Li"]
value_co = float(df["co_kg"].sum()) * PRICES_INR["Co"]
value_ni = float(df["ni_kg"].sum()) * PRICES_INR["Ni"]
value_cu = float(df["cu_kg"].sum()) * PRICES_INR["Cu"]
value_al = float(df["al_kg"].sum()) * PRICES_INR["Al"]
value_gr = float(df["graphite_kg"].sum()) * PRICES_INR["Graphite"]
total_value_cr = (value_li + value_co + value_ni + value_cu + value_al + value_gr) / 1e7

# CO2 avoided nationally
co2_by_material = {
    "li_kg":       float(df["li_kg"].sum())       * CO2_FACTORS["li_kg"],
    "co_kg":       float(df["co_kg"].sum())       * CO2_FACTORS["co_kg"],
    "ni_kg":       float(df["ni_kg"].sum())       * CO2_FACTORS["ni_kg"],
    "cu_kg":       float(df["cu_kg"].sum())       * CO2_FACTORS["cu_kg"],
    "al_kg":       float(df["al_kg"].sum())       * CO2_FACTORS["al_kg"],
    "graphite_kg": float(df["graphite_kg"].sum()) * CO2_FACTORS["graphite_kg"],
}
total_co2_kg = sum(co2_by_material.values())
total_co2_kt = total_co2_kg / 1e6

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Batteries reaching EOL", f"{total_batteries:,}")
k2.metric("Total mass", f"{total_kg/1e6:,.1f} kt")
k3.metric("Material recovered", f"{total_recovered_kg/1e6:,.2f} kt")
k4.metric("Recovered value", f"Rs {total_value_cr:,.1f} Cr")
k5.metric("CO2 avoided", f"{total_co2_kt:,.1f} kt")

st.markdown("---")

# ============================================================
# INDIA MAP - facilities + district inflow
# ============================================================
st.subheader("Recycling facilities and estimated district inflow")

left, right = st.columns([2, 1])

with left:
    fig = px.scatter_geo(
        df,
        lat="lat", lon="lon",
        size="total_kg",
        color="state",
        hover_name="district",
        hover_data={"total_kg": ":,.0f", "batteries": ":,", "lat": False, "lon": False},
        projection="natural earth",
    )

    fig.add_scattergeo(
        lat=FACILITIES["lat"],
        lon=FACILITIES["lon"],
        text=FACILITIES["name"] + " (" + FACILITIES["capacity_tpa"].astype(str) + " TPA)",
        mode="markers+text",
        textposition="top center",
        marker=dict(size=12, color="crimson", symbol="star", line=dict(width=1, color="white")),
        name="Formal facilities",
        showlegend=True,
    )

    fig.update_geos(
        lataxis_range=[6, 38],
        lonaxis_range=[65, 98],
        showcountries=True,
        countrycolor="lightgray",
        showland=True,
        landcolor="whitesmoke",
        showcoastlines=True,
    )
    fig.update_layout(
        height=600,
        margin=dict(l=0, r=0, t=20, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    st.plotly_chart(fig, width="stretch")
    st.caption(
        "Red stars = operational formal recycling facilities (2026). "
        "Bubble size = estimated annual battery inflow per district."
    )

with right:
    st.subheader("Formal capacity by state")
    cap_df = FACILITIES.groupby("state")["capacity_tpa"].sum().reset_index()
    cap_df = cap_df.sort_values("capacity_tpa", ascending=True)
    fig_cap = px.bar(
        cap_df, x="capacity_tpa", y="state", orientation="h",
        text="capacity_tpa",
        color="capacity_tpa", color_continuous_scale="Blues",
    )
    fig_cap.update_layout(
        height=400, showlegend=False, coloraxis_showscale=False,
        margin=dict(l=0, r=0, t=20, b=0),
        xaxis_title="Capacity (TPA)",
        yaxis_title="",
    )
    st.plotly_chart(fig_cap, width="stretch")
    total_cap = int(FACILITIES["capacity_tpa"].sum())
    st.caption(f"Total formal capacity mapped: **{total_cap:,} TPA**")

st.markdown("---")

# ============================================================
# TOP DISTRICTS + BATTERY TYPE MIX
# ============================================================
left, right = st.columns([2, 1])

with left:
    st.subheader("Top 10 districts by estimated battery inflow")
    top = df.sort_values("batteries", ascending=False).head(10)[
        ["district", "state", "batteries", "total_kg", "chemistry"]
    ].rename(columns={
        "district": "District",
        "state": "State",
        "batteries": "Batteries",
        "total_kg": "Mass (kg)",
        "chemistry": "Dominant type",
    })
    st.dataframe(top, width="stretch", hide_index=True)

with right:
    st.subheader("Battery type mix (by battery count)")
    chem_counts = df.groupby("chemistry")["batteries"].sum().reset_index()
    chem_counts = chem_counts.rename(columns={"chemistry": "Battery type"})
    fig2 = px.pie(
        chem_counts, names="Battery type", values="batteries", hole=0.4,
    )
    fig2.update_layout(height=340, margin=dict(l=0, r=0, t=20, b=0))
    st.plotly_chart(fig2, width="stretch")

st.markdown("---")

# ============================================================
# MATERIAL RECOVERY - mass + value
# ============================================================
st.subheader("Material recovery - mass and economic value")

mat_rows = []
for name, col, price in [
    ("Lithium",  "li_kg",       PRICES_INR["Li"]),
    ("Cobalt",   "co_kg",       PRICES_INR["Co"]),
    ("Nickel",   "ni_kg",       PRICES_INR["Ni"]),
    ("Copper",   "cu_kg",       PRICES_INR["Cu"]),
    ("Aluminium","al_kg",       PRICES_INR["Al"]),
    ("Graphite", "graphite_kg", PRICES_INR["Graphite"]),
]:
    kg = float(df[col].sum())
    mat_rows.append({
        "Material": name,
        "Recovered (kg)": kg,
        "Price (Rs/kg)": price,
        "Value (Rs Cr)": kg * price / 1e7,
    })

mat_df = pd.DataFrame(mat_rows)

left, right = st.columns(2)

with left:
    fig3 = px.bar(
        mat_df, x="Material", y="Recovered (kg)",
        text_auto=".0f", color="Material",
    )
    fig3.update_layout(
        height=380, showlegend=False,
        margin=dict(l=0, r=0, t=20, b=0),
    )
    st.plotly_chart(fig3, width="stretch")

with right:
    fig4 = px.bar(
        mat_df, x="Material", y="Value (Rs Cr)",
        text_auto=".2f", color="Material",
    )
    fig4.update_layout(
        height=380, showlegend=False,
        margin=dict(l=0, r=0, t=20, b=0),
    )
    st.plotly_chart(fig4, width="stretch")


st.markdown("---")
st.subheader("CO2 avoided by material (kilotonnes)")

co2_rows = []
for key, factor in CO2_FACTORS.items():
    kg = float(df[key].sum())
    co2_rows.append({
        "Material": MATERIAL_LABELS[key],
        "CO2 avoided (kt)": kg * factor / 1e6,
    })
co2_df = pd.DataFrame(co2_rows)

fig_co2 = px.bar(
    co2_df, x="Material", y="CO2 avoided (kt)",
    text_auto=".2f", color="Material",
)
fig_co2.update_layout(
    height=380, showlegend=False,
    margin=dict(l=0, r=0, t=20, b=0),
)
st.plotly_chart(fig_co2, width="stretch")
st.caption(
    "Emission factors from Argonne GREET model (2023). "
    "Values represent avoided emissions compared to virgin material production."
)

st.dataframe(
    mat_df.style.format({
        "Recovered (kg)": "{:,.0f}",
        "Price (Rs/kg)": "{:,.0f}",
        "Value (Rs Cr)": "{:,.2f}",
    }),
    width="stretch", hide_index=True,
)
st.caption(
    "Prices are 2026 approximations (LME + Indian spot). "
    "Update PRICES_INR in this file when real quotes are available."
)

st.markdown("---")

# ============================================================
# STATE SUMMARY TABLE
# ============================================================
st.subheader("State-level summary")

state_df = df.groupby("state").agg(
    districts=("district", "count"),
    batteries=("batteries", "sum"),
    total_kg=("total_kg", "sum"),
    li_kg=("li_kg", "sum"),
    co_kg=("co_kg", "sum"),
    cu_kg=("cu_kg", "sum"),
).reset_index().rename(columns={
    "state": "State",
    "districts": "Districts",
    "batteries": "Batteries",
    "total_kg": "Mass (kg)",
    "li_kg": "Li (kg)",
    "co_kg": "Co (kg)",
    "cu_kg": "Cu (kg)",
}).sort_values("Batteries", ascending=False)

cap_by_state = FACILITIES.groupby("state")["capacity_tpa"].sum()
state_df["Formal capacity (TPA)"] = state_df["State"].map(cap_by_state).fillna(0).astype(int)

st.dataframe(
    state_df.style.format({
        "Batteries": "{:,}",
        "Mass (kg)": "{:,.0f}",
        "Li (kg)": "{:,.1f}",
        "Co (kg)": "{:,.1f}",
        "Cu (kg)": "{:,.1f}",
        "Formal capacity (TPA)": "{:,}",
    }),
    width="stretch", hide_index=True,
)

# ============================================================
# INDIA BATTERY MARKETPLACE ANALYTICS
# Source: Actual listings and completed transactions
# ============================================================

st.markdown("---")
st.title("India Battery Marketplace Analytics")

st.caption(
    "Analysis of actual battery listings and completed purchases "
    "recorded in the existing Battery Passport database."
)

if not DB_PATH.exists():
    st.warning("Marketplace database not found.")

else:
    with sqlite3.connect(DB_PATH) as con:
        transactions = pd.read_sql_query(
            """
            SELECT
                t.transaction_id,
                t.battery_id,
                t.seller_name,
                l.seller_city,
                l.seller_state,
                l.seller_pincode,
                t.buyer_name,
                t.buyer_city,
                t.buyer_state,
                t.buyer_pincode,
                l.asking_price,
                t.selling_price,
                t.transaction_date,
                t.status,
                b.chemistry,
                b.capacity_kwh
            FROM transactions t
                     JOIN battery_listings l
                          ON t.listing_id = l.listing_id
                     JOIN batteries b
                          ON t.battery_id = b.battery_id
            WHERE t.status = 'Completed'
            ORDER BY t.transaction_date DESC
            """,
            con,
        )

        listings = pd.read_sql_query(
            """
            SELECT
                listing_id,
                battery_id,
                seller_name,
                seller_city,
                seller_state,
                asking_price,
                status,
                listed_at
            FROM battery_listings
            """,
            con,
        )

    # Convert monetary columns to numeric values.
    if not transactions.empty:
        transactions["asking_price"] = pd.to_numeric(
            transactions["asking_price"], errors="coerce"
        )

        transactions["selling_price"] = pd.to_numeric(
            transactions["selling_price"], errors="coerce"
        )

        transactions["buyer_savings"] = (
                transactions["asking_price"]
                - transactions["selling_price"]
        )

    total_listings = len(listings)
    available_listings = (
        int((listings["status"] == "Available").sum())
        if not listings.empty else 0
    )

    completed_count = len(transactions)

    total_sales_value = (
        float(transactions["selling_price"].sum())
        if completed_count else 0.0
    )

    average_purchase_price = (
        float(transactions["selling_price"].mean())
        if completed_count else 0.0
    )

    total_buyer_savings = (
        float(transactions["buyer_savings"].sum())
        if completed_count else 0.0
    )

    # --------------------------------------------------------
    # MARKETPLACE KPIs
    # --------------------------------------------------------

    st.subheader("Marketplace Overview")

    k1, k2, k3, k4, k5 = st.columns(5)

    k1.metric("Total Listings", f"{total_listings:,}")
    k2.metric("Available Listings", f"{available_listings:,}")
    k3.metric("Completed Sales", f"{completed_count:,}")
    k4.metric("Total Sales Value", f"₹{total_sales_value:,.0f}")
    k5.metric("Buyer Savings", f"₹{total_buyer_savings:,.0f}")

    if transactions.empty:
        st.info(
            "No completed marketplace transactions are recorded yet. "
            "Complete a purchase through the Buyer Dashboard to populate "
            "these analytics."
        )

    else:
        st.caption(
            "Sales value and savings are calculated only from completed "
            "transactions. Savings = seller asking price minus actual "
            "purchase price. A negative value means the buyer paid above "
            "the asking price."
        )

        # ----------------------------------------------------
        # CITY-WISE SELLING AND BUYING ACTIVITY
        # ----------------------------------------------------

        st.markdown("---")
        st.subheader("City-wise Buying and Selling Activity")

        seller_activity = (
            transactions.groupby(
                ["seller_city", "seller_state"]
            )
            .size()
            .reset_index(name="Transactions")
            .rename(
                columns={
                    "seller_city": "City",
                    "seller_state": "State",
                }
            )
        )

        seller_activity["Activity"] = "Selling"

        buyer_activity = (
            transactions.groupby(
                ["buyer_city", "buyer_state"]
            )
            .size()
            .reset_index(name="Transactions")
            .rename(
                columns={
                    "buyer_city": "City",
                    "buyer_state": "State",
                }
            )
        )

        buyer_activity["Activity"] = "Buying"

        city_activity = pd.concat(
            [seller_activity, buyer_activity],
            ignore_index=True,
        )

        city_summary = (
            city_activity.groupby(["City", "State", "Activity"])
            ["Transactions"]
            .sum()
            .reset_index()
        )

        fig_city = px.bar(
            city_summary,
            x="City",
            y="Transactions",
            color="Activity",
            barmode="group",
            hover_data=["State"],
            title="Recorded buying and selling transactions by city",
        )

        fig_city.update_layout(height=420)

        st.plotly_chart(
            fig_city,
            use_container_width=True,
        )

        # ----------------------------------------------------
        # TOP SELLER CITIES
        # ----------------------------------------------------

        left, right = st.columns(2)

        with left:
            st.subheader("Top Seller Cities")

            top_sellers = (
                transactions.groupby(
                    ["seller_city", "seller_state"]
                )
                .agg(
                    Transactions=("transaction_id", "count"),
                    Sales_Value=("selling_price", "sum"),
                )
                .reset_index()
                .sort_values(
                    "Transactions",
                    ascending=False,
                )
                .head(10)
                .rename(
                    columns={
                        "seller_city": "City",
                        "seller_state": "State",
                        "Sales_Value": "Sales Value (₹)",
                    }
                )
            )

            st.dataframe(
                top_sellers,
                hide_index=True,
                use_container_width=True,
            )

        with right:
            st.subheader("Top Buyer Cities")

            top_buyers = (
                transactions.groupby(
                    ["buyer_city", "buyer_state"]
                )
                .agg(
                    Transactions=("transaction_id", "count"),
                    Purchase_Value=("selling_price", "sum"),
                )
                .reset_index()
                .sort_values(
                    "Transactions",
                    ascending=False,
                )
                .head(10)
                .rename(
                    columns={
                        "buyer_city": "City",
                        "buyer_state": "State",
                        "Purchase_Value": "Purchase Value (₹)",
                    }
                )
            )

            st.dataframe(
                top_buyers,
                hide_index=True,
                use_container_width=True,
            )

        # ----------------------------------------------------
        # ASKING PRICE VS ACTUAL PURCHASE PRICE
        # ----------------------------------------------------

        st.markdown("---")
        st.subheader("Asking Price vs Actual Purchase Price")

        price_comparison = pd.DataFrame(
            {
                "Price Type": [
                    "Seller Asking Price",
                    "Actual Purchase Price",
                ],
                "Average Price (₹)": [
                    transactions["asking_price"].mean(),
                    transactions["selling_price"].mean(),
                ],
            }
        )

        fig_price = px.bar(
            price_comparison,
            x="Price Type",
            y="Average Price (₹)",
            text_auto=",.0f",
            title="Average battery transaction prices",
        )

        fig_price.update_layout(height=380)

        st.plotly_chart(
            fig_price,
            use_container_width=True,
        )

        # ----------------------------------------------------
        # ECONOMIC ANALYSIS
        # ----------------------------------------------------

        st.markdown("---")
        st.subheader("Battery Marketplace Economic Analysis")

        average_asking = float(
            transactions["asking_price"].mean()
        )

        average_selling = float(
            transactions["selling_price"].mean()
        )

        average_savings = float(
            transactions["buyer_savings"].mean()
        )

        e1, e2, e3 = st.columns(3)

        e1.metric(
            "Average Asking Price",
            f"₹{average_asking:,.0f}",
        )

        e2.metric(
            "Average Purchase Price",
            f"₹{average_selling:,.0f}",
        )

        e3.metric(
            "Average Price Difference",
            f"₹{average_savings:,.0f}",
        )

        st.caption(
            "The price difference is based on recorded marketplace "
            "prices only. It is not automatically a verified saving "
            "against the cost of a new battery."
        )



        # ----------------------------------------------------
        # BATTERY MOVEMENT MAP - AUTOMATIC CITY LOOKUP
        # ----------------------------------------------------

        st.markdown("---")
        st.subheader("Seller-to-Buyer Battery Movement Across India")

        # Persistent coordinate cache
        CACHE_PATH = (
                Path(__file__).resolve().parent.parent
                / "data"
                / "city_coordinates_cache.json"
        )

        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

        if CACHE_PATH.exists():
            try:
                with open(CACHE_PATH, "r", encoding="utf-8") as file:
                    coordinate_cache = json.load(file)
            except (json.JSONDecodeError, OSError):
                coordinate_cache = {}
        else:
            coordinate_cache = {}

        # OpenStreetMap geocoder
        geolocator = Nominatim(
            user_agent="ev_battery_lifecycle_dashboard"
        )

        geocode_with_delay = RateLimiter(
            geolocator.geocode,
            min_delay_seconds=1,
            max_retries=1,
            error_wait_seconds=2,
            swallow_exceptions=True,
        )

        def normalize_city(city):
            return " ".join(
                str(city).strip().casefold().split()
            )

        def get_city_coordinates(city, state=None):

            city = str(city).strip()

            if len(city) < 3:
                return None

            state = str(state).strip() if state else ""

            cache_key = normalize_city(city) + "|" + normalize_city(state)

            # Return previously saved coordinates
            if cache_key in coordinate_cache:
                return tuple(coordinate_cache[cache_key])

            # Search for the city in India
            query = f"{city}, {state}, India" if state else f"{city}, India"

            try:
                location = geocode_with_delay(
                    query,
                    country_codes="in",
                )

                if location:
                    coordinates = (
                        location.latitude,
                        location.longitude,
                    )

                    coordinate_cache[cache_key] = coordinates

                    # Save coordinates for future use
                    with open(
                            CACHE_PATH,
                            "w",
                            encoding="utf-8",
                    ) as file:
                        json.dump(
                            coordinate_cache,
                            file,
                            indent=4,
                        )

                    return coordinates

            except Exception:
                pass

            return None

        map_points = []
        unsupported_cities = set()

        for _, transaction in transactions.iterrows():

            seller_city = str(transaction["seller_city"]).strip()
            buyer_city = str(transaction["buyer_city"]).strip()

            seller_state = (
                transaction["seller_state"]
                if "seller_state" in transactions.columns
                else ""
            )

            buyer_state = (
                transaction["buyer_state"]
                if "buyer_state" in transactions.columns
                else ""
            )

            seller_coords = get_city_coordinates(
                seller_city,
                seller_state,
            )

            buyer_coords = get_city_coordinates(
                buyer_city,
                buyer_state,
            )

            if not seller_coords:
                unsupported_cities.add(seller_city)

            if not buyer_coords:
                unsupported_cities.add(buyer_city)

            if seller_coords and buyer_coords:

                map_points.append({
                    "Battery ID": transaction["battery_id"],
                    "Seller City": seller_city,
                    "Buyer City": buyer_city,
                    "Seller Lat": seller_coords[0],
                    "Seller Lon": seller_coords[1],
                    "Buyer Lat": buyer_coords[0],
                    "Buyer Lon": buyer_coords[1],
                    "Purchase Price (₹)": transaction["selling_price"],
                })

        if map_points:

            map_df = pd.DataFrame(map_points)

            city_markers = []

            for _, item in map_df.iterrows():

                city_markers.append({
                    "City": item["Seller City"],
                    "Latitude": item["Seller Lat"],
                    "Longitude": item["Seller Lon"],
                    "Location Type": "Seller",
                })

                city_markers.append({
                    "City": item["Buyer City"],
                    "Latitude": item["Buyer Lat"],
                    "Longitude": item["Buyer Lon"],
                    "Location Type": "Buyer",
                })

            marker_df = pd.DataFrame(city_markers)

            fig_map = px.scatter_geo(
                marker_df,
                lat="Latitude",
                lon="Longitude",
                color="Location Type",
                hover_name="City",
                projection="natural earth",
                title="Recorded Battery Transactions Across India",
            )


            for _, item in map_df.iterrows():

                fig_map.add_scattergeo(
                    lat=[
                    item["Seller Lat"],
                    item["Buyer Lat"],
                    ],
                    lon=[
                        item["Seller Lon"],
                        item["Buyer Lon"],
                    ],
                    mode="lines",
                    line=dict(width=2),
                    name=item["Battery ID"],
                    showlegend=False,
                    hoverinfo="text",
                    text=[
                        f"Battery ID: {item['Battery ID']}<br>"
                        f"Seller: {item['Seller City']}<br>"
                        f"Buyer: {item['Buyer City']}",

                        f"Battery ID: {item['Battery ID']}<br>"
                        f"Seller: {item['Seller City']}<br>"
                        f"Buyer: {item['Buyer City']}",
                    ],
                )

            fig_map.update_geos(
                lataxis_range=[6, 38],
                lonaxis_range=[65, 98],
                showcountries=True,
                countrycolor="lightgray",
                showland=True,
                showcoastlines=True,
            )

            fig_map.update_layout(
                height=550,
                margin=dict(l=0, r=0, t=40, b=0),
            )

            st.plotly_chart(
                fig_map,
                use_container_width=True,
            )

            st.caption(
                "Lines represent recorded seller-to-buyer transactions. "
                "City coordinates are retrieved automatically and cached."
            )

        else:
            st.info(
                "No completed transactions currently have both "
                "seller and buyer cities successfully mapped."
            )

        if unsupported_cities:
            st.warning(
                "Could not locate these cities: "
                + ", ".join(sorted(unsupported_cities))
            )

        # BATTERY MOVEMENT MAP
        # ----------------------------------------------------
        # TRANSACTION RECORDS
        # ----------------------------------------------------

        st.markdown("---")
        st.subheader("Completed Transaction Records")

        transaction_display = transactions[
            [
                "transaction_id",
                "battery_id",
                "seller_name",
                "seller_city",
                "buyer_name",
                "buyer_city",
                "asking_price",
                "selling_price",
                "buyer_savings",
                "transaction_date",
                "chemistry",
                "capacity_kwh",
            ]
        ].rename(
            columns={
                "transaction_id": "Transaction ID",
                "battery_id": "Battery ID",
                "seller_name": "Seller",
                "seller_city": "Seller City",
                "buyer_name": "Buyer",
                "buyer_city": "Buyer City",
                "asking_price": "Asking Price (₹)",
                "selling_price": "Purchase Price (₹)",
                "buyer_savings": "Price Difference (₹)",
                "transaction_date": "Date",
                "chemistry": "Chemistry",
                "capacity_kwh": "Capacity (kWh)",
            }
        )

        st.dataframe(
            transaction_display,
            hide_index=True,
            use_container_width=True,
        )

        csv_data = transaction_display.to_csv(
            index=False
        ).encode("utf-8")

        st.download_button(
            "Download Transaction Records (CSV)",
            data=csv_data,
            file_name="india_battery_transactions.csv",
            mime="text/csv",
        )

    # --------------------------------------------------------
    # CURRENT LISTING STATUS
    # --------------------------------------------------------

    st.markdown("---")
    st.subheader("Current Marketplace Listings")

    if listings.empty:
        st.info("No marketplace listings have been created yet.")
    else:
        st.dataframe(
            listings,
            hide_index=True,
            use_container_width=True,
        )

# ============================================================
# NASA BATTERY RESEARCH DATASET UPLOAD
# Separate from the existing Battery Passport database
# ============================================================

st.markdown("---")
st.title("NASA Battery Research Dataset")
st.caption(
    "Upload and analyse NASA B0005 experimental discharge-cycle data. "
    "This section does not modify the existing Battery Passport database."
)

uploaded_nasa_file = st.file_uploader(
    "Upload NASA battery CSV file",
    type=["csv"],
    key="nasa_research_upload"
)

if uploaded_nasa_file is not None:

    try:
        nasa_df = pd.read_csv(uploaded_nasa_file)

        required_columns = [
            "battery_id",
            "discharge_cycle_number",
            "cycle_type",
            "discharge_capacity_Ah",
            "voltage_mean_V",
            "temperature_max_C"
        ]

        missing_columns = [
            col for col in required_columns
            if col not in nasa_df.columns
        ]

        if missing_columns:
            st.error(
                f"NASA CSV is missing required columns: {missing_columns}"
            )

        else:
            # Convert measurement columns to numeric values
            numeric_columns = [
                "discharge_cycle_number",
                "discharge_capacity_Ah",
                "voltage_mean_V",
                "temperature_max_C"
            ]

            for col in numeric_columns:
                nasa_df[col] = pd.to_numeric(
                    nasa_df[col], errors="coerce"
                )

            # Keep discharge records with valid measurements
            nasa_df = nasa_df[
                nasa_df["cycle_type"].astype(str).str.lower() == "discharge"
                ]

            nasa_df = nasa_df.dropna(
                subset=numeric_columns
            )

            nasa_df = nasa_df.sort_values(
                "discharge_cycle_number"
            )
            # Calculate rated-capacity-based State of Health
            reference_capacity_ah = 2.0

            nasa_df["soh_percent"] = (
                nasa_df["discharge_capacity_Ah"]
                / reference_capacity_ah
                ) * 100

            if nasa_df.empty:
                st.warning("No valid discharge-cycle records found.")

            else:
                st.success(
                    f"Successfully loaded {len(nasa_df)} discharge-cycle records."
                )

                st.subheader("Dataset Overview")

                st.write(
                    "Battery ID:",
                    ", ".join(
                        nasa_df["battery_id"].astype(str).unique()
                    )
                )

                st.metric(
                    "Discharge cycles",
                    len(nasa_df)
                )

                st.dataframe(
                    nasa_df,
                    use_container_width=True,
                    hide_index=True
                )

                # ------------------------------------------------
                # CAPACITY ANALYSIS
                # ------------------------------------------------

                st.markdown("---")
                st.subheader("Battery Capacity Degradation")

                first_capacity = float(
                    nasa_df.iloc[0]["discharge_capacity_Ah"]
                )

                last_capacity = float(
                    nasa_df.iloc[-1]["discharge_capacity_Ah"]
                )

                capacity_change = (
                                          (last_capacity - first_capacity)
                                          / first_capacity
                                  ) * 100

                c1, c2, c3 = st.columns(3)

                c1.metric(
                    "First uploaded capacity",
                    f"{first_capacity:.4f} Ah"
                )

                c2.metric(
                    "Last uploaded capacity",
                    f"{last_capacity:.4f} Ah"
                )

                c3.metric(
                    "Capacity change",
                    f"{capacity_change:.2f}%"
                )

                fig_capacity = px.line(
                    nasa_df,
                    x="discharge_cycle_number",
                    y="discharge_capacity_Ah",
                    markers=True,
                    title="Discharge Capacity Across Cycles"
                )

                fig_capacity.update_layout(
                    xaxis_title="Discharge Cycle",
                    yaxis_title="Capacity (Ah)"
                )

                st.plotly_chart(
                    fig_capacity,
                    use_container_width=True
                )

                # ------------------------------------------------
                # VOLTAGE ANALYSIS
                # ------------------------------------------------

                st.markdown("---")
                st.subheader("Voltage Analysis")

                fig_voltage = px.line(
                    nasa_df,
                    x="discharge_cycle_number",
                    y="voltage_mean_V",
                    markers=True,
                    title="Mean Voltage Across Discharge Cycles"
                )

                fig_voltage.update_layout(
                    xaxis_title="Discharge Cycle",
                    yaxis_title="Mean Voltage (V)"
                )

                st.plotly_chart(
                    fig_voltage,
                    use_container_width=True
                )

                # ------------------------------------------------
                # TEMPERATURE ANALYSIS
                # ------------------------------------------------

                st.markdown("---")
                st.subheader("Temperature Analysis")

                fig_temperature = px.line(
                    nasa_df,
                    x="discharge_cycle_number",
                    y="temperature_max_C",
                    markers=True,
                    title="Maximum Temperature Across Discharge Cycles"
                )

                fig_temperature.update_layout(
                    xaxis_title="Discharge Cycle",
                    yaxis_title="Maximum Temperature (°C)"
                )

                st.plotly_chart(
                    fig_temperature,
                    use_container_width=True
                )
                # SOH ANALYSIS
                st.markdown("---")
                st.subheader("State of Health (SoH) Analysis")

                fig_soh = px.line(
                    nasa_df,
                    x="discharge_cycle_number",
                    y="soh_percent",
                    markers=True,
                    title="Calculated SoH Across Discharge Cycles"
                )

                fig_soh.update_layout(
                    xaxis_title="Discharge Cycle",
                    yaxis_title="SoH (%)"
                )

                st.plotly_chart(
                    fig_soh,
                    use_container_width=True
                )

                st.info(
                    "Research note: Capacity change above is measured "
                    "relative to the first uploaded discharge cycle. "
                    "It is not State of Health (SoH). A documented "
                    "reference capacity is needed to calculate SoH."
                )

    except Exception as e:
        st.error(f"Could not read the NASA CSV file: {e}")