from dataclasses import dataclass


@dataclass
class BatteryBank:
    charge_j: float
    max_j: float
    health_pct: float = 100.0


class PhoenixPowerModel:

    def __init__(self):

        print("Deploying TSKY Power Core v2.0...")

        # =====================================================
        # SOLAR ARRAYS
        # =====================================================

        self.BOL_SOLAR_CAPACITY_KW = 70.0
        self.solar_array_health_pct = 100.0

        # =====================================================
        # POWER BUS
        # =====================================================

        self.bus_a_health_pct = 100.0
        self.bus_b_health_pct = 100.0

        # =====================================================
        # SUPERCAPACITORS
        # =====================================================

        self.SUPERCAPACITY_KWH = 10.0

        self.SUPERCAP_MAX_J = (
            self.SUPERCAPACITY_KWH *
            1000 *
            3600
        )

        self.supercap_charge_j = (
            self.SUPERCAP_MAX_J
        )

        # =====================================================
        # BATTERIES
        # =====================================================

        self.TOTAL_BATTERY_KWH = 80.0

        total_battery_j = (
            self.TOTAL_BATTERY_KWH *
            1000 *
            3600
        )

        self.battery_a = BatteryBank(
            charge_j=total_battery_j / 2,
            max_j=total_battery_j / 2
        )

        self.battery_b = BatteryBank(
            charge_j=total_battery_j / 2,
            max_j=total_battery_j / 2
        )

        # =====================================================
        # CRITICAL LOADS
        # =====================================================

        self.flight_computer_kw = 0.5
        self.adcs_kw = 1.0
        self.telemetry_kw = 0.5

        self.cooling_kw = 4.0

        # =====================================================
        # STATES
        # =====================================================

        self.safe_mode = False
        self.emergency_shutdown = False

    # =========================================================
    # AGING MODEL
    # =========================================================

    def _apply_degradation(
        self,
        mission_elapsed_days
    ):

        years = mission_elapsed_days / 365.25

        self.solar_array_health_pct = max(
            80.0,
            100.0 - years * 2.0
        )

        self.bus_a_health_pct = max(
            90.0,
            100.0 - years * 0.5
        )

        self.bus_b_health_pct = max(
            90.0,
            100.0 - years * 0.5
        )

        self.battery_a.health_pct = max(
            80.0,
            100.0 - years * 1.5
        )

        self.battery_b.health_pct = max(
            80.0,
            100.0 - years * 1.5
        )

    # =========================================================
    # BATTERY %
    # =========================================================

    def _battery_charge_pct(self):

        total_charge = (
            self.battery_a.charge_j +
            self.battery_b.charge_j
        )

        total_capacity = (
            self.battery_a.max_j +
            self.battery_b.max_j
        )

        return (
            total_charge /
            total_capacity
        ) * 100

    # =========================================================
    # FUTURE PREDICTION
    # =========================================================

    def _predict_future_charge(
        self,
        battery_pct,
        net_kw
    ):

        future_j = (
            net_kw *
            1000 *
            1800
        )

        total_capacity_j = (
            self.battery_a.max_j +
            self.battery_b.max_j
        )

        predicted = battery_pct + (

            future_j /
            total_capacity_j

        ) * 100

        return max(
            0,
            min(100, predicted)
        )

    # =========================================================
    # POWER STATE
    # =========================================================

    def _determine_power_state(
        self,
        predicted_battery_pct
    ):

        if predicted_battery_pct > 40:
            return "NOMINAL"

        if predicted_battery_pct > 20:
            return "POWER_SAVE"

        if predicted_battery_pct > 5:
            return "THROTTLE"

        return "SAFE_MODE"

    # =========================================================
    # MAIN LOOP
    # =========================================================

    def update_telemetry(

        self,

        is_sunlit: bool,
        solar_efficiency_pct: float,

        gpu_load_kw: float,
        comms_load_kw: float,

        mission_elapsed_days: float,
        sim_seconds: float

    ):

        self._apply_degradation(
            mission_elapsed_days
        )

        # =====================================================
        # SOLAR GENERATION
        # =====================================================

        if is_sunlit:

            generation_kw = (

                self.BOL_SOLAR_CAPACITY_KW *

                (solar_efficiency_pct / 100.0) *

                (self.solar_array_health_pct / 100.0)

            )

        else:

            generation_kw = 0.0

        # =====================================================
        # LOADS
        # =====================================================

        tier1_kw = (

            self.flight_computer_kw +
            self.adcs_kw +
            self.telemetry_kw

        )

        tier2_kw = self.cooling_kw

        total_demand_kw = (

            tier1_kw +
            tier2_kw +
            gpu_load_kw +
            comms_load_kw

        )

        # =====================================================
        # POWER BALANCE
        # =====================================================

        net_kw = (
            generation_kw -
            total_demand_kw
        )

        net_j = (
            net_kw *
            1000 *
            sim_seconds
        )

        # =====================================================
        # CHARGING
        # =====================================================

        if net_j > 0:

            supercap_room = (

                self.SUPERCAP_MAX_J -
                self.supercap_charge_j

            )

            supercap_fill = min(
                supercap_room,
                net_j
            )

            self.supercap_charge_j += (
                supercap_fill
            )

            remaining = (
                net_j -
                supercap_fill
            )

            if remaining > 0:

                half = remaining / 2

                self.battery_a.charge_j = min(
                    self.battery_a.max_j,
                    self.battery_a.charge_j + half
                )

                self.battery_b.charge_j = min(
                    self.battery_b.max_j,
                    self.battery_b.charge_j + half
                )

        # =====================================================
        # DISCHARGING
        # =====================================================

        else:

            deficit = abs(net_j)

            supercap_draw = min(
                deficit,
                self.supercap_charge_j
            )

            self.supercap_charge_j -= (
                supercap_draw
            )

            deficit -= supercap_draw

            if deficit > 0:

                half = deficit / 2

                self.battery_a.charge_j = max(
                    0,
                    self.battery_a.charge_j - half
                )

                self.battery_b.charge_j = max(
                    0,
                    self.battery_b.charge_j - half
                )

        # =====================================================
        # METRICS
        # =====================================================

        battery_pct = (
            self._battery_charge_pct()
        )

        predicted_battery_pct = (
            self._predict_future_charge(
                battery_pct,
                net_kw
            )
        )

        recommended_state = (
            self._determine_power_state(
                predicted_battery_pct
            )
        )

        if recommended_state == "SAFE_MODE":
            self.safe_mode = True

        if battery_pct < 5:
            self.emergency_shutdown = True

        power_headroom_pct = max(
            0,
            min(
                100,
                (
                    generation_kw /
                    max(total_demand_kw, 0.001)
                ) * 100
            )
        )

        supercap_pct = (

            self.supercap_charge_j /

            self.SUPERCAP_MAX_J

        ) * 100

        stored_energy_j = (

            self.supercap_charge_j +

            self.battery_a.charge_j +

            self.battery_b.charge_j

        )

        survivability_hours = (

            stored_energy_j /

            max(
                total_demand_kw * 1000,
                1
            )

        ) / 3600

        return {

            "solar_generation_kw":
                round(generation_kw, 2),

            "total_demand_kw":
                round(total_demand_kw, 2),

            "net_power_kw":
                round(net_kw, 2),

            "solar_array_health_pct":
                round(
                    self.solar_array_health_pct,
                    2
                ),

            "battery_charge_pct":
                round(
                    battery_pct,
                    2
                ),

            "battery_a_health_pct":
                round(
                    self.battery_a.health_pct,
                    2
                ),

            "battery_b_health_pct":
                round(
                    self.battery_b.health_pct,
                    2
                ),

            "supercap_charge_pct":
                round(
                    supercap_pct,
                    2
                ),

            "power_headroom_pct":
                round(
                    power_headroom_pct,
                    2
                ),

            "predicted_battery_30min_pct":
                round(
                    predicted_battery_pct,
                    2
                ),

            "power_survivability_hours":
                round(
                    survivability_hours,
                    2
                ),

            "recommended_power_state":
                recommended_state,

            "alerts": {
                "safe_mode":
                    self.safe_mode,
                "emergency_shutdown":
                    self.emergency_shutdown,
                "low_power":
                    battery_pct < 25,
                "critical_power":
                    battery_pct < 10
            }
        }

    def reduce_power_demand(self, workload_name: str):
        """Reduces system power demand when a workload is paused."""
        print(f"[Power Model] Reducing power demand for workload: {workload_name}")

    def restore_power_demand(self, workload_name: str):
        """Restores workload power demand when a workload is resumed."""
        print(f"[Power Model] Restoring power demand for workload: {workload_name}")

    def update_solar_input(self, solar_power_pct: float):
        """Updates solar array health / input to reflect degradation or routing changes."""
        print(f"[Power Model] Solar array efficiency updated to {solar_power_pct}%")
        self.solar_array_health_pct = solar_power_pct