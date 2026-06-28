from dataclasses import dataclass
from typing import Optional


@dataclass
class FailureEvent:
    type: str          # "gpu_failure" | "debris_strike" | "solar_damage" | "battery_drain"
    description: str
    severity: int      # 1-3 (1 = minor, 3 = critical)
    gpus_lost: int = 0
    power_reduction: float = 0.0   # percentage 0.0-1.0
    heat_spike: float = 0.0        # immediate temp increase


FAILURE_PRESETS = {
    "gpu_failure": FailureEvent(
        type="gpu_failure",
        description="Cosmic radiation damaged GPU module",
        severity=2,
        gpus_lost=1,
        heat_spike=5.0
    ),
    "debris_strike": FailureEvent(
        type="debris_strike",
        description="Micrometeorite impact on GPU cluster A",
        severity=3,
        gpus_lost=3,
        power_reduction=0.15,
        heat_spike=10.0
    ),
    "solar_damage": FailureEvent(
        type="solar_damage",
        description="Solar panel surface degraded",
        severity=2,
        power_reduction=0.25
    ),
    "battery_drain": FailureEvent(
        type="battery_drain",
        description="Battery cell failure detected",
        severity=2,
        power_reduction=0.30
    ),
}
