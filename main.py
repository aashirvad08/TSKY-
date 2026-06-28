"""
FarAway / Tsukuyomi-1  — Unified FastAPI Backend
=================================================
Single process.  All six physics models run in-process.
The simulation loop runs in a background thread; FastAPI
serves the live state + SSE stream to any frontend.

Endpoints
---------
GET  /                          health ping
GET  /telemetry/stream          SSE — new frame every ~1 s
GET  /telemetry/snapshot        latest full telemetry (JSON)
GET  /status                    satellite state + mission list + logs + health score
POST /state                     push external telemetry (legacy compat)
POST /sim/tick                  manual sim advance (body: {seconds: float})
POST /sim/speed                 set time-dilation  (body: {factor: int})
POST /inject/{failure_type}     inject a failure scenario
POST /workload/{name}/pause     pause a named workload
POST /workload/{name}/resume    resume a named workload
POST /ask                       AI explanation (body: {question: str})
POST /reset                     reset everything to nominal
GET  /health                    quick health check
"""

import asyncio
import json
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles

# ── Physics models ──────────────────────────────────────────────────────────
from orbital_model import OrbitalSpigot
from sunlight_model import PhoenixSunlightModel
from ADCS import PhoenixADCS
from power_model import PhoenixPowerModel
from thermal_model import PhoenixThermalModel
from inter_communication_model import PhoenixCommsModel
from fault_injection_engine import PhoenixFaultEngine

# ── Mission / agent layer ────────────────────────────────────────────────────
from mission.workloads import default_workloads
from mission.mission_manager import MissionManager
from mission.logger import EventLogger
from mission.agent import AutonomousAgent
from ultralytics import YOLO
from PIL import Image
import io
import base64
from fastapi import UploadFile, File
import torch

# Load YOLOv8 model at startup
# Uses GPU/MPS if available, falls back to CPU
if torch.cuda.is_available():
    DEVICE = "cuda"
elif torch.backends.mps.is_available():
    DEVICE = "mps"
else:
    DEVICE = "cpu"

yolo_model = YOLO("yolov8n.pt")  # downloads automatically first run
yolo_model.to(DEVICE)

print(f"TSKY AI Engine loaded on: {DEVICE}")


# Registry of known relay satellites
RELAY_SATELLITES = {
    "SAT-ALPHA": {
        "name": "SAT-ALPHA",
        "type": "Wildfire Scout",
        "orbit_altitude_km": 380,
        "distance_km": 850,
        "status": "online"
    },
    "SAT-BETA": {
        "name": "SAT-BETA", 
        "type": "Flood Monitor",
        "orbit_altitude_km": 420,
        "distance_km": 1200,
        "status": "online"
    },
    "SAT-GAMMA": {
        "name": "SAT-GAMMA",
        "type": "Climate Observer", 
        "orbit_altitude_km": 410,
        "distance_km": 2100,
        "status": "online"
    },
    "SAT-DELTA": {
        "name": "SAT-DELTA",
        "type": "Disaster Response",
        "orbit_altitude_km": 395,
        "distance_km": 3400,
        "status": "online"
    }
}

# Track incoming transmissions
transmission_log = []


def check_satellite_link(satellite_id: str) -> dict:
    sat = RELAY_SATELLITES.get(satellite_id)
    if not sat:
        return {"success": False, "reason": "Unknown satellite"}
    
    distance_km = sat["distance_km"]
    
    # Use Person 1's inter_communication_model
    try:
        from inter_communication_model import PhoenixCommsModel
        link = PhoenixCommsModel()
        res = link.update_telemetry(
            satellite_distance_km=distance_km,
            antenna_alignment_pct=90.0,
            data_volume_gb=2.0,
            network_congestion_pct=10.0,
            mission_elapsed_days=0.0
        )
        quality = res["link_quality_pct"] / 100.0
        bandwidth_gbps = res["bandwidth_gbps"]
        latency_ms = res["latency_ms"]
    except Exception:
        # Fallback calculation if import fails
        max_range_km = 5000
        quality = max(0.0, 1.0 - (distance_km / max_range_km))
        bandwidth_gbps = quality * 40.0
        latency_ms = (distance_km / 300000.0) * 1000.0  # speed of light

    # Simulate packet loss
    import random
    packet_loss = max(0.0, (1.0 - quality) * 0.3)
    transmission_success = random.random() > packet_loss
    
    return {
        "success": transmission_success,
        "satellite_id": satellite_id,
        "distance_km": distance_km,
        "link_quality": round(quality, 3),
        "bandwidth_gbps": round(bandwidth_gbps, 2),
        "latency_ms": round(latency_ms, 2),
        "packet_loss_pct": round(packet_loss * 100, 1)
    }




