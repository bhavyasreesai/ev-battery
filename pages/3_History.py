"""
Module D - Analysis history viewer.

Reads data/history.db and shows:
  - summary KPIs (total analyses, most common decision, CO2 saved)
  - a filterable table of every logged analysis
  - a bar chart of decisions over time
  - CSV export
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import streamlit as st
import pandas as pd
import plotly.express as px

from history import fetch_history, count_rows, clear_history

st.set_page_config(
    page_title="History",
    page_icon="H",
    layout="wide",
)

st.title("Analysis History")
st.caption("Every battery analysis is logged here (audit trail).")

# ---------- Load ----------
total = count_rows()
if total == 0:
    st.info("No analyses yet. Run one on the app page or upload a batch CSV.")
    st.stop()

rows = fetch_history()
df = pd.DataFrame(rows)

# Convert timestamp for sorting
df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

# ---------- KPI row ----------
k1, k2, k3, k4 = st.columns(4)
k1.metric("Total analyses", f"{len(df):,}")
k2.metric("Unique batteries", f"{df['battery_id'].nunique():,}")
k3.metric("Most common decision", df["decision"].mode().iloc[0] if len(df) else "-")
k4.metric("Total CO2 avoided", f"{df['carbon_avoided_kg'].fillna(0).sum():,.0f} kg")

st.markdown("---")

# ---------- Filters ----------
st.subheader("Filters")

f1, f2, f3 = st.columns(3)

with f1:
    chem_options = ["All"] + sorted(df["chemistry"].dropna().unique().tolist())
    chem_filter = st.selectbox("Battery type", chem_options)

with f2:
    dec_options = ["All"] + sorted(df["decision"].dropna().unique().tolist())
    dec_filter = st.selectbox("Decision", dec_options)

with f3:
    src_options = ["All"] + sorted(df["source"].dropna().unique().tolist())
    src_filter = st.selectbox("Source", src_options)

filtered = df.copy()
if chem_filter != "All":
    filtered = filtered[filtered["chemistry"] == chem_filter]
if dec_filter != "All":
    filtered = filtered[filtered["decision"] == dec_filter]
if src_filter != "All":
    filtered = filtered[filtered["source"] == src_filter]

st.caption(f"Showing {len(filtered):,} of {len(df):,} analyses.")

# ---------- Chart: decisions breakdown ----------
st.markdown("---")
st.subheader("Decision breakdown")

chart_data = filtered["decision"].value_counts().reset_index()
chart_data.columns = ["Decision", "Count"]

fig = px.bar(chart_data, x="Decision", y="Count",
             text_auto=True, color="Decision")
fig.update_layout(height=350, showlegend=False,
                  margin=dict(l=0, r=0, t=20, b=0))
st.plotly_chart(fig, width="stretch")

# ---------- Table ----------
st.markdown("---")
st.subheader("Full log")

display_cols = [
    "id", "timestamp", "battery_id", "chemistry", "soh", "rul",
    "decision", "confidence", "carbon_avoided_kg", "top_centre", "source",
]
display_df = filtered[display_cols].copy()
display_df["timestamp"] = display_df["timestamp"].dt.strftime("%Y-%m-%d %H:%M")
display_df = display_df.rename(columns={
    "id": "ID",
    "timestamp": "Time",
    "battery_id": "Battery ID",
    "chemistry": "Type",
    "soh": "SoH (%)",
    "rul": "RUL",
    "decision": "Decision",
    "confidence": "Confidence",
    "carbon_avoided_kg": "CO2 (kg)",
    "top_centre": "Top centre",
    "source": "Source",
})
st.dataframe(display_df, width="stretch", hide_index=True)

# ---------- Download ----------
csv = display_df.to_csv(index=False).encode("utf-8")
st.download_button(
    label="Download filtered history as CSV",
    data=csv,
    file_name="analysis_history.csv",
    mime="text/csv",
)

# ---------- Danger zone ----------
st.markdown("---")
with st.expander("Danger zone"):
    st.warning("This will delete every row in the history database.")
    if st.button("Clear history"):
        clear_history()
        st.success("History cleared. Refresh the page.")