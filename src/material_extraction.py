"""
Module 4 - Material extraction estimator.

Given a battery's chemistry and weight, estimate:
  - mass of each material present
  - mass recoverable (using literature recovery rates)
  - mass of hazardous / hard-to-recover residual
"""

# Material composition as fraction of total battery weight
# Sources: Argonne GREET model + common EV battery recycling literature
MATERIALS = {
    "LFP": {"Li": 0.035, "Fe": 0.20, "P": 0.03,
            "Graphite": 0.20, "Cu": 0.08, "Al": 0.12,
            "Electrolyte": 0.10, "Separator": 0.02},
    "NMC": {"Li": 0.02, "Ni": 0.10, "Mn": 0.05, "Co": 0.03,
            "Graphite": 0.20, "Cu": 0.08, "Al": 0.12,
            "Electrolyte": 0.10, "Separator": 0.02},
    "NCA": {"Li": 0.02, "Ni": 0.12, "Co": 0.04, "Al": 0.05,
            "Graphite": 0.20, "Cu": 0.08,
            "Electrolyte": 0.10, "Separator": 0.02},
    "LMO": {"Li": 0.02, "Mn": 0.15,
            "Graphite": 0.20, "Cu": 0.08, "Al": 0.12,
            "Electrolyte": 0.10, "Separator": 0.02},
}

# Recovery efficiency (fraction of material that can be recovered)
RECOVERY_RATE = {
    "Li": 0.90, "Ni": 0.96, "Co": 0.95, "Mn": 0.90,
    "Cu": 0.98, "Al": 0.97, "Graphite": 0.90,
    "Fe": 0.00, "P": 0.00,
    "Electrolyte": 0.00,   # hazardous, handled separately
    "Separator": 0.00,     # usually incinerated
}

# Materials that must be handled as hazardous waste
HAZARDOUS = {"Electrolyte", "Separator"}


def extract_materials(chemistry, weight_kg):
    chemistry = chemistry.upper()
    if chemistry not in MATERIALS:
        raise ValueError(f"Unknown chemistry: {chemistry}")

    composition = MATERIALS[chemistry]
    results = {"recoverable": {}, "hazardous": {}, "residual_kg": 0.0}

    for material, fraction in composition.items():
        content_kg = weight_kg * fraction
        rate = RECOVERY_RATE.get(material, 0.0)

        if material in HAZARDOUS:
            results["hazardous"][material] = content_kg
            results["residual_kg"] += content_kg
        elif rate > 0:
            recovered = content_kg * rate
            results["recoverable"][material] = {
                "content_kg": round(content_kg, 2),
                "recovered_kg": round(recovered, 2),
                "rate": rate,
            }
            results["residual_kg"] += (content_kg - recovered)
        else:
            # Fe, P, non-recoverable -> slag/residual
            results["residual_kg"] += content_kg

    results["residual_kg"] = round(results["residual_kg"], 2)
    return results


def format_report(chemistry, weight_kg, results):
    print(f"\nChemistry : {chemistry}")
    print(f"Weight    : {weight_kg} kg")
    print("-" * 55)
    print(f"{'Material':<12}{'Content':>12}{'Recovered':>12}{'Rate':>8}")
    print("-" * 55)
    for mat, data in results["recoverable"].items():
        print(f"{mat:<12}{data['content_kg']:>10.2f}kg"
              f"{data['recovered_kg']:>10.2f}kg"
              f"{data['rate']*100:>7.0f}%")
    if results["hazardous"]:
        print("-" * 55)
        print("HAZARDOUS / controlled:")
        for mat, kg in results["hazardous"].items():
            print(f"  {mat:<12}{kg:>10.2f}kg")
    print("-" * 55)
    print(f"Residual (slag / losses): {results['residual_kg']} kg")


if __name__ == "__main__":
    tests = [
        ("NMC", 300),
        ("LFP", 200),
        ("NCA", 350),
        ("LMO", 250),
    ]
    for chem, weight in tests:
        r = extract_materials(chem, weight)
        format_report(chem, weight, r)
