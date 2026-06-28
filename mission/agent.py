import os
from dotenv import load_dotenv
from .mission_manager import MissionManager
from .logger import EventLogger

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

load_dotenv()


class AutonomousAgent:
    def __init__(self, mission_manager: MissionManager, logger: EventLogger):
        self.mm = mission_manager
        self.logger = logger
        self.last_battery = 100
        self.last_temp = 40
        self.last_gpus = 8
        self.client = None

    def tick(self, satellite_state: dict):
        battery = satellite_state.get("battery", 100)
        temp = satellite_state.get("temperature", 40)
        healthy_gpus = satellite_state.get("healthy_gpus", 8)

        # --- Cascading effect detection ---

        # Battery dropping — warn before it hits critical
        if battery < 30 and self.last_battery >= 30:
            self.logger.log(
                "Battery below 30% — monitoring closely", "warning")
        if battery < 20 and self.last_battery >= 20:
            self.logger.log(
                "CRITICAL: Battery below 20% — power conservation mode", "critical")

        # Temperature rising
        if temp > 75 and self.last_temp <= 75:
            self.logger.log(
                "Temperature elevated above 75°C — watching thermal load", "warning")
        if temp > 85 and self.last_temp <= 85:
            self.logger.log(
                "CRITICAL: Temperature exceeded 85°C — reducing compute", "critical")

        # GPU count dropped (outside of direct failure injection)
        if healthy_gpus < self.last_gpus:
            self.logger.log(
                f"GPU count dropped {self.last_gpus} → {healthy_gpus} — triggering workload migration",
                "failure"
            )

        # Run priority scheduler every tick
        actions = self.mm.apply_recovery(satellite_state)
        for action in actions:
            self.logger.log(action, "recovery")

        self.last_battery = battery
        self.last_temp = temp
        self.last_gpus = healthy_gpus

    def explain(self, question: str, satellite_state: dict) -> str:
        battery = satellite_state.get("battery", 100)
        temp = satellite_state.get("temperature", 15.0)
        healthy_gpus = satellite_state.get("healthy_gpus", 8)
        
        # Get missions status
        missions = self.mm.get_status_dict()
        paused = [m["name"] for m in missions if m["status"] == "paused"]
        active = [m["name"] for m in missions if m["status"] == "active"]
        
        recent_events = [e['message'] for e in self.logger.get_recent(5)]

        client_type = None
        client = None
        
        # Check for OpenAI key first, then GITHUB_TOKEN
        openai_key = os.getenv("OPENAI_API_KEY")
        github_token = os.getenv("GITHUB_TOKEN")
        
        system_prompt = """You are TSKY, the autonomous AI managing Tsukuyomi-1, an orbital GPU datacenter.
You speak in short, confident, technical sentences. No fluff.
When asked why something happened, explain using the actual numbers provided.
Never say you don't know — always give a direct answer based on the telemetry."""

        context = f"""Current satellite state:
- Temperature: {temp:.1f}°C  (critical threshold: 85°C)
- Battery: {battery:.1f}%  (critical threshold: 20%)
- Healthy GPUs: {healthy_gpus}/8
- Active missions: {', '.join(active) if active else 'none'}
- Paused missions: {', '.join(paused) if paused else 'none'}
- Recent events: {'; '.join(recent_events) if recent_events else 'none'}
"""

        try:
            if openai_key and OpenAI:
                client = OpenAI(api_key=openai_key)
                client_type = "openai"
            elif github_token and OpenAI:
                client = OpenAI(
                    base_url="https://models.inference.ai.azure.com",
                    api_key=github_token,
                    timeout=5.0,
                )
                client_type = "github"
                
            if client:
                model_name = "gpt-4o-mini" if client_type == "openai" else "gpt-4o"
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": context + "\n\nQuestion: " + question},
                    ],
                    max_tokens=150,
                    temperature=0.4,
                )
                return response.choices[0].message.content
        except Exception as e:
            print(f"LLM API Error: {e}")
            
        # If no LLM API keys are provided or the API call failed, run our smart expert system
        return self._expert_system_explanation(question, satellite_state, battery, temp, healthy_gpus, active, paused, recent_events)

    def _expert_system_explanation(
        self,
        question: str,
        state: dict,
        battery: float,
        temp: float,
        healthy_gpus: int,
        active: list,
        paused: list,
        recent_events: list
    ) -> str:
        q = question.lower()
        
        max_temp = state.get("max_node_temp", temp)
        solar_kw = state.get("solar_power_kw", 0.0)
        net_power = state.get("net_power_flow", 0.0)
        is_sunlit = state.get("is_sunlit", True)
        pcm = state.get("pcm_saturation", 0.0)
        lat = state.get("latitude", 0.0)
        lon = state.get("longitude", 0.0)
        alt = state.get("altitude_km", 390.0)
        blackout = state.get("blackout", False)
        
        # Calculate health score dynamically
        score = int(((healthy_gpus / 8) * 60 + (min(battery, 100.0) / 100.0) * 30 + (max(0.0, 85.0 - temp) / 85.0) * 10))
        health_score = max(0, min(100, score))

        if any(w in q for w in ["temp", "heat", "hot", "cool", "thermal", "radiator", "ammonia", "pcm"]):
            resp = f"TSKY THERMAL REPORT: Average cluster temperature is {temp:.1f}°C, with max node at {max_temp:.1f}°C. "
            if pcm > 0:
                resp += f"Liquid ammonia loops degraded or saturated. Passive PCM wax cooling active at {pcm:.1f}% capacity. "
            else:
                resp += "Active liquid ammonia cooling loops operating within normal parameters. "
            
            if temp > 75:
                resp += "Elevated thermal load detected. Emergency shutdown threshold is 85°C. Cooling manifolds set to maximum flow."
            else:
                resp += "Thermal dissipation is nominal. Node heat is fully under control."
            return resp

        elif any(w in q for w in ["battery", "power", "solar", "blackout", "charge", "energy", "sun", "sunlit", "eclipse"]):
            sun_status = "Sunlit (SSO Dawn-Dusk)" if is_sunlit else "Eclipse (Earth shadow)"
            resp = f"TSKY POWER REPORT: Battery level is {battery:.1f}%. Solar array generation is {solar_kw:.1f} kW. Net power flow: {net_power:+.2f} kW. "
            resp += f"Current orbital illumination: {sun_status}. "
            
            if battery < 20 or blackout:
                resp += "WARNING: Critical power deficit. Load-shedding protocol active to protect core subsystems."
            elif battery < 35:
                resp += "Battery reserves low. Non-essential processes are being monitored for potential shedding."
            else:
                resp += "Power reserves nominal. Energy balance is stable."
            return resp

        elif any(w in q for w in ["workload", "mission", "pause", "resume", "scheduler", "running", "active"]):
            resp = f"TSKY SCHEDULER: Currently running {len(active)} active workloads and {len(paused)} paused workloads. "
            if active:
                resp += f"Active missions: {', '.join(active)}. "
            if paused:
                resp += f"Paused missions: {', '.join(paused)}. "
                
            if paused:
                resp += "Lower-priority workloads were paused by the Autonomous Recovery Engine to conserve power/thermal margins."
            else:
                resp += "All workloads running at nominal capacity. GPU scheduler operating at peak efficiency."
            return resp

        elif any(w in q for w in ["gpu", "node", "rack", "healthy", "capacity"]):
            resp = f"TSKY COMPUTE REPORT: Cluster capacity is {healthy_gpus}/8 healthy GPU nodes. "
            if healthy_gpus < 8:
                lost = 8 - healthy_gpus
                resp += f"An anomaly resulted in the loss of {lost} GPU node(s). Workloads have been dynamically migrated to the remaining {healthy_gpus} online nodes."
            else:
                resp += "All 8 onboard GPU nodes are online and processing workloads."
            return resp

        elif any(w in q for w in ["fault", "fail", "anomaly", "strike", "debris", "damage", "incident", "accident"]):
            if recent_events:
                events_str = " -> ".join(recent_events[:3])
                resp = f"TSKY LOGS: Recent events include: '{events_str}'. "
            else:
                resp = "TSKY LOGS: No anomalous events recorded recently. "
                
            if healthy_gpus < 8 or battery < 30 or temp > 75:
                resp += "Current anomalous state has triggered autonomous mitigation workflows. Hardware status is being updated."
            else:
                resp += "Systems are reporting nominal status. Zero active hardware failures."
            return resp

        elif any(w in q for w in ["orbit", "altitude", "coordinate", "lat", "lon", "location", "position", "where"]):
            sun_status = "Direct Sunlight" if is_sunlit else "Eclipse"
            resp = f"TSKY NAVIGATION: Orbit type: SSO (Sun-Synchronous). Altitude: {alt:.1f} km. "
            resp += f"Current position: {abs(lat):.2f}°{'N' if lat>=0 else 'S'}, {abs(lon):.2f}°{'E' if lon>=0 else 'W'}. "
            resp += f"Orbital phase is in {sun_status}."
            return resp

        elif any(w in q for w in ["who", "what are you", "tsky", "copilot", "agent", "ai"]):
            return "I am TSKY, the autonomous AI copilot managing Tsukuyomi-1. My primary directive is to maintain the health and safety of the 20-node orbital GPU datacenter. I monitor telemetry, run failure mitigation loops, and assist operators with real-time status explanations."

        # Default general response
        resp = f"TSKY status report: Health score at {health_score}%. Cluster operating at {healthy_gpus}/8 healthy GPUs. "
        resp += f"Average temp is {temp:.1f}°C, battery reserves are {battery:.1f}%. "
        if paused:
            resp += f"Load-shedding active: {', '.join(paused)} paused."
        else:
            resp += "All subsystems nominal. No active load-shedding."
        return resp
