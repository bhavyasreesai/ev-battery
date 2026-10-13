"""
Carbon savings calculator.

Estimates CO2 emissions avoided by recycling battery materials versus
producing them from virgin sources.

Emission factors (kg CO2 avoided per kg of recycled material) are based on:
  - Argonne National Laboratory GREET model (2023)
  - ICCT Life-Cycle Analysis of EV Batteries (2023)

Values represent a mid-range estimate; actual savings depend on the specific
recycling process (pyro vs hydro), grid mix, and virgin-material baseline.
"""

# kg CO2 avoided per kg of recycled material
CO2_FACTORS = {
    "li_kg":       5.0,   # Lithium
    "co_kg":       4.0,   # Cobalt
    "ni_kg":       3.5,   # Nickel
    "cu_kg":       2.0,   # Copper
    "al_kg":       1.5,   # Aluminium
    "graphite_kg": 1.0,   # Graphite
}

# Display labels for the UI
MATERIAL_LABELS = {
    "li_kg":       "Lithium",
    "co_kg":       "Cobalt",
    "ni_kg":       "Nickel",
    "cu_kg":       "Copper",
    "al_kg":       "Aluminium",
    "graphite_kg": "Graphite",
}


def carbon_avoided(recovered_kg: dict) -> float:
    """
    Given a dict of {material_column: recovered_kg},
    return total CO2 avoided (kg).

    Example:
        >>> carbon_avoided({"li_kg": 10, "cu_kg": 20})
        90.0    # 10*5.0 + 20*2.0
    """
    total = 0.0
    for key, kg in recovered_kg.items():
        factor = CO2_FACTORS.get(key, 0.0)
        total += kg * factor
    return round(total, 2)


def carbon_breakdown(recovered_kg: dict) -> list:
    """
    Returns a list of dicts, one per material, showing the CO2 contribution.
    Useful for tables and charts.
    """
    rows = []
    for key, kg in recovered_kg.items():
        factor = CO2_FACTORS.get(key, 0.0)
        rows.append({
            "material": MATERIAL_LABELS.get(key, key),
            "recovered_kg": round(kg, 2),
            "co2_factor": factor,
            "co2_avoided_kg": round(kg * factor, 2),
        })
    return rows


if __name__ == "__main__":
    # Self-test
    test = {"li_kg": 10, "co_kg": 5, "cu_kg": 20, "al_kg": 30}
    print("Total CO2 avoided:", carbon_avoided(test), "kg")
    print()
    print("Breakdown:")
    for row in carbon_breakdown(test):
        print(f"  {row['material']:10s}  {row['recovered_kg']:6.2f} kg  x {row['co2_factor']}  =  {row['co2_avoided_kg']:8.2f} kg CO2")