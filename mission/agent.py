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
        temp = satellite_state.get("temperature", 40)
        healthy_gpus = satellite_state.get("healthy_gpus", 8)
        missions = self.mm.get_status_dict()
        paused = [m["name"] for m in missions if m["status"] == "paused"]
        active = [m["name"] for m in missions if m["status"] == "active"]

        system_prompt = """You are PHOENIX, the autonomous AI managing an orbital data center 400km above Earth.
You speak in short, confident, technical sentences. No fluff.
When asked why something happened, explain using the actual numbers provided.
Never say you don't know — always give a direct answer based on the telemetry."""

        context = f"""Current satellite state:
- Temperature: {temp:.1f}°C  (critical threshold: 85°C)
- Battery: {battery:.0f}%  (critical threshold: 20%)
- Healthy GPUs: {healthy_gpus}/8
- Active missions: {', '.join(active) if active else 'none'}
- Paused missions: {', '.join(paused) if paused else 'none'}
- Recent events: {[e['message'] for e in self.logger.get_recent(5)]}
"""

        try:
            client = self._get_client()
            if not client:
                return self._fallback_explanation(battery, temp, healthy_gpus, active, paused)

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": context + "\n\nQuestion: " + question},
                ],
                max_tokens=150,
                temperature=0.4,
            )
            return response.choices[0].message.content
        except Exception:
            return self._fallback_explanation(battery, temp, healthy_gpus, active, paused)

    def _get_client(self):
        if self.client:
            return self.client
        token = os.getenv("GITHUB_TOKEN")
        if not token or OpenAI is None:
            return None
        self.client = OpenAI(
            base_url="https://models.inference.ai.azure.com",
            api_key=token,
            timeout=5.0,
        )
        return self.client

    def _fallback_explanation(self, battery, temp, healthy_gpus, active, paused) -> str:
        active_text = ", ".join(active) if active else "no active missions"
        paused_text = ", ".join(paused) if paused else "no paused missions"
        return (
            "PHOENIX: Telemetry is stable enough for autonomous explanation. "
            f"Battery is {battery:.1f}%, temperature is {temp:.1f}°C, and GPU capacity is {healthy_gpus}/8. "
            f"Active missions: {active_text}. Paused missions: {paused_text}. "
            "The scheduler preserves higher-priority Earth observation workloads first."
        )
