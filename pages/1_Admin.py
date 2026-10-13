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
import plotly.express as px
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

