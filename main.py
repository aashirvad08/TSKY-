from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv

from mission.mission_manager import MissionManager
from mission.logger import EventLogger
from mission.agent import AutonomousAgent

load_dotenv()
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

SOLAR_NOMINAL_KW = 3.15

# --- Person 1's hooks (they will fill these in, you define the interface) ---
# These get replaced by real functions once Person 1 wires them up
def pause_workload(workload_name: str): pass
def resume_workload(workload_name: str): pass
def enable_backup_gpu(gpus_remaining: int): pass
def reroute_power(solar_power: float): pass
def activate_cooling(): pass

hooks = {
    "pause_workload": pause_workload,
    "resume_workload": resume_workload,
    "enable_backup_gpu": enable_backup_gpu,
    "reroute_power": reroute_power,
    "activate_cooling": activate_cooling,
}

mm = MissionManager(hooks=hooks)
logger = EventLogger()
agent = AutonomousAgent(mm, logger)

satellite_state = {
    "temperature": 40.0,
    "battery": 100.0,
    "solar_power": 100.0,
    "healthy_gpus": 8,
    "orbit": 0,
    "is_sunlit": True,
    "blackout": False,
    "debris_warning": False,
    "net_power_flow": 0.0,
    "max_node_temp": 40.0,
    "node_temperatures": [],
    "pcm_saturation": 0.0,
    "latitude": 0.0,
    "longitude": 0.0,
    "altitude_km": 400.0,
    "solar_power_kw": 0.0,
}
critical_node_failure_active = False

@app.post("/state")
async def receive_state(data: dict):
    """Accepts Person 1's full telemetry and maps it to our state."""
    global critical_node_failure_active

    # --- Orbit data ---
    if "is_sunlit" in data:
        satellite_state["is_sunlit"] = data["is_sunlit"]
        satellite_state["latitude"] = data.get("latitude", satellite_state["latitude"])
        satellite_state["longitude"] = data.get("longitude", satellite_state["longitude"])
        satellite_state["altitude_km"] = data.get("altitude_km", satellite_state["altitude_km"])
        satellite_state["debris_warning"] = data.get("hazard_debris_warning", False)

    # --- Power data ---
    if "flywheel_charge_pct" in data:
        satellite_state["battery"] = data["flywheel_charge_pct"]        # their battery = flywheel
        solar_average_kw = (
            data.get("solar_port_wing_kw", 0) + data.get("solar_starboard_wing_kw", 0)
        ) / 2
        satellite_state["solar_power_kw"] = round(solar_average_kw, 2)
        satellite_state["solar_power"] = round(
            max(0, min(100, (solar_average_kw / SOLAR_NOMINAL_KW) * 100)),
            1,
        )
        satellite_state["net_power_flow"] = data.get("net_power_flow_kw", 0)
        satellite_state["blackout"] = data.get("alerts", {}).get("blackout_critical", False)

    # --- Thermal data ---
    if "avg_cluster_temp_c" in data:
        satellite_state["temperature"] = data["avg_cluster_temp_c"]     # main temp we use
        satellite_state["max_node_temp"] = data.get("max_node_temp_c", satellite_state["max_node_temp"])
        satellite_state["node_temperatures"] = data.get("node_temperatures_c", [])
        satellite_state["pcm_saturation"] = data.get("pcm_saturation_pct", 0)

        # If Person 1 reports hardware damage, reduce our GPU count
        mission_status = data.get("mission_status")
        if mission_status == "CRITICAL_NODE_FAILURE" and not critical_node_failure_active:
            satellite_state["healthy_gpus"] = max(0, satellite_state.get("healthy_gpus", 8) - 2)
            critical_node_failure_active = True
        elif mission_status and mission_status != "CRITICAL_NODE_FAILURE":
            critical_node_failure_active = False

    # Run agent tick with updated state
    agent.tick(satellite_state)
    return {"ok": True}

@app.post("/inject/{failure_type}")
async def inject_failure(failure_type: str):
    actions, patches = mm.inject_failure(failure_type, satellite_state)
    satellite_state.update(patches)
    if failure_type not in {"gpu_failure", "debris_strike", "solar_damage", "battery_drain"}:
        logger.log(actions[0], "warning")
    else:
        logger.log_recovery_sequence(failure_type, actions)
    return {
        "actions": actions,
        "state": satellite_state,
        "missions": mm.get_status_dict()
    }

@app.get("/status")
async def get_status():
    return {
        "satellite": satellite_state,
        "missions": mm.get_status_dict(),
        "logs": logger.get_recent(20),
        "health_score": calculate_health(),
    }

@app.post("/ask")
async def ask_agent(body: dict):
    question = body.get("question", "")
    answer = agent.explain(question, satellite_state)
    return {"answer": answer}

def calculate_health() -> int:
    gpus = satellite_state.get("healthy_gpus", 8)
    battery = satellite_state.get("battery", 100)
    temp = satellite_state.get("temperature", 40)
    score = (gpus / 8) * 60 + (min(battery, 100) / 100) * 30 + (max(0, 85 - temp) / 85) * 10
    return int(max(0, min(100, score)))
