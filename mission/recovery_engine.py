from typing import List, Tuple

from .failure_models import FailureEvent
from .workloads import Workload


class RecoveryEngine:
    def __init__(self, hooks: dict = None):
        # hooks are Person 1's functions, injected at startup
        self.hooks = hooks or {}

    def _call_hook(self, name: str, **kwargs):
        """Safely call a Person 1 hook if it exists."""
        fn = self.hooks.get(name)
        if fn:
            try:
                fn(**kwargs)
            except Exception:
                pass

    def handle_failure(
        self,
        event: FailureEvent,
        workloads: List[Workload],
        satellite_state: dict
    ) -> Tuple[List[str], dict]:
        actions = []
        patches = {}

        if event.gpus_lost > 0:
            current = satellite_state.get("healthy_gpus", 8)
            new_count = max(0, current - event.gpus_lost)
            patches["healthy_gpus"] = new_count
            actions.append(
                f"FAILURE DETECTED — GPU loss: {current} → {new_count} healthy GPUs")
            actions.append(f"ROOT CAUSE: {event.description}")

            self._call_hook("enable_backup_gpu", gpus_remaining=new_count)
            actions.append(
                "Backup GPU activated — workload redistribution in progress")
        else:
            actions.append(f"ROOT CAUSE: {event.description}")

        if event.power_reduction > 0:
            current_solar = satellite_state.get("solar_power", 100)
            new_solar = round(current_solar * (1 - event.power_reduction), 1)
            patches["solar_power"] = new_solar
            actions.append(f"Solar power reduced to {new_solar}%")
            self._call_hook("reroute_power", solar_power=new_solar)

        if event.heat_spike > 0:
            current_temp = satellite_state.get("temperature", 40)
            patches["temperature"] = current_temp + event.heat_spike
            actions.append(
                f"Temperature spike: {current_temp:.1f}°C → {patches['temperature']:.1f}°C")
            self._call_hook("activate_cooling")
            actions.append("Thermal control activated")

        return actions, patches

    def should_pause_workload(self, workload: Workload, satellite_state: dict) -> bool:
        battery = satellite_state.get("battery", 100)
        healthy_gpus = satellite_state.get("healthy_gpus", 8)
        temperature = satellite_state.get("temperature", 40)
        blackout = satellite_state.get("blackout", False)

        if battery < 20 and workload.priority < 5:
            return True
        if healthy_gpus <= 3 and workload.priority < 7:
            return True
        if temperature > 85 and workload.priority < 8:
            return True
        if blackout and workload.priority < 7:
            return True
        return False

    def should_resume_workload(self, workload: Workload, satellite_state: dict) -> bool:
        battery = satellite_state.get("battery", 100)
        healthy_gpus = satellite_state.get("healthy_gpus", 8)
        temperature = satellite_state.get("temperature", 40)
        blackout = satellite_state.get("blackout", False)

        return battery > 35 and healthy_gpus >= 5 and temperature < 75 and not blackout