# ============================================================================
# Simulation state
# ============================================================================

class SimulationState:
    """Thread-safe container for the live simulation."""

    def __init__(self):
        self.lock = threading.Lock()

        # Physics models
        self.orbit      = OrbitalSpigot(time_dilation_factor=600)
        self.sunlight   = PhoenixSunlightModel()
        self.adcs       = PhoenixADCS()
        self.power      = PhoenixPowerModel()
        self.thermal    = PhoenixThermalModel()
        self.comms      = PhoenixCommsModel()
        self.faults     = PhoenixFaultEngine()

        # Mission layer
        self.logger  = EventLogger()
        self.mm      = MissionManager(hooks=self._build_hooks())
        self.agent   = AutonomousAgent(self.mm, self.logger)

        # Scheduler — tracks workload status + distributes load
        self._workload_map: Dict[str, dict] = {
            w.name: {"priority": w.priority, "power": w.power_usage,
                     "heat": w.heat_generation, "status": w.status}
            for w in self.mm.workloads
        }
        self.healthy_gpus = 8

        # Time-keeping
        self.mission_time_seconds: float = 0.0
        self.time_dilation: int = 600          # sim-seconds per real-second
        self.sim_tick_seconds: float = 600.0   # physics step size
        self.running = True

        # Latest computed frames
        self.last_telemetry: Dict[str, Any] = {}
        self.last_satellite_state: Dict[str, Any] = _default_sat_state()
        self.critical_node_failure_active = False

    # ------------------------------------------------------------------
    # Hooks: keep physics models in sync when agent makes decisions
    # ------------------------------------------------------------------

    def _build_hooks(self):
        return {
            "pause_workload":   self._hook_pause_workload,
            "resume_workload":  self._hook_resume_workload,
            "enable_backup_gpu": self._hook_enable_backup_gpu,
            "reroute_power":    self._hook_reroute_power,
            "activate_cooling": self._hook_activate_cooling,
        }

    def _hook_pause_workload(self, workload_name: str):
        self.thermal.reduce_heat_load(workload_name)
        self.power.reduce_power_demand(workload_name)
        if workload_name in self._workload_map:
            self._workload_map[workload_name]["status"] = "paused"

    def _hook_resume_workload(self, workload_name: str):
        self.thermal.restore_heat_load(workload_name)
        self.power.restore_power_demand(workload_name)
        if workload_name in self._workload_map:
            self._workload_map[workload_name]["status"] = "active"

    def _hook_enable_backup_gpu(self, gpus_remaining: int):
        self.thermal.redistribute_load(gpus_remaining)
        self.healthy_gpus = gpus_remaining

    def _hook_reroute_power(self, solar_power: float):
        self.power.update_solar_input(solar_power)

    def _hook_activate_cooling(self):
        self.thermal.set_max_ammonia_flow()
        self.thermal.activate_emergency_cooling()
        self.thermal.activate_pcm()

    # ------------------------------------------------------------------
    # Workload scheduler
    # ------------------------------------------------------------------

    def _compute_scheduler(self) -> dict:
        gpu_load_kw  = 0.0
        comms_load   = 2.0
        data_vol_gb  = 10.0

        for w in self._workload_map.values():
            if w["status"] == "active":
                gpu_load_kw += w["power"]

        node_workloads = [0.0] * 20
        if self.healthy_gpus > 0:
            per_node = gpu_load_kw / self.healthy_gpus
            for i in range(min(self.healthy_gpus, 20)):
                node_workloads[i] = per_node

        return {
            "node_workloads_kw": node_workloads,
            "gpu_load_kw": gpu_load_kw,
            "comms_load_kw": comms_load,
            "data_volume_gb": data_vol_gb,
        }

    # ------------------------------------------------------------------
    # Core physics tick
    # ------------------------------------------------------------------

    def tick(self, sim_seconds: float = None) -> Dict[str, Any]:
        if sim_seconds is None:
            sim_seconds = self.sim_tick_seconds

        self.mission_time_seconds += sim_seconds
        mission_days = self.mission_time_seconds / 86400.0

        # 1. Orbit
        orbit = self.orbit.update()

        # 2. Sunlight
        sunlight = self.sunlight.update_telemetry(
            orbit["is_sunlit"], 100.0, sim_seconds
        )

        # 3. Scheduler
        sched = self._compute_scheduler()

        # 4. ADCS  (needs prior thermal estimates; we pass last-frame values safely)
        prev_thermal = self.last_telemetry.get("thermal", {})
        adcs = self.adcs.update_telemetry(
            is_sunlit=orbit["is_sunlit"],
            debris_warning=orbit.get("debris_warning", False),
            mission_elapsed_days=mission_days,
            battery_charge_pct=self.last_satellite_state.get("battery", 100),
            power_demand_kw=sched["gpu_load_kw"],
            solar_generation_kw=self.last_telemetry.get("power", {}).get("solar_generation_kw", 0),
            avg_cluster_temp_c=prev_thermal.get("avg_cluster_temp_c", 15),
            max_node_temp_c=prev_thermal.get("max_node_temp_c", 15),
            radiator_temp_c=prev_thermal.get("radiator_temp_c", 15),
            pcm_saturation_pct=prev_thermal.get("pcm_charge_pct", 0),
            sim_seconds=sim_seconds,
        )

        # 5. Power
        power = self.power.update_telemetry(
            is_sunlit=orbit["is_sunlit"],
            solar_efficiency_pct=adcs["solar_efficiency_pct"],
            gpu_load_kw=sched["gpu_load_kw"],
            comms_load_kw=sched["comms_load_kw"],
            mission_elapsed_days=mission_days,
            sim_seconds=sim_seconds,
        )

        # 6. Thermal
        thermal = self.thermal.update_telemetry(
            node_workloads_kw=sched["node_workloads_kw"],
            radiator_view_factor=adcs["radiator_view_factor"],
            mission_elapsed_days=mission_days,
            sim_seconds=sim_seconds,
        )

        # 7. Comms
        comms = self.comms.update_telemetry(
            satellite_distance_km=500,
            antenna_alignment_pct=adcs["antenna_alignment_pct"],
            data_volume_gb=sched["data_volume_gb"],
            network_congestion_pct=10,
            mission_elapsed_days=mission_days,
        )

        # 8. Fault engine decay
        self.faults.update(sim_seconds)

        # Build composite telemetry
        telemetry = {
            "timestamp":      datetime.now(timezone.utc).isoformat(),
            "mission_days":   round(mission_days, 4),
            "sim_elapsed_s":  round(self.mission_time_seconds, 1),
            "orbit":    orbit,
            "sunlight": sunlight,
            "adcs":     adcs,
            "power":    power,
            "thermal":  thermal,
            "comms":    comms,
            "scheduler": {
                "gpu_load_kw":   round(sched["gpu_load_kw"], 2),
                "comms_load_kw": round(sched["comms_load_kw"], 2),
                "data_volume_gb": sched["data_volume_gb"],
                "workloads": [
                    {"name": n, **v}
                    for n, v in self._workload_map.items()
                ],
            },
            "faults": [
                {"name": f.name, "subsystem": f.subsystem,
                 "severity": f.severity, "remaining_s": round(f.duration_seconds, 0)}
                for f in self.faults.active_faults
            ],
        }

        # Update flattened satellite state for the agent
        sat = self.last_satellite_state
        sat.update({
            "is_sunlit":      orbit["is_sunlit"],
            "latitude":       orbit["latitude"],
            "longitude":      orbit["longitude"],
            "altitude_km":    orbit["altitude_km"],
            "debris_warning": orbit.get("debris_warning", False),
            "temperature":    thermal["avg_cluster_temp_c"],
            "max_node_temp":  thermal["max_node_temp_c"],
            "node_temperatures": thermal["node_temperatures_c"],
            "pcm_saturation": thermal["pcm_charge_pct"],
            "battery":        power["battery_charge_pct"],
            "solar_power_kw": power["solar_generation_kw"],
            "solar_power":    round(min(100, (power["solar_generation_kw"] / 70) * 100), 1),
            "net_power_flow": power["net_power_kw"],
            "blackout":       power["alerts"].get("critical_power", False),
            "healthy_gpus":   self.healthy_gpus,
            "orbit":          orbit.get("orbit_type", "SSO"),
        })

        # Agent tick (monitoring + auto-recovery)
        try:
            self.agent.tick(sat)
        except Exception as e:
            self.logger.log(f"Agent tick error: {e}", "warning")

        self.last_telemetry = telemetry
        return telemetry

    # ------------------------------------------------------------------
    # Full status snapshot
    # ------------------------------------------------------------------

    def status_snapshot(self) -> dict:
        sat = self.last_satellite_state
        return {
            "satellite":   sat,
            "telemetry":   self.last_telemetry,
            "missions":    self.mm.get_status_dict(),
            "logs":        self.logger.get_recent(30),
            "health_score": _calculate_health(sat),
            "inference_engine": {
                "model": "YOLOv8n",
                "device": DEVICE,
                "ready": True
            },
            "constellation": {
                "relay_satellites": len(RELAY_SATELLITES),
                "recent_transmissions": len(transmission_log),
                "last_transmission": transmission_log[-1] if transmission_log else None
            },
            "physics_sync": {
                "solar_array_health_pct":  self.power.solar_array_health_pct,
                "battery_a_health_pct":    self.power.battery_a.health_pct,
                "battery_b_health_pct":    self.power.battery_b.health_pct,
                "loop_a_health_pct":       self.thermal.loop_a.health_pct,
                "loop_b_health_pct":       self.thermal.loop_b.health_pct,
                "battery_a_charge_j":      self.power.battery_a.charge_j,
                "battery_b_charge_j":      self.power.battery_b.charge_j,
                "active_faults": [
                    {"name": f.name, "subsystem": f.subsystem,
                     "severity": f.severity, "duration": f.duration_seconds}
                    for f in self.faults.active_faults
                ],
            },
        }

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def reset(self):
        with self.lock:
            self.healthy_gpus = 8
            self.mission_time_seconds = 0.0
            self.critical_node_failure_active = False
            self.last_satellite_state = _default_sat_state()
            self.last_telemetry = {}

            # Reset physics
            self.thermal.node_temps_c = [15.0] * self.thermal.NUM_NODES
            self.thermal.loop_a.health_pct = 100.0
            self.thermal.loop_b.health_pct = 100.0
            self.thermal.loop_a.nominal_flow_kg_s = 0.45
            self.thermal.loop_b.nominal_flow_kg_s = 0.45
            self.thermal.pcm_energy_j = 0.0
            self.thermal.emergency_shutdown = False

            total_j = self.power.TOTAL_BATTERY_KWH * 1000 * 3600
            self.power.solar_array_health_pct = 100.0
            self.power.battery_a.health_pct = 100.0
            self.power.battery_b.health_pct = 100.0
            self.power.battery_a.charge_j = total_j / 2
            self.power.battery_b.charge_j = total_j / 2
            self.power.supercap_charge_j = self.power.SUPERCAP_MAX_J
            self.power.safe_mode = False
            self.power.emergency_shutdown = False

            self.faults.active_faults = []
            self.logger.events.clear()

            # Reset workloads
            for w in self.mm.workloads:
                w.status = "active"
            for name, v in self._workload_map.items():
                v["status"] = "active"
            if hasattr(self.mm.engine, "cooldowns"):
                self.mm.engine.cooldowns.clear()


