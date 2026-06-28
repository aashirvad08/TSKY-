import random
from dataclasses import dataclass

@dataclass
class Fault:
    name: str
    subsystem: str
    severity: str
    duration_seconds: float

class PhoenixFaultEngine:

    def __init__(self):

        self.active_faults = []

    def inject_fault(
        self,
        name,
        subsystem,
        severity,
        duration_seconds
    ):

        self.active_faults.append(
            Fault(
                name=name,
                subsystem=subsystem,
                severity=severity,
                duration_seconds=duration_seconds
            )
        )

    def update(self, sim_seconds):

        resolved = []

        for fault in self.active_faults:

            fault.duration_seconds -= sim_seconds

            if fault.duration_seconds <= 0:
                resolved.append(fault)

        for fault in resolved:
            self.active_faults.remove(fault)

        return self.active_faults