from dataclasses import dataclass
from typing import List


@dataclass
class Workload:
    name: str
    priority: int
    power_usage: float
    heat_generation: float
    status: str = "active"


def default_workloads() -> List[Workload]:
    return [
        Workload("Wildfire Detection", priority=10, power_usage=20, heat_generation=3.0),
        Workload("Flood Prediction", priority=9, power_usage=18, heat_generation=2.5),
        Workload("Climate Monitoring", priority=7, power_usage=15, heat_generation=2.0),
        Workload("Scientific AI", priority=5, power_usage=25, heat_generation=4.0),
        Workload("LLM Service", priority=2, power_usage=30, heat_generation=5.0),
    ]
