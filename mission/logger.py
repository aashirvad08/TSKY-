from datetime import datetime
from typing import List, Dict

class EventLogger:
    def __init__(self):
        self.events: List[Dict] = []

    def log(self, message: str, event_type: str = "info"):
        # event_type: "info" | "warning" | "critical" | "recovery" | "failure"
        entry = {
            "time": datetime.utcnow().strftime("%H:%M:%S"),
            "message": message,
            "type": event_type
        }
        self.events.append(entry)
        print(f"[{entry['time']}] [{event_type.upper()}] {message}")

    def log_recovery_sequence(self, failure_type: str, actions: List[str]):
        """Logs a full recovery sequence with proper types."""
        self.log(f"── FAILURE INJECTED: {failure_type} ──", "failure")
        for action in actions:
            etype = "failure" if action.startswith(("FAILURE DETECTED", "ROOT CAUSE")) else "recovery"
            self.log(action, etype)
        self.log("── MISSION CONTINUITY PRESERVED ──", "recovery")

    def get_recent(self, n: int = 20) -> List[Dict]:
        return self.events[-n:]
