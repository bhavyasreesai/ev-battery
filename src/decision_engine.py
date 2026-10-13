from dataclasses import dataclass, field
from typing import List


@dataclass
class BatteryState:
    battery_id: str
    chemistry: str = "unknown"
    soh: float = 100.0
    rul: int = 1000
    cycle_count: int = 0
    safe: bool = True
    damaged: bool = False


@dataclass
class Decision:
    action: str
    confidence: float
    reasons: List[str] = field(default_factory=list)


def decide(state):
    reasons = []

    if state.damaged:
        reasons.append("Battery physically damaged / swollen")
        reasons.append("Safety hazard - immediate controlled handling")
        return Decision("RECYCLE_HAZARDOUS", 1.0, reasons)

    if not state.safe:
        reasons.append("Failed safety check")
        return Decision("RECYCLE", 0.95, reasons)

    if state.soh >= 80 and state.rul >= 200:
        reasons.append(f"SoH {state.soh:.1f}% >= 80%")
        reasons.append(f"RUL {state.rul} cycles >= 200")
        return Decision("CONTINUE_EV", 0.92, reasons)

    if 60 <= state.soh < 80 and state.rul >= 50:
        reasons.append(f"SoH {state.soh:.1f}% in second-life band (60-80%)")
        reasons.append(f"RUL {state.rul} cycles still useful")
        return Decision("SECOND_LIFE", 0.85, reasons)

    if 40 <= state.soh < 60 and state.rul >= 50:
        reasons.append(f"SoH {state.soh:.1f}% in repair band (40-60%)")
        return Decision("REPAIR", 0.70, reasons)

    if state.soh < 40:
        reasons.append(f"SoH {state.soh:.1f}% below 40%")
    if state.rul < 50:
        reasons.append(f"RUL {state.rul} cycles critically low")
    if state.soh >= 40 and state.rul < 50:
        reasons.append(
            f"SoH {state.soh:.1f}% would allow second-life, "
            f"but RUL {state.rul} cycles is too low"
        )
    return Decision("RECYCLE", 0.90, reasons)


if __name__ == "__main__":
    tests = [
        BatteryState("EVB-001", "NMC", soh=92, rul=800, safe=True),
        BatteryState("EVB-002", "LFP", soh=72, rul=300, safe=True),
        BatteryState("EVB-003", "NMC", soh=55, rul=150, safe=True),
        BatteryState("EVB-004", "LFP", soh=35, rul=20, safe=True),
        BatteryState("EVB-005", "NMC", soh=88, rul=600, safe=True, damaged=True),
        BatteryState("EVB-006", "NMC", soh=75, rul=250, safe=False),
    ]
    for b in tests:
        d = decide(b)
        print(f"{b.battery_id} | SoH={b.soh:5.1f}% RUL={b.rul:4d} safe={b.safe} damaged={b.damaged}")
        print(f"  -> {d.action:20s} (confidence {d.confidence:.2f})")
        for r in d.reasons:
            print(f"     - {r}")
        print()
