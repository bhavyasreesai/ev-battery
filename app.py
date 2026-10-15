"""
EV Battery Lifecycle - Streamlit Buyer Dashboard
Run: streamlit run app.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import streamlit as st
import pandas as pd
from pipeline import analyse_battery
from report import generate_report
from history import log_analysis
from database import get_battery, add_health_snapshot, record_decision

st.set_page_config(
    page_title="EV Battery Lifecycle",
    page_icon="B",
    layout="wide",
)

st.title("EV Battery Lifecycle Decision System")
st.caption("AI-powered SoH -> RUL -> Reuse/Recycle -> Materials -> Centre")

# ----- Sidebar inputs -----
st.sidebar.header("Battery Input")

battery_id = st.sidebar.text_input("Battery ID", "EVB-IN-000245")
chemistry = st.sidebar.selectbox("Battery type", ["LFP", "NMC", "NCA", "LMO"])
capacity_kwh = st.sidebar.number_input("Capacity (kWh)", 1.0, 500.0, 45.0)
weight_kg = st.sidebar.number_input("Weight (kg)", 10.0, 1000.0, 320.0)

st.sidebar.markdown("---")
st.sidebar.subheader("Latest Health Snapshot")

cycle = st.sidebar.number_input("Cycle count", 0, 5000, 1420)
voltage = st.sidebar.number_input("Voltage (V)", 0.0, 5.0, 3.75, step=0.01)
temperature = st.sidebar.number_input("Temperature (C)", -10.0, 80.0, 28.0)
capacity = st.sidebar.number_input("Current capacity (Ah)", 0.0, 200.0, 32.0)
soh = st.sidebar.slider("SoH (%)", 0.0, 100.0, 68.0)

st.sidebar.markdown("---")
st.sidebar.subheader("Safety")
safe = st.sidebar.checkbox("Passed safety check", value=True)
damaged = st.sidebar.checkbox("Physically damaged / swollen", value=False)


# ----- Run pipeline only when requested -----
if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None

if st.button("Analyse Battery", type="primary"):
    registered_battery = get_battery(battery_id)

    if not registered_battery:
        st.error(
            f"Battery {battery_id} is not registered in the Battery Passport. "
            "Register it in the Seller dashboard first."
        )
        st.stop()

    result = analyse_battery(
        battery_id=battery_id,
        chemistry=chemistry,
        capacity_kwh=capacity_kwh,
        weight_kg=weight_kg,
        cycle=cycle,
        voltage=voltage,
        temperature=temperature,
        capacity=capacity,
        soh=soh,
        safe=safe,
        damaged=damaged,
    )

    add_health_snapshot(
        battery_id=battery_id,
        cycle_count=cycle,
        soh=result["soh"],
        rul=result["rul"],
        voltage=voltage,
        temperature=temperature,
    )

    record_decision(
        battery_id=battery_id,
        action=result["decision"],
        confidence=result["confidence"],
        reasons=result.get("reasons", []),
        recommended_centre=(
            result["centres"][0].get("centre_id")
            if result.get("centres")
            else None
        ),
    )

    log_analysis(result, source="app")
    st.session_state.analysis_result = result

result = st.session_state.analysis_result

if result is None:
    st.info("Enter the battery details in the sidebar, then click Analyse Battery.")
    st.stop()

# ----- Top row: key metrics -----
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Battery type", result["chemistry"])
col2.metric("SoH", f"{result['soh']:.1f} %")
col3.metric("RUL", f"{result['rul']} cycles")
col4.metric("Model", result["model_name"])
if result["carbon_avoided_kg"] > 0:
    col5.metric("CO2 avoided", f"{result['carbon_avoided_kg']:.0f} kg")
else:
    col5.metric("CO2 avoided", "--")

st.markdown("---")

# ----- Decision banner -----
action = result["decision"]
colour_map = {
    "CONTINUE_EV": "GREEN",
    "SECOND_LIFE": "YELLOW",
    "REPAIR": "ORANGE",
    "RECYCLE": "RED",
    "RECYCLE_HAZARDOUS": "DANGER",
}
tag = colour_map.get(action, "")
st.subheader(f"Recommendation [{tag}]: {action}")
st.progress(min(1.0, result["confidence"]))
st.write(f"Confidence: {result['confidence']*100:.0f}%")

with st.expander("Why this recommendation?"):
    for r in result["reasons"]:
        st.write(f"- {r}")

st.markdown("---")

# ----- Materials + Centres -----
if result["materials"]:
    left, right = st.columns(2)

    with left:
        st.subheader("Recoverable Materials")
        rows = []
        for mat, data in result["materials"]["recoverable"].items():
            rows.append({
                "Material": mat,
                "Content (kg)": data["content_kg"],
                "Recovered (kg)": data["recovered_kg"],
                "Rate": f"{data['rate']*100:.0f}%",
            })
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

        st.markdown("**Hazardous / controlled handling**")
        for mat, kg in result["materials"]["hazardous"].items():
            st.write(f"- {mat}: {kg:.2f} kg")
        st.caption(f"Residual (slag / losses): {result['materials']['residual_kg']} kg")

    with right:
        st.subheader("Recommended Recycling Centres")
        if result["centres"]:
            cdf = pd.DataFrame(result["centres"])[
                ["centre_name", "distance_km", "score"]
            ].rename(columns={
                "centre_name": "Centre",
                "distance_km": "Distance (km)",
                "score": "Score",
            })
            st.dataframe(cdf, width="stretch", hide_index=True)
            top = result["centres"][0]
            st.success(f"Top pick: {top['centre_name']} "
                       f"({top['distance_km']} km, score {top['score']})")
        else:
            st.warning("No suitable centre found for this chemistry.")
else:
    st.info("Battery is still usable - no recycling required.")



# ----- Environmental impact (carbon) -----
st.markdown("---")

if result["carbon_avoided_kg"] > 0:
    st.subheader("Environmental impact")
    st.metric(
        "CO2 emissions avoided by recycling this battery",
        f"{result['carbon_avoided_kg']:.0f} kg",
    )
    st.caption(
        "Equivalent to ~{:,.0f} km of average car driving. "
        "Factors from Argonne GREET model (2023).".format(
            result["carbon_avoided_kg"] / 0.25
        )
    )

    with st.expander("Breakdown by material"):
        cdf = pd.DataFrame(result["carbon_breakdown"])
        cdf = cdf.rename(columns={
            "material": "Material",
            "recovered_kg": "Recovered (kg)",
            "co2_factor": "CO2 factor (kg/kg)",
            "co2_avoided_kg": "CO2 avoided (kg)",
        })
        st.dataframe(cdf, width="stretch", hide_index=True)
else:
    st.info("No CO2 savings - battery is still usable, no recycling needed.")


# ----- Download PDF report -----
st.markdown("---")
st.subheader("Export report")

pdf_bytes = generate_report(result)
st.download_button(
    label="Download PDF report",
    data=pdf_bytes,
    file_name=f"battery_report_{result['battery_id']}.pdf",
    mime="application/pdf",
)
st.caption(
    "One-page PDF summary: battery details, decision, materials, "
    "recycling centre, and CO2 savings."
)