# ============================================================================
# Helpers
# ============================================================================

def _default_sat_state() -> dict:
    return {
        "temperature": 15.0, "max_node_temp": 15.0, "battery": 100.0,
        "solar_power": 100.0, "solar_power_kw": 70.0, "healthy_gpus": 8,
        "orbit": "SSO", "is_sunlit": True, "blackout": False,
        "debris_warning": False, "net_power_flow": 0.0, "pcm_saturation": 0.0,
        "latitude": 0.0, "longitude": 0.0, "altitude_km": 550.0,
        "node_temperatures": [],
    }


def _calculate_health(sat: dict) -> int:
    gpus    = sat.get("healthy_gpus", 8)
    battery = sat.get("battery", 100.0)
    temp    = sat.get("temperature", 15.0)
    score   = ((gpus / 8) * 60
               + (min(battery, 100.0) / 100.0) * 30
               + (max(0.0, 85.0 - temp) / 85.0) * 10)
    return int(max(0, min(100, score)))


# ============================================================================
# Background simulation loop
# ============================================================================

sim = SimulationState()


def _simulation_loop():
    """Runs forever in a daemon thread — one tick per real second."""
    while sim.running:
        try:
            with sim.lock:
                sim.tick()
        except Exception as e:
            print(f"[SIM ERROR] {e}")
        time.sleep(1)


