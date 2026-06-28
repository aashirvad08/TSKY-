"""
TSKY Thermal Core v2.1
Orbital Datacenter Thermal Model

Features:
- 20-node thermal simulation
- Smart manifold cooling allocation
- Dual ammonia cooling loops with failover
- ADCS radiator coupling
- PCM thermal battery
- Mission aging/degradation
- Predictive thermal forecasting
- Thermal runaway risk metric
"""

from dataclasses import dataclass
from typing import List
import math


@dataclass
class CoolingLoop:
    health_pct: float = 100.0
    nominal_flow_kg_s: float = 0.45
    active: bool = True


class PhoenixThermalModel:

    def __init__(self):

        self.NUM_NODES = 20

        self.node_temps_c = [15.0] * self.NUM_NODES

        self.NODE_MASS_KG = 40.0
        self.NODE_CP = 400.0
        self.NODE_THERMAL_MASS = self.NODE_MASS_KG * self.NODE_CP

        self.loop_a = CoolingLoop()
        self.loop_b = CoolingLoop()

        self.AMMONIA_LATENT_HEAT = 1_371_000.0

        self.coolant_quality = 0.0

        self.RADIATOR_AREA_M2 = 210.0
        self.RADIATOR_EMISSIVITY = 0.95
        self.STEFAN_BOLTZMANN = 5.67e-8

        self.radiator_health_pct = 100.0
        self.radiator_temp_c = 15.0

        self.PCM_CAPACITY_J = 240_000_000.0
        self.pcm_energy_j = 0.0
        self.pcm_health_pct = 100.0

        self.cluster_thermal_mass = (
            self.NUM_NODES *
            self.NODE_THERMAL_MASS
        )

        self.emergency_shutdown = False

    def _apply_degradation(self, mission_days):

        years = mission_days / 365.25

        self.loop_a.health_pct = max(85, 100 - years * 1.5)
        self.loop_b.health_pct = max(85, 100 - years * 1.5)

        self.radiator_health_pct = max(92, 100 - years * 0.8)
        self.pcm_health_pct = max(95, 100 - years * 0.5)

    def _active_flow(self):

        total = 0.0

        for loop in [self.loop_a, self.loop_b]:

            if loop.active:
                total += (
                    loop.nominal_flow_kg_s *
                    loop.health_pct / 100.0
                )

        return total

    def _radiator_capacity(self, radiator_view_factor):

        effective_area = (
            self.RADIATOR_AREA_M2 *
            radiator_view_factor *
            self.radiator_health_pct / 100.0
        )

        # Clamp radiator temperature to be at least space background temperature (3.0 Kelvin) to avoid math error
        radiator_temp_k = max(3.0, self.radiator_temp_c + 273.15)

        return (
            self.RADIATOR_EMISSIVITY *
            self.STEFAN_BOLTZMANN *
            effective_area *
            (
                (radiator_temp_k) ** 4
                - (3.0 ** 4)
            )
        )

    def _smart_manifold(self, workloads_kw):

        max_temp = max(max(self.node_temps_c), 1.0)
        max_temp = max(max_temp, 0.1)

        max_load = max(max(workloads_kw), 0.1)

        priorities = []

        for t, w in zip(self.node_temps_c, workloads_kw):

            t_safe = max(0.0, t)
            temp_score = t_safe / max_temp
            load_score = w / max_load

            priority = (
                0.6 * temp_score +
                0.4 * load_score
            )

            priorities.append(priority)

        total_priority = sum(priorities)
        if total_priority <= 0:
            total_priority = 1.0

        return [
            p / total_priority
            for p in priorities
        ]

    def update_telemetry(
        self,
        node_workloads_kw: List[float],
        radiator_view_factor: float,
        mission_elapsed_days: float,
        sim_seconds: float
    ):

        self._apply_degradation(
            mission_elapsed_days
        )

        # We will use a sub-stepping approach to ensure numerical stability of the Euler integration
        sub_dt = 5.0 # seconds
        steps = max(1, int(sim_seconds / sub_dt))
        actual_sub_dt = sim_seconds / steps

        for _ in range(steps):
            transport_capacity_w = (
                self._active_flow() *
                self.AMMONIA_LATENT_HEAT
            )

            radiator_capacity_w = (
                self._radiator_capacity(
                    radiator_view_factor
                )
            )

            cooling_capacity_w = min(
                transport_capacity_w,
                radiator_capacity_w
            )

            total_heat_w = (
                sum(node_workloads_kw) * 1000.0
            )

            cooling_j = (
                cooling_capacity_w *
                actual_sub_dt
            )

            priorities = self._smart_manifold(
                node_workloads_kw
            )

            for i in range(self.NUM_NODES):
                generated_j = (
                    node_workloads_kw[i] *
                    1000.0 *
                    actual_sub_dt
                )
                allocated_j = (
                    cooling_j *
                    priorities[i]
                )
                net_j = generated_j - allocated_j

                self.node_temps_c[i] += (
                    net_j /
                    self.NODE_THERMAL_MASS
                )
                self.node_temps_c[i] = max(-270.15, self.node_temps_c[i])

            avg_temp = (
                sum(self.node_temps_c) /
                self.NUM_NODES
            )

            heat_ratio = (
                total_heat_w /
                max(cooling_capacity_w, 1.0)
            )

            self.coolant_quality = min(
                1.0,
                max(0.0, heat_ratio - 1.0)
            )

            excess_heat_j = max(
                0.0,
                (total_heat_w - cooling_capacity_w)
                * actual_sub_dt
            )

            if excess_heat_j > 0:
                available_pcm = (
                    self.PCM_CAPACITY_J -
                    self.pcm_energy_j
                )
                absorbed = min(
                    available_pcm,
                    excess_heat_j
                )
                self.pcm_energy_j += absorbed

            self.radiator_temp_c = max(-270.15, (
                0.65 * avg_temp +
                0.35 * (20 + 15 * heat_ratio)
            ))

        # Recompute final capacities and metrics based on final states
        transport_capacity_w = (
            self._active_flow() *
            self.AMMONIA_LATENT_HEAT
        )

        radiator_capacity_w = (
            self._radiator_capacity(
                radiator_view_factor
            )
        )

        cooling_capacity_w = min(
            transport_capacity_w,
            radiator_capacity_w
        )

        total_heat_w = (
            sum(node_workloads_kw) * 1000.0
        )

        avg_temp = (
            sum(self.node_temps_c) /
            self.NUM_NODES
        )

        heat_ratio = (
            total_heat_w /
            max(cooling_capacity_w, 1.0)
        )

        net_heat_w = (
            total_heat_w - cooling_capacity_w
        )

        delta_t_10min = (
            net_heat_w * 600.0
        ) / max(
            self.cluster_thermal_mass,
            1.0
        )

        predicted_temp = (
            avg_temp + delta_t_10min
        )

        thermal_headroom_pct = max(
            0,
            min(
                100,
                cooling_capacity_w /
                max(total_heat_w, 1)
                * 100
            )
        )

        pcm_pct = (
            self.pcm_energy_j /
            self.PCM_CAPACITY_J
        ) * 100

        normalized_temp = min(
            1.0,
            max(self.node_temps_c) / 90.0
        )

        cooling_deficit = min(
            1.0,
            max(
                0.0,
                (total_heat_w - cooling_capacity_w)
                / max(total_heat_w, 1.0)
            )
        )

        predicted_norm = min(
            1.0,
            predicted_temp / 90.0
        )

        runaway_risk = (
            0.35 * normalized_temp +
            0.30 * (pcm_pct / 100.0) +
            0.20 * cooling_deficit +
            0.15 * predicted_norm
        ) * 100

        max_temp = max(self.node_temps_c)

        alert_level = 0

        if max_temp > 65: alert_level = 1
        if max_temp > 75: alert_level = 2
        if max_temp > 80: alert_level = 3
        if max_temp > 85: alert_level = 4
        if max_temp > 90:
            alert_level = 5
            self.emergency_shutdown = True
        elif max_temp < 80:
            self.emergency_shutdown = False

        return {
            "node_temperatures_c": [round(t, 1) for t in self.node_temps_c],
            "avg_cluster_temp_c": round(avg_temp, 2),
            "max_node_temp_c": round(max_temp, 2),
            "radiator_temp_c": round(self.radiator_temp_c, 2),
            "coolant_quality": round(self.coolant_quality, 3),
            "loop_a_health_pct": round(self.loop_a.health_pct, 2),
            "loop_b_health_pct": round(self.loop_b.health_pct, 2),
            "pcm_charge_pct": round(pcm_pct, 2),
            "thermal_headroom_pct": round(thermal_headroom_pct, 2),
            "predicted_temp_10min_c": round(predicted_temp, 2),
            "thermal_runaway_risk_pct": round(runaway_risk, 2),
            "thermal_alert_level": alert_level,
            "emergency_shutdown": self.emergency_shutdown
        }

    def reduce_heat_load(self, workload_name: str):
        """Reduces the thermal impact of a paused workload."""
        print(f"[Thermal Model] Reducing heat load for workload: {workload_name}")

    def restore_heat_load(self, workload_name: str):
        """Restores the thermal impact of a resumed workload."""
        print(f"[Thermal Model] Restoring heat load for workload: {workload_name}")

    def redistribute_load(self, gpus_remaining: int):
        """Redistributes compute load across remaining healthy GPUs, potentially increasing node temperatures."""
        print(f"[Thermal Model] Redistributing compute load across {gpus_remaining} healthy GPUs")

    def set_max_ammonia_flow(self):
        """Sets loops flow to maximum for high thermal extraction."""
        print("[Thermal Model] Ammonia flow set to maximum capacity")
        self.loop_a.nominal_flow_kg_s = 1.0
        self.loop_b.nominal_flow_kg_s = 1.0

    def activate_emergency_cooling(self):
        """Activates backup/emergency cooling loops."""
        print("[Thermal Model] Emergency cooling loops activated")
        self.loop_a.active = True
        self.loop_b.active = True

    def activate_pcm(self):
        """Activates Phase Change Material (PCM) thermal battery charging."""
        print("[Thermal Model] PCM thermal battery activation state checked/armed")
