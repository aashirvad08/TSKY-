from typing import Dict, List

from .workloads import Workload, default_workloads
from .recovery_engine import RecoveryEngine


class MissionManager:
    def __init__(self, hooks: dict = None):
        self.workloads: List[Workload] = default_workloads()
        self.engine = RecoveryEngine(hooks=hooks)
        self.hooks = hooks or {}

    def apply_recovery(self, satellite_state: dict) -> List[str]:
        actions = []

        for workload in self._by_priority():
            if workload.status == "active" and self.engine.should_pause_workload(workload, satellite_state):
                actions.append(self._pause(workload, "resources critical"))

        for workload in self._by_priority():
            if workload.status == "paused" and self.engine.should_resume_workload(workload, satellite_state):
                workload.status = "active"
                self._call_hook("resume_workload", workload_name=workload.name)
                actions.append(f"Resumed '{workload.name}' — resources recovered")

        actions.extend(self._enforce_gpu_capacity(satellite_state))

        return actions

    def inject_failure(self, failure_type: str, satellite_state: dict):
        from .failure_models import FAILURE_PRESETS
        event = FAILURE_PRESETS.get(failure_type)
        if not event:
            return [f"Unknown failure type: {failure_type}"], {}

        actions, patches = self.engine.handle_failure(event, self.workloads, satellite_state)
        recovery_actions = self.apply_recovery({**satellite_state, **patches})
        return actions + recovery_actions, patches

    def _call_hook(self, name: str, **kwargs):
        fn = self.hooks.get(name)
        if fn:
            try:
                fn(**kwargs)
            except Exception:
                pass

    def _by_priority(self) -> List[Workload]:
        return sorted(self.workloads, key=lambda workload: workload.priority, reverse=True)

    def _pause(self, workload: Workload, reason: str) -> str:
        workload.status = "paused"
        self._call_hook("pause_workload", workload_name=workload.name)
        return f"Paused '{workload.name}' (priority {workload.priority}) — {reason}"

    def _enforce_gpu_capacity(self, satellite_state: dict) -> List[str]:
        healthy_gpus = satellite_state.get("healthy_gpus", 8)
        if healthy_gpus >= 5:
            return []

        protected_slots = 3 if healthy_gpus >= 3 else max(0, healthy_gpus)
        active_by_priority = [w for w in self._by_priority() if w.status == "active"]
        overflow = active_by_priority[protected_slots:]
        return [self._pause(workload, "resources critical") for workload in overflow]

    def get_total_heat(self) -> float:
        return sum(w.heat_generation for w in self.workloads if w.status == "active")

    def get_total_power(self) -> float:
        return sum(w.power_usage for w in self.workloads if w.status == "active")

    def get_status_dict(self) -> List[Dict]:
        return [
            {
                "name": w.name,
                "priority": w.priority,
                "power_usage": w.power_usage,
                "heat_generation": w.heat_generation,
                "status": w.status,
            }
            for w in sorted(self.workloads, key=lambda x: x.priority, reverse=True)
        ]
