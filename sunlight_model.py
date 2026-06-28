from collections import deque


class PhoenixSunlightModel:

    """
    TSKY Sunlight Engine v2.0

    Purpose:
    Tracks usable solar illumination
    for power generation systems.

    """

    def __init__(self):

        print("Deploying TSKY Sunlight Engine v2.0...")

        self.SOLAR_CONSTANT_W_M2 = 1361.0

        self.sunlit_minutes = 0.0
        self.total_minutes = 0.0

        self.recent_history = deque(maxlen=1440)

        self.eclipse_duration_minutes = 0.0

    def update_telemetry(

        self,

        is_sunlit: bool,

        solar_efficiency_pct: float,

        sim_seconds: float

    ):

        minutes = sim_seconds / 60.0

        self.total_minutes += minutes

        if is_sunlit:

            self.sunlit_minutes += minutes

            self.eclipse_duration_minutes = 0.0

            eclipse_state = "FULL_SUN"

        else:

            self.eclipse_duration_minutes += minutes

            eclipse_state = "ECLIPSE"

        self.recent_history.append(
            1 if is_sunlit else 0
        )

        sunlight_availability_pct = (

            self.sunlit_minutes /

            max(self.total_minutes, 1e-6)

        ) * 100

        sunlight_intensity_pct = (

            solar_efficiency_pct

            if is_sunlit

            else 0.0

        )

        solar_flux = (

            self.SOLAR_CONSTANT_W_M2 *

            sunlight_intensity_pct / 100.0

        )

        usable_solar_fraction = (

            sunlight_intensity_pct / 100.0

        )

        return {

            "is_sunlit":
                is_sunlit,

            "eclipse_state":
                eclipse_state,

            "sunlight_intensity_pct":
                round(
                    sunlight_intensity_pct,
                    2
                ),

            "solar_flux_w_m2":
                round(
                    solar_flux,
                    2
                ),

            "eclipse_duration_minutes":
                round(
                    self.eclipse_duration_minutes,
                    2
                ),

            "sunlight_availability_pct":
                round(
                    sunlight_availability_pct,
                    2
                ),

            "usable_solar_fraction":
                round(
                    usable_solar_fraction,
                    4
                )
        }