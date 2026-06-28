---
title: FarAwayOrbitalComputeSystem
emoji: 📈
colorFrom: pink
colorTo: pink
sdk: docker
app_port: 7860
pinned: false
---

# FarAway — Tsukuyomi-1 Mission Control Backend

Unified FastAPI backend for the orbital GPU datacenter simulation.  
All six physics models run in a single process; a background thread
drives the simulation clock while FastAPI serves live telemetry to
any frontend over HTTP + SSE.

---

## Quick Start

```bash
cd faraway_backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Interactive API docs → http://localhost:8000/docs

---

## Architecture

```
Background thread (1 tick/s)
  └─ SimulationState.tick()
        ├─ OrbitalSpigot          → position, sunlit, debris
        ├─ PhoenixSunlightModel   → eclipse state, solar flux
        ├─ PhoenixADCS            → attitude mode, solar/radiator alignment
        ├─ PhoenixPowerModel      → generation, battery, supercap
        ├─ PhoenixThermalModel    → 20-node temps, ammonia loops, PCM
        ├─ PhoenixCommsModel      → link quality, bandwidth, latency
        └─ PhoenixFaultEngine     → active fault lifetime tracking

FastAPI (main thread)
  ├─ GET  /telemetry/stream       SSE — streams last_telemetry every 1 s
  ├─ GET  /telemetry/snapshot     latest frame (JSON)
  ├─ GET  /status                 full status: sat state + missions + logs
  ├─ GET  /health                 quick health check
  ├─ POST /sim/tick               manual advance {seconds: float}
  ├─ POST /sim/speed              change dilation {factor: int}
  ├─ POST /state                  push external telemetry (legacy)
  ├─ POST /inject/{type}          inject failure scenario
  ├─ POST /workload/{name}/pause  pause a named workload
  ├─ POST /workload/{name}/resume resume a named workload
  ├─ GET  /workloads              list all workloads + status
  ├─ POST /ask                    AI agent Q&A {question: str}
  └─ POST /reset                  reset to nominal
```

---

## API Reference

### GET /telemetry/stream
Server-Sent Events.  One JSON frame per second.

**Frontend usage:**
```js
const es = new EventSource('http://localhost:8000/telemetry/stream');
es.onmessage = (e) => {
  const frame = JSON.parse(e.data);
  // frame.orbit   → lat, lon, altitude, is_sunlit, debris_warning
  // frame.power   → battery_charge_pct, solar_generation_kw, net_power_kw
  // frame.thermal → avg_cluster_temp_c, node_temperatures_c[20], pcm_charge_pct
  // frame.adcs    → attitude_mode, solar_efficiency_pct, radiator_view_factor
  // frame.comms   → link_quality_pct, bandwidth_gbps, latency_ms
  // frame.sunlight→ eclipse_state, solar_flux_w_m2
  // frame.scheduler.workloads → [{name, status, power_usage, ...}]
  // frame.faults  → [{name, subsystem, severity, remaining_s}]
};
```

### GET /telemetry/snapshot
Same shape as SSE frame but a single HTTP GET (no streaming).

### GET /status
Full status object:
```json
{
  "satellite": { "temperature": ..., "battery": ..., "healthy_gpus": ... },
  "telemetry": { /* full physics frame */ },
  "missions":  [ { "name": "Wildfire Detection", "status": "active", ... } ],
  "logs":      [ { "time": "...", "type": "warning", "message": "..." } ],
  "health_score": 87,
  "physics_sync": { "loop_a_health_pct": ..., "active_faults": [...] }
}
```

### POST /inject/{failure_type}
Supported types: `gpu_failure` | `debris_strike` | `solar_damage` | `battery_drain`

```bash
curl -X POST http://localhost:8000/inject/debris_strike
```

Response includes `actions` (recovery narrative), updated `satellite`, and `active_faults`.

### POST /workload/{name}/pause & /resume
Name is case-insensitive.  Workloads: `Wildfire Detection`, `Flood Prediction`,
`Climate Monitoring`, `Scientific AI`, `LLM Service`.

```bash
curl -X POST "http://localhost:8000/workload/LLM Service/pause"
curl -X POST "http://localhost:8000/workload/LLM Service/resume"
```

### POST /ask
```bash
curl -X POST http://localhost:8000/ask \
     -H 'Content-Type: application/json' \
     -d '{"question": "Why is the temperature rising?"}'
```

### POST /sim/speed
```bash
curl -X POST http://localhost:8000/sim/speed \
     -H 'Content-Type: application/json' \
     -d '{"factor": 3600}'   # 1 real-second = 1 sim-hour
```

### POST /reset
Resets all physics models, workloads, and logs to launch state.

---

## Telemetry Frame Schema

```
{
  timestamp:         ISO-8601
  mission_days:      float
  sim_elapsed_s:     float

  orbit: {
    is_sunlit:             bool
    latitude:              float  (°)
    longitude:             float  (°)
    altitude_km:           float
    orbit_type:            "SSO (Dawn-Dusk)"
    debris_warning:        bool
  }

  sunlight: {
    eclipse_state:         "FULL_SUN" | "ECLIPSE"
    solar_flux_w_m2:       float
    sunlight_availability_pct: float
    eclipse_duration_minutes:  float
  }

  adcs: {
    attitude_mode:         "SCIENCE_MODE" | "POWER_MODE" | "THERMAL_MODE"
                           | "SAFE_MODE" | "DEBRIS_AVOIDANCE"
    solar_efficiency_pct:  float
    radiator_view_factor:  float  (0–1)
    antenna_alignment_pct: float
    reaction_wheel_momentum_pct: float
    alerts: { safe_mode, thermal_priority, debris_avoidance, ... }
  }

  power: {
    solar_generation_kw:       float
    total_demand_kw:           float
    net_power_kw:              float   (+ charging, - discharging)
    battery_charge_pct:        float
    supercap_charge_pct:       float
    power_survivability_hours: float
    recommended_power_state:   "NOMINAL" | "POWER_SAVE" | "THROTTLE" | "SAFE_MODE"
    alerts: { low_power, critical_power, safe_mode, emergency_shutdown }
  }

  thermal: {
    node_temperatures_c:       float[20]
    avg_cluster_temp_c:        float
    max_node_temp_c:           float
    radiator_temp_c:           float
    coolant_quality:           float  (0=liquid, 1=all vapour)
    loop_a_health_pct:         float
    loop_b_health_pct:         float
    pcm_charge_pct:            float  (0=empty, 100=full)
    thermal_headroom_pct:      float
    predicted_temp_10min_c:    float
    thermal_runaway_risk_pct:  float
    thermal_alert_level:       int    (0–5)
    emergency_shutdown:        bool
  }

  comms: {
    link_quality_pct:          float
    bandwidth_gbps:            float
    latency_ms:                float
    packet_loss_pct:           float
    recommended_link_state:    "NOMINAL" | "DEGRADED" | "RECOVERY" | "LOST"
  }

  scheduler: {
    gpu_load_kw:   float
    workloads:     [ { name, status, priority, power_usage, heat_generation } ]
  }

  faults: [ { name, subsystem, severity, remaining_s } ]
}
```

---

## Frontend Integration Notes

- Connect to `/telemetry/stream` with `EventSource` for live updates (no polling needed).
- Use `/inject/*` buttons to trigger demo scenarios.
- `/status` is useful for an initial page load before SSE connects.
- CORS is open (`*`) — change in `main.py` before production.
- The AI `/ask` endpoint requires `GITHUB_TOKEN` in `.env` (falls back to a canned response if absent).
