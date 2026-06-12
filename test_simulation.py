import requests


BASE_URL = "http://127.0.0.1:8000"


def post(path, payload=None):
    response = requests.post(f"{BASE_URL}{path}", json=payload or {}, timeout=20)
    response.raise_for_status()
    return response.json()


def get(path):
    response = requests.get(f"{BASE_URL}{path}", timeout=20)
    response.raise_for_status()
    return response.json()


def mission_names(missions, status):
    return [mission["name"] for mission in missions if mission["status"] == status]


def print_status(status):
    satellite = status["satellite"]
    missions = status["missions"]
    print(f"   Health Score : {status['health_score']}%")
    print(f"   GPUs         : {satellite['healthy_gpus']}/8")
    print(f"   Battery      : {satellite['battery']:.1f}%")
    print(f"   Temperature  : {satellite['temperature']:.1f}°C")
    print(f"   Active       : {mission_names(missions, 'active')}")


def push_normal_telemetry():
    post("/state", {
        "timestamp": "2026-06-12T00:00:00Z",
        "orbit_type": "SSO (Dawn-Dusk)",
        "is_sunlit": True,
        "latitude": 23.4,
        "longitude": 77.2,
        "altitude_km": 400.0,
        "hazard_debris_warning": False,
    })
    post("/state", {
        "solar_port_wing_kw": 3.2,
        "solar_starboard_wing_kw": 3.1,
        "total_power_demand_kw": 4.5,
        "net_power_flow_kw": 1.2,
        "flywheel_rpm": 42000,
        "flywheel_charge_pct": 85.0,
        "alerts": {
            "blackout_critical": False,
            "gyroscopic_stress_warning": False,
        },
    })
    post("/state", {
        "node_temperatures_c": [
            50, 51, 52, 53, 50, 49, 52, 54, 51, 50,
            53, 52, 51, 50, 49, 52, 53, 51, 50, 52,
        ],
        "avg_cluster_temp_c": 52.0,
        "max_node_temp_c": 54.0,
        "radiator_temp_c": 38.0,
        "pcm_saturation_pct": 12.0,
        "ammonia_flow_kg_s": 0.003,
        "mission_status": "NOMINAL",
    })


def print_actions(result):
    for action in result["actions"]:
        print(f"   -> {action}")


def main():
    print("=== PHOENIX Self-Healing Test ===\n")

    print("1. Pushing normal telemetry...")
    push_normal_telemetry()

    print("2. Checking initial status...")
    status = get("/status")
    print_status(status)

    print("\n3. Injecting single GPU failure...")
    print_actions(post("/inject/gpu_failure"))

    print("\n4. Injecting debris strike...")
    print_actions(post("/inject/debris_strike"))

    print("\n5. Status after failures:")
    status = get("/status")
    print_status(status)
    print(f"   Paused       : {mission_names(status['missions'], 'paused')}")

    print("\n6. Asking PHOENIX to explain decisions...")
    answer = post("/ask", {"question": "why were missions paused and what is system health?"})["answer"]
    print(f"   {answer}")

    print("\n7. Recent event log:")
    status = get("/status")
    for event in status["logs"][-10:]:
        print(f"   [{event['time']}] [{event['type'].upper()}] {event['message']}")

    print("\n=== Test Complete ===")


if __name__ == "__main__":
    main()
