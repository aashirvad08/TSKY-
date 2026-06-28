import asyncio
from datetime import datetime, timedelta, timezone
from skyfield.api import load, EarthSatellite, wgs84
import random

class OrbitalSpigot:
    def __init__(self, start_time=None, time_dilation_factor=600):
        """
        time_dilation_factor: How fast time moves.
        600 means 1 real second = 600 simulation seconds (10 minutes).
        This is critical so your demo shows a full orbit in ~9 real-world seconds.
        """
        print("Initializing Async Orbital Physics Engine...")
        self.ts = load.timescale()
        self.eph = load('de421.bsp')

        # Dawn-Dusk SSO Proxy TLE
        line1 = '1 23710U 95059A   23301.12345678  .00000123  00000-0  12345-4 0  9999'
        line2 = '2 23710  98.5780  80.1234 0001234  90.0000 270.0000 14.29812345123456'
        self.satellite = EarthSatellite(line1, line2, 'Tsukuyomi-1', self.ts)

        # Set the starting clock
        self.current_sim_time = start_time or datetime.now(timezone.utc)
        self.time_dilation = time_dilation_factor
        
    def _calculate_state(self) -> dict:
        """Internal synchronous math function."""
        t = self.ts.from_datetime(self.current_sim_time)
        geocentric = self.satellite.at(t)
        subpoint = wgs84.subpoint(geocentric)
        
        is_sunlit = geocentric.is_sunlit(self.eph)
        debris_warning = random.random() < 0.005 # 0.5% chance per tick

        return {
            "timestamp": self.current_sim_time.isoformat(),
            "orbit_type": "SSO (Dawn-Dusk)",
            "is_sunlit": bool(is_sunlit),
            "latitude": round(subpoint.latitude.degrees, 4),
            "longitude": round(subpoint.longitude.degrees, 4),
            "altitude_km": round(subpoint.elevation.km, 2),
            "hazard_debris_warning": debris_warning
        }
    def update(self) -> dict:
        """
        Advance the simulation clock and return the new state.
        Fits PhoenixMissionCore's expectations.
        """
        self.current_sim_time += timedelta(seconds=self.time_dilation)
        state = self._calculate_state()
        state["debris_warning"] = state.get("hazard_debris_warning", False)
        return state

    async def telemetry_stream(self, current_sim_time):
        """
        ASYNC GENERATOR: This is what FastAPI will consume.
        It yields a new state, advances the clock, and waits 1 real second.
        """
        while True:
            # 1. Calculate current physics
            state = self._calculate_state()
            
            # 2. Yield data to FastAPI
            yield state
            
            # 3. Fast-forward the simulation clock by our dilation factor
            self.current_sim_time += timedelta(seconds=self.time_dilation)
            
            # 4. Sleep for 1 real-world second before the next tick
            await asyncio.sleep(1)