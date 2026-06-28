import math


class PhoenixADCS:
    """
    TSKY Orbital Data Center
    Autonomous Attitude Determination & Control System v2.0

    Mission Modes:

    SCIENCE_MODE
    POWER_MODE
    THERMAL_MODE
    SAFE_MODE
    DEBRIS_AVOIDANCE

    """

    def __init__(self):

        print("Deploying TSKY ADCS v2.0...")

        # =====================================================
        # ATTITUDE STATE
        # =====================================================

        self.attitude_mode = "SCIENCE_MODE"

        self.yaw_deg = 0.0
        self.pitch_deg = 0.0
        self.roll_deg = 0.0

        # =====================================================
        # HEALTH STATE
        # =====================================================

        self.reaction_wheel_health_pct = 100.0
        self.solar_array_health_pct = 100.0
        self.sensor_health_pct = 100.0

        # =====================================================
        # MOMENTUM STORAGE
        # =====================================================

        self.reaction_wheel_momentum_pct = 10.0
        self.momentum_dump_active = False

        # =====================================================
        # POINTING OBJECTIVES
        # =====================================================

        self.sun_alignment = 0.90
        self.radiator_alignment = 0.85
        self.antenna_alignment = 0.90

    # =========================================================
    # MISSION AGING MODEL
    # =========================================================

    def _apply_degradation(self, mission_elapsed_days):

        mission_years = mission_elapsed_days / 365.25

        self.solar_array_health_pct = max(
            75.0,
            100.0 - mission_years * 2.0
        )

        self.reaction_wheel_health_pct = max(
            80.0,
            100.0 - mission_years * 1.0
        )

        self.sensor_health_pct = max(
            85.0,
            100.0 - mission_years * 0.5
        )

    # =========================================================
    # MOMENTUM MANAGEMENT
    # =========================================================

    def _manage_reaction_wheels(self):

        if self.reaction_wheel_momentum_pct > 80:

            self.momentum_dump_active = True

            self.reaction_wheel_momentum_pct -= 40

        else:

            self.momentum_dump_active = False

    # =========================================================
    # ATTITUDE MODE SELECTION
    # =========================================================

    def _determine_mode(
        self,
        battery_pct,
        radiator_temp_c,
        max_node_temp_c,
        pcm_pct,
        debris_warning
    ):

        if battery_pct < 15:
            return "SAFE_MODE"

        if debris_warning:
            return "DEBRIS_AVOIDANCE"

        if (
            radiator_temp_c > 65
            or max_node_temp_c > 75
            or pcm_pct > 60
        ):
            return "THERMAL_MODE"

        if battery_pct < 40:
            return "POWER_MODE"

        return "SCIENCE_MODE"

    # =========================================================
    # ATTITUDE OPTIMIZER
    # =========================================================

    def _optimize_orientation(
        self,
        mode,
        power_need,
        thermal_need,
        comm_need
    ):

        if mode == "POWER_MODE":

            self.sun_alignment = 1.00
            self.radiator_alignment = 0.75
            self.antenna_alignment = 0.75

        elif mode == "THERMAL_MODE":

            self.sun_alignment = 0.75
            self.radiator_alignment = 1.00
            self.antenna_alignment = 0.80

        elif mode == "DEBRIS_AVOIDANCE":

            self.sun_alignment = 0.65
            self.radiator_alignment = 0.70
            self.antenna_alignment = 0.60

        elif mode == "SAFE_MODE":

            self.sun_alignment = 1.00
            self.radiator_alignment = 0.90
            self.antenna_alignment = 0.50

        else:

            self.sun_alignment = (
                0.50 +
                0.50 * (1 - power_need)
            )

            self.radiator_alignment = (
                0.50 +
                0.50 * thermal_need
            )

            self.antenna_alignment = (
                0.80 +
                0.20 * comm_need
            )

    # =========================================================
    # MAIN UPDATE LOOP
    # =========================================================

    def update_telemetry(

        self,

        # ORBIT
        is_sunlit,
        debris_warning,
        mission_elapsed_days,

        # POWER
        battery_charge_pct,
        power_demand_kw,
        solar_generation_kw,

        # THERMAL
        avg_cluster_temp_c,
        max_node_temp_c,
        radiator_temp_c,
        pcm_saturation_pct,

        sim_seconds

    ):

        # =====================================================
        # DEGRADATION
        # =====================================================

        self._apply_degradation(
            mission_elapsed_days
        )

        # =====================================================
        # RESOURCE PRESSURE
        # =====================================================

        power_need = (
            1.0 -
            (battery_charge_pct / 100.0)
        )

        thermal_need = min(
            1.0,
            radiator_temp_c / 85.0
        )

        comm_need = min(
            1.0,
            power_demand_kw / 80.0
        )

        # =====================================================
        # ATTITUDE MODE
        # =====================================================

        self.attitude_mode = (
            self._determine_mode(
                battery_charge_pct,
                radiator_temp_c,
                max_node_temp_c,
                pcm_saturation_pct,
                debris_warning
            )
        )

        # =====================================================
        # ATTITUDE OPTIMIZATION
        # =====================================================

        self._optimize_orientation(
            self.attitude_mode,
            power_need,
            thermal_need,
            comm_need
        )

        # =====================================================
        # SUN VECTOR MODEL
        # =====================================================

        if is_sunlit:

            sun_incidence_deg = (
                (1.0 - self.sun_alignment)
                * 90.0
            )

        else:

            sun_incidence_deg = 180.0

        solar_efficiency = max(
            0.0,
            math.cos(
                math.radians(
                    sun_incidence_deg
                )
            )
        )

        solar_efficiency *= (
            self.solar_array_health_pct
            / 100.0
        )

        # =====================================================
        # RADIATOR MODEL
        # =====================================================

        radiator_view_factor = (
            self.radiator_alignment
        )

        # =====================================================
        # ANTENNA MODEL
        # =====================================================

        antenna_alignment_pct = (
            self.antenna_alignment
            * self.sensor_health_pct
            / 100.0
        )

        # =====================================================
        # REACTION WHEEL MODEL
        # =====================================================

        maneuver_load = (
            abs(self.sun_alignment - 0.5)
            + abs(self.radiator_alignment - 0.5)
        )

        self.reaction_wheel_momentum_pct += (
            maneuver_load * 2.0
        )

        self.reaction_wheel_momentum_pct = min(
            100,
            self.reaction_wheel_momentum_pct
        )

        self._manage_reaction_wheels()

        # =====================================================
        # ATTITUDE TELEMETRY
        # =====================================================

        self.yaw_deg = (
            self.sun_alignment * 25
        )

        self.pitch_deg = (
            self.radiator_alignment * 25
        )

        self.roll_deg = (
            self.antenna_alignment * 10
        )

        # =====================================================
        # HEADROOM CALCULATIONS
        # =====================================================

        thermal_headroom_pct = max(
            0,
            min(
                100,
                (
                    (85 - max_node_temp_c)
                    / 85
                ) * 100
            )
        )

        power_headroom_pct = max(
            0,
            battery_charge_pct
        )

        optimization_score = (

            0.45 * power_need +

            0.35 * thermal_need +

            0.20 * comm_need

        )

        # =====================================================
        # TELEMETRY
        # =====================================================

        return {

            "attitude_mode":
                self.attitude_mode,

            "yaw_deg":
                round(self.yaw_deg, 2),

            "pitch_deg":
                round(self.pitch_deg, 2),

            "roll_deg":
                round(self.roll_deg, 2),

            "sun_incidence_deg":
                round(
                    sun_incidence_deg,
                    2
                ),

            "solar_efficiency_pct":
                round(
                    solar_efficiency * 100,
                    2
                ),

            "radiator_view_factor":
                round(
                    radiator_view_factor,
                    3
                ),

            "antenna_alignment_pct":
                round(
                    antenna_alignment_pct * 100,
                    2
                ),

            "reaction_wheel_health_pct":
                round(
                    self.reaction_wheel_health_pct,
                    2
                ),

            "reaction_wheel_momentum_pct":
                round(
                    self.reaction_wheel_momentum_pct,
                    2
                ),

            "solar_array_health_pct":
                round(
                    self.solar_array_health_pct,
                    2
                ),

            "sensor_health_pct":
                round(
                    self.sensor_health_pct,
                    2
                ),

            "thermal_headroom_pct":
                round(
                    thermal_headroom_pct,
                    2
                ),

            "power_headroom_pct":
                round(
                    power_headroom_pct,
                    2
                ),

            "optimization_score":
                round(
                    optimization_score,
                    3
                ),

            "alerts": {

                "safe_mode":
                    self.attitude_mode
                    == "SAFE_MODE",

                "thermal_priority":
                    self.attitude_mode
                    == "THERMAL_MODE",

                "power_priority":
                    self.attitude_mode
                    == "POWER_MODE",

                "debris_avoidance":
                    self.attitude_mode
                    == "DEBRIS_AVOIDANCE",

                "momentum_dump_active":
                    self.momentum_dump_active,

                "wheel_saturation":
                    self.reaction_wheel_momentum_pct
                    > 70

            }
        }