# ============================================================================
# FastAPI app
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    thread = threading.Thread(target=_simulation_loop, daemon=True)
    thread.start()
    yield
    sim.running = False


app = FastAPI(
    title="FarAway — Tsukuyomi-1 Mission Control API",
    description="Unified backend for the orbital GPU datacenter simulation.",
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Root ────────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return FileResponse("frontend/dist/index.html")


# ── SSE telemetry stream ─────────────────────────────────────────────────────

@app.get("/telemetry/stream")
async def telemetry_stream():
    """
    Server-Sent Events stream.
    Frontend connects once; receives a JSON frame every ~1 s.
    Usage:  const es = new EventSource('/telemetry/stream');
            es.onmessage = e => console.log(JSON.parse(e.data));
    """
    async def event_generator():
        while True:
            with sim.lock:
                frame = sim.last_telemetry
            if frame:
                yield f"data: {json.dumps(frame)}\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Snapshot ─────────────────────────────────────────────────────────────────

@app.get("/telemetry/snapshot")
async def telemetry_snapshot():
    """Return the latest full telemetry frame (JSON, no streaming)."""
    with sim.lock:
        return sim.last_telemetry or {"error": "no data yet"}


# ── Status ───────────────────────────────────────────────────────────────────

@app.get("/status")
async def get_status():
    with sim.lock:
        return sim.status_snapshot()


# ── Health ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    sat = sim.last_satellite_state
    return {
        "status": "online",
        "health_score": _calculate_health(sat),
        "healthy_gpus": sat.get("healthy_gpus", 8),
        "battery_pct":  sat.get("battery", 100),
        "temperature_c": sat.get("temperature", 15),
        "is_sunlit":    sat.get("is_sunlit", True),
    }


# ── Manual tick ──────────────────────────────────────────────────────────────

@app.post("/sim/tick")
async def manual_tick(body: dict = {}):
    """Advance the simulation by `seconds` (default: current tick size)."""
    seconds = float(body.get("seconds", sim.sim_tick_seconds))
    with sim.lock:
        frame = sim.tick(seconds)
    return frame


@app.post("/sim/speed")
async def set_speed(body: dict):
    """
    Change time-dilation factor.
    factor=600  → 1 real-second = 10 sim-minutes  (default)
    factor=60   → 1 real-second = 1 sim-minute
    factor=3600 → 1 real-second = 1 sim-hour
    """
    factor = int(body.get("factor", 600))
    sim.time_dilation = factor
    sim.sim_tick_seconds = float(factor)
    sim.orbit.time_dilation = factor
    return {"time_dilation": factor}


# ── External state push (legacy compat) ──────────────────────────────────────

@app.post("/state")
async def receive_state(data: dict):
    """
    Legacy endpoint: accepts orbit / power / thermal telemetry from an
    external process and merges it into the satellite state.
    """
    with sim.lock:
        sat = sim.last_satellite_state

        if "is_sunlit" in data:
            sat["is_sunlit"]      = data.get("is_sunlit", sat.get("is_sunlit", True))
            sat["latitude"]       = data.get("latitude", sat.get("latitude", 0.0))
            sat["longitude"]      = data.get("longitude", sat.get("longitude", 0.0))
            sat["altitude_km"]    = data.get("altitude_km", sat.get("altitude_km", 550.0))
            sat["debris_warning"] = data.get("hazard_debris_warning",
                                             data.get("debris_warning", False))

        if "battery_charge_pct" in data or "solar_generation_kw" in data:
            sat["battery"]       = data.get("battery_charge_pct", sat.get("battery", 100.0))
            sat["solar_power_kw"] = data.get("solar_generation_kw", sat.get("solar_power_kw", 0.0))
            sat["net_power_flow"] = data.get("net_power_kw", sat.get("net_power_flow", 0.0))
            sat["blackout"]      = data.get("alerts", {}).get("critical_power", False)

        if "avg_cluster_temp_c" in data:
            sat["temperature"]       = data.get("avg_cluster_temp_c", sat.get("temperature", 15.0))
            sat["max_node_temp"]     = data.get("max_node_temp_c", sat.get("max_node_temp", 15.0))
            sat["node_temperatures"] = data.get("node_temperatures_c", [])
            sat["pcm_saturation"]    = data.get("pcm_charge_pct", sat.get("pcm_saturation", 0.0))

            mission_status = data.get("mission_status")
            if mission_status == "CRITICAL_NODE_FAILURE" and not sim.critical_node_failure_active:
                sat["healthy_gpus"] = max(0, sat.get("healthy_gpus", 8) - 2)
                sim.critical_node_failure_active = True
            elif mission_status and mission_status != "CRITICAL_NODE_FAILURE":
                sim.critical_node_failure_active = False

        sim.agent.tick(sat)
    return {"ok": True}


# ── Fault injection ───────────────────────────────────────────────────────────

@app.post("/inject/{failure_type}")
async def inject_failure(failure_type: str):
    """
    Inject a named failure scenario.
    Supported: gpu_failure | debris_strike | solar_damage | battery_drain
    """
    with sim.lock:
        sat = sim.last_satellite_state
        actions, patches = sim.mm.inject_failure(failure_type, sat)
        sat.update(patches)

        # Apply damage directly to physics models
        try:
            if failure_type == "gpu_failure":
                sim.thermal.node_temps_c[0] = 85.0
                sim.faults.inject_fault("GPU_Fail", "THERMAL", "MAJOR", 3600)
                sim.healthy_gpus = max(0, sim.healthy_gpus - 1)

            elif failure_type == "debris_strike":
                sim.thermal.loop_a.health_pct = max(0.0, sim.thermal.loop_a.health_pct - 30.0)
                sim.power.solar_array_health_pct = max(0.0, sim.power.solar_array_health_pct - 15.0)
                sim.faults.inject_fault("Debris_Strike", "HULL", "CRITICAL", 7200)
                sim.healthy_gpus = max(0, sim.healthy_gpus - 3)

            elif failure_type == "solar_damage":
                sim.power.solar_array_health_pct = max(0.0, sim.power.solar_array_health_pct - 25.0)
                sim.faults.inject_fault("Solar_Damage", "POWER", "MAJOR", 7200)

            elif failure_type == "battery_drain":
                sim.power.battery_a.health_pct = max(0.0, sim.power.battery_a.health_pct - 30.0)
                sim.power.battery_b.health_pct = max(0.0, sim.power.battery_b.health_pct - 30.0)
                sim.power.battery_a.charge_j  *= 0.7
                sim.power.battery_b.charge_j  *= 0.7
                sim.faults.inject_fault("Battery_Drain", "POWER", "MAJOR", 3600)

        except Exception as e:
            sim.logger.log(f"Fault injection side-effect error: {e}", "warning")

        sim.logger.log_recovery_sequence(failure_type, actions)

        return {
            "injected": failure_type,
            "actions": actions,
            "satellite": sat,
            "missions": sim.mm.get_status_dict(),
            "active_faults": [
                {"name": f.name, "subsystem": f.subsystem, "severity": f.severity}
                for f in sim.faults.active_faults
            ],
        }


# ── Workload control ──────────────────────────────────────────────────────────

@app.post("/workload/{name}/pause")
async def pause_workload(name: str):
    with sim.lock:
        matches = [w for w in sim.mm.workloads if w.name.lower() == name.lower()]
        if not matches:
            return {"error": f"Workload '{name}' not found"}
        w = matches[0]
        if w.status == "paused":
            return {"status": "already_paused", "name": w.name}
        w.status = "paused"
        sim._hook_pause_workload(w.name)
        sim.logger.log(f"Manually paused workload: {w.name}", "info")
        return {"status": "paused", "name": w.name}


@app.post("/workload/{name}/resume")
async def resume_workload(name: str):
    with sim.lock:
        matches = [w for w in sim.mm.workloads if w.name.lower() == name.lower()]
        if not matches:
            return {"error": f"Workload '{name}' not found"}
        w = matches[0]
        if w.status == "active":
            return {"status": "already_active", "name": w.name}
        w.status = "active"
        if hasattr(sim.mm.engine, "cooldowns") and w.name in sim.mm.engine.cooldowns:
            sim.mm.engine.cooldowns[w.name] = 0
        sim._hook_resume_workload(w.name)
        sim.logger.log(f"Manually resumed workload: {w.name}", "info")
        return {"status": "active", "name": w.name}


@app.get("/workloads")
async def list_workloads():
    with sim.lock:
        return {"workloads": sim.mm.get_status_dict()}


# ── AI agent question ─────────────────────────────────────────────────────────

@app.post("/ask")
async def ask_agent(body: dict):
    """Ask the autonomous agent to explain the current state."""
    question = body.get("question", "What is the current system status?")
    with sim.lock:
        sat = sim.last_satellite_state.copy()
    answer = sim.agent.explain(question, sat)
    return {"question": question, "answer": answer}



# ── YOLOv8 Deep Learning Inference Endpoints ─────────────────────────────────

@app.post("/analyze-image")
async def analyze_image(file: UploadFile = File(...)):
    try:
        # Read uploaded image
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")
        
        # Run YOLOv8 inference
        results = yolo_model(image, device=DEVICE, conf=0.25)
        result = results[0]
        
        # Extract detections
        detections = []
        for box in result.boxes:
            detections.append({
                "class": result.names[int(box.cls[0])],
                "confidence": round(float(box.conf[0]), 3),
                "bbox": [
                    round(float(box.xyxy[0][0])),
                    round(float(box.xyxy[0][1])),
                    round(float(box.xyxy[0][2])),
                    round(float(box.xyxy[0][3]))
                ]
            })
        
        # Generate annotated image with bounding boxes
        annotated = result.plot()  # returns numpy array with boxes drawn
        annotated_pil = Image.fromarray(annotated)
        buffer = io.BytesIO()
        annotated_pil.save(buffer, format="JPEG", quality=85)
        annotated_b64 = base64.b64encode(buffer.getvalue()).decode()
        
        # Log this as an active workload in PHOENIX
        sim.logger.log(
            f"GPU inference complete — {len(detections)} objects detected "
            f"on {DEVICE.upper()}",
            "info"
        )
        
        # Simulate GPU heat from inference
        with sim.lock:
            satellite_state = sim.last_satellite_state
            current_temp = satellite_state.get("temperature", 40)
            satellite_state["temperature"] = min(current_temp + 2.5, 120.0)
        
        return {
            "success": True,
            "device": DEVICE,
            "model": "YOLOv8n",
            "detections": detections,
            "detection_count": len(detections),
            "annotated_image_b64": annotated_b64,
            "workload": "Wildfire Detection"
        }
    
    except Exception as e:
        sim.logger.log(f"Inference failed: {str(e)}", "critical")
        return {
            "success": False,
            "error": str(e),
            "detections": []
        }


@app.post("/analyze-satellite")
async def analyze_satellite_image(
    file: UploadFile = File(...),
    mission: str = "Wildfire Detection"
):
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")
        
        # Check if mission is active before running inference
        with sim.lock:
            mission_status = sim.mm.get_status_dict()
        mission_active = any(
            m["name"].lower() == mission.lower() and m["status"] == "active" 
            for m in mission_status
        )
        
        if not mission_active:
            return {
                "success": False,
                "error": f"Mission '{mission}' is currently paused. "
                         f"System resources insufficient.",
                "detections": [],
                "mission_status": "PAUSED"
            }
        
        # Run inference
        results = yolo_model(image, device=DEVICE, conf=0.25)
        result = results[0]
        
        detections = []
        for box in result.boxes:
            detections.append({
                "class": result.names[int(box.cls[0])],
                "confidence": round(float(box.conf[0]), 3),
                "bbox": [
                    round(float(box.xyxy[0][0])),
                    round(float(box.xyxy[0][1])),
                    round(float(box.xyxy[0][2])),
                    round(float(box.xyxy[0][3]))
                ]
            })
        
        annotated = result.plot()
        annotated_pil = Image.fromarray(annotated)
        buffer = io.BytesIO()
        annotated_pil.save(buffer, format="JPEG", quality=85)
        annotated_b64 = base64.b64encode(buffer.getvalue()).decode()
        
        sim.logger.log(
            f"[{mission}] Satellite image analyzed — "
            f"{len(detections)} objects detected on {DEVICE.upper()}",
            "info"
        )
        
        # Simulate GPU heat from inference
        with sim.lock:
            satellite_state = sim.last_satellite_state
            current_temp = satellite_state.get("temperature", 40)
            satellite_state["temperature"] = min(current_temp + 2.5, 120.0)
            
            healthy_gpus = satellite_state.get("healthy_gpus", 8)
            system_health = _calculate_health(satellite_state)
        
        return {
            "success": True,
            "mission": mission,
            "mission_status": "ACTIVE",
            "device": DEVICE,
            "model": "YOLOv8n",
            "detections": detections,
            "detection_count": len(detections),
            "annotated_image_b64": annotated_b64,
            "healthy_gpus": healthy_gpus,
            "system_health": system_health
        }
    
    except Exception as e:
        sim.logger.log(f"Satellite inference failed: {str(e)}", "critical")
        return {
            "success": False,
            "error": str(e),
            "detections": []
        }



# ── Inter-Satellite Image Relay Endpoints ────────────────────────────────────

@app.post("/satellite/transmit/{satellite_id}")
async def receive_from_satellite(
    satellite_id: str,
    file: UploadFile = File(...)
):
    sat = RELAY_SATELLITES.get(satellite_id)
    if not sat:
        return {
            "success": False,
            "error": f"Satellite {satellite_id} not in registry"
        }
    
    # Check link quality using inter_communication_model
    link = check_satellite_link(satellite_id)
    
    sim.logger.log(
        f"[COMMS] {satellite_id} ({sat['type']}) initiating transmission — "
        f"distance: {sat['distance_km']}km, "
        f"link quality: {link['link_quality']*100:.0f}%, "
        f"latency: {link['latency_ms']:.0f}ms",
        "info"
    )
    
    # Check if healthy_gpus drops below 4
    with sim.lock:
        satellite_state = sim.last_satellite_state
        healthy_gpus = satellite_state.get("healthy_gpus", 8)
    
    if healthy_gpus < 4:
        sim.logger.log(
            f"[COMMS] Rejected transmission from {satellite_id} — "
            f"insufficient GPU resources ({healthy_gpus}/8)",
            "warning"
        )
        return {
            "success": False,
            "satellite_id": satellite_id,
            "error": "Tsukuyomi-1 GPU resources critically low. "
                     "Transmission rejected to preserve priority missions.",
            "healthy_gpus": healthy_gpus,
            "retry_when": "GPU count recovers above 4"
        }
    
    # Simulate transmission delay based on real latency
    import asyncio
    await asyncio.sleep(min(link["latency_ms"] / 1000.0, 2.0))
    
    # Check if transmission succeeded (packet loss simulation)
    if not link["success"]:
        sim.logger.log(
            f"[COMMS] Transmission from {satellite_id} FAILED — "
            f"packet loss {link['packet_loss_pct']}%",
            "warning"
        )
        return {
            "success": False,
            "satellite_id": satellite_id,
            "error": "Transmission failed due to packet loss",
            "link": link,
            "retry_recommended": True
        }
    
    sim.logger.log(
        f"[COMMS] Image received from {satellite_id} — "
        f"running GPU inference",
        "info"
    )
    
    # Run inference on received image
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")
        
        results = yolo_model(image, device=DEVICE, conf=0.25)
        result = results[0]
        
        detections = []
        for box in result.boxes:
            detections.append({
                "class": result.names[int(box.cls[0])],
                "confidence": round(float(box.conf[0]), 3),
                "bbox": [
                    round(float(box.xyxy[0][0])),
                    round(float(box.xyxy[0][1])),
                    round(float(box.xyxy[0][2])),
                    round(float(box.xyxy[0][3]))
                ]
            })
        
        annotated = result.plot()
        annotated_pil = Image.fromarray(annotated)
        buffer = io.BytesIO()
        annotated_pil.save(buffer, format="JPEG", quality=85)
        annotated_b64 = base64.b64encode(buffer.getvalue()).decode()
        
        # Spike temperature from GPU load
        with sim.lock:
            satellite_state = sim.last_satellite_state
            current_temp = satellite_state.get("temperature", 40)
            satellite_state["temperature"] = min(current_temp + 2.5, 120.0)
            
            # Log transmission record
            global transmission_log
            record = {
                "satellite_id": satellite_id,
                "satellite_type": sat["type"],
                "distance_km": sat["distance_km"],
                "link_quality": link["link_quality"],
                "latency_ms": link["latency_ms"],
                "detections_count": len(detections),
                "timestamp": __import__("datetime").datetime.utcnow().isoformat()
            }
            transmission_log.append(record)
            if len(transmission_log) > 100:
                transmission_log = transmission_log[-100:]
                
            healthy_gpus = satellite_state.get("healthy_gpus", 8)
            system_health = _calculate_health(satellite_state)
        
        sim.logger.log(
            f"[COMMS] Inference complete for {satellite_id} — "
            f"{len(detections)} objects detected. "
            f"Result transmitted back.",
            "recovery"
        )
        
        return {
            "success": True,
            "source_satellite": satellite_id,
            "satellite_type": sat["type"],
            "link": link,
            "inference": {
                "device": DEVICE,
                "model": "YOLOv8n",
                "detections": detections,
                "detection_count": len(detections),
                "annotated_image_b64": annotated_b64
            },
            "system_health": system_health,
            "healthy_gpus": healthy_gpus
        }
    
    except Exception as e:
        sim.logger.log(
            f"[COMMS] Inference failed for {satellite_id}: {str(e)}",
            "critical"
        )
        return {
            "success": False,
            "satellite_id": satellite_id,
            "error": str(e)
        }


@app.get("/satellites")
async def get_satellites():
    satellite_list = []
    for sat_id, sat in RELAY_SATELLITES.items():
        link = check_satellite_link(sat_id)
        satellite_list.append({
            "id": sat_id,
            "name": sat["name"],
            "type": sat["type"],
            "distance_km": sat["distance_km"],
            "link_quality_pct": round(link["link_quality"] * 100, 1),
            "bandwidth_gbps": link["bandwidth_gbps"],
            "latency_ms": link["latency_ms"],
            "status": sat["status"]
        })
    return {
        "constellation_size": len(RELAY_SATELLITES),
        "satellites": satellite_list,
        "transmission_log": transmission_log[-10:]
    }


@app.get("/satellites/{satellite_id}/link")
async def check_link(satellite_id: str):
    link = check_satellite_link(satellite_id)
    sat = RELAY_SATELLITES.get(satellite_id, {})
    return {
        "satellite_id": satellite_id,
        "satellite_type": sat.get("type", "unknown"),
        "link": link
    }


# ── Reset ─────────────────────────────────────────────────────────────────────


@app.post("/reset")
async def reset():
    sim.reset()
    return {"ok": True, "message": "Tsukuyomi-1 reset to nominal state."}


# ── Static Files ──────────────────────────────────────────────────────────────
app.mount("/", StaticFiles(directory="frontend/dist"), name="static")
