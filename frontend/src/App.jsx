import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import OrbitalTracker from './components/OrbitalTracker';
import ThermalGrid from './components/ThermalGrid';
import PowerControl from './components/PowerControl';
import CommsRelay from './components/CommsRelay';
import AgentCopilot from './components/AgentCopilot';
import OperationsConsole from './components/OperationsConsole';
import EventLog from './components/EventLog';

// Determine API base dynamically
const API_BASE = window.location.origin;

export default function App() {
  const [telemetry, setTelemetry] = useState(null);
  const [status, setStatus] = useState(null);
  const [logs, setLogs] = useState([]);
  const [isConnected, setIsConnected] = useState(false);

  // Fetch full status snapshot
  const fetchStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/status`);
      const data = await res.json();
      if (data) {
        setStatus(data);
        if (data.logs) {
          setLogs(data.logs);
        }
      }
    } catch (e) {
      console.error("Error fetching status snapshot", e);
    }
  };

  // Setup SSE telemetry stream
  useEffect(() => {
    fetchStatus();

    const eventSource = new EventSource(`${API_BASE}/telemetry/stream`);
    
    eventSource.onopen = () => {
      setIsConnected(true);
      console.log("SSE Telemetry Uplink Opened.");
    };

    eventSource.onmessage = (event) => {
      try {
        const frame = JSON.parse(event.data);
        setTelemetry(frame);
        
        // Update logs if available in frame
        if (frame.faults && frame.faults.length > 0) {
          // If we have active faults, fetch status to get fresh logs
          fetchStatus();
        }
      } catch (e) {
        console.error("Error parsing telemetry frame", e);
      }
    };

    eventSource.onerror = (err) => {
      setIsConnected(false);
      console.error("SSE Connection Error. Attempting reconnect...", err);
    };

    // Periodically fetch status for logger syncing
    const interval = setInterval(fetchStatus, 3000);

    return () => {
      eventSource.close();
      clearInterval(interval);
    };
  }, []);

  // System Handlers
  const handleReset = async () => {
    try {
      const res = await fetch(`${API_BASE}/reset`, { method: 'POST' });
      const data = await res.json();
      console.log("System reset:", data.message);
      await fetchStatus();
    } catch (e) {
      console.error("Error resetting system", e);
    }
  };

  const handleSetSpeed = async (factor) => {
    try {
      await fetch(`${API_BASE}/sim/speed`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ factor })
      });
      await fetchStatus();
    } catch (e) {
      console.error("Error setting speed dilation", e);
    }
  };

  const handleInjectFault = async (failureType) => {
    try {
      const res = await fetch(`${API_BASE}/inject/${failureType}`, { method: 'POST' });
      const data = await res.json();
      console.log("Injected fault response:", data);
      await fetchStatus();
    } catch (e) {
      console.error("Error injecting fault", e);
    }
  };

  const handleToggleWorkload = async (name, isCurrentlyActive) => {
    const endpoint = isCurrentlyActive ? 'pause' : 'resume';
    try {
      const res = await fetch(`${API_BASE}/workload/${name}/${endpoint}`, { method: 'POST' });
      const data = await res.json();
      console.log(`Workload ${name} ${endpoint} result:`, data);
      await fetchStatus();
    } catch (e) {
      console.error(`Error toggling workload ${name}`, e);
    }
  };

  // Determine if there is any critical alert in the current telemetry
  const isAlertActive = telemetry?.thermal?.emergency_shutdown || 
                        telemetry?.power?.alerts?.critical_power || 
                        (telemetry?.faults && telemetry.faults.length > 0);

  return (
    <div style={{ minHeight: '100vh', width: '100%' }}>
      {/* Global alert background pulse if faults active */}
      {isAlertActive && (
        <div style={{
          position: 'fixed',
          top: 0, left: 0, right: 0, bottom: 0,
          boxShadow: 'inset 0 0 80px rgba(255, 0, 60, 0.15)',
          pointerEvents: 'none',
          zIndex: 999,
          animation: 'pulse-glow 2s infinite ease-in-out'
        }} />
      )}

      <div className="dashboard-container">
        {/* Header Block */}
        <Header 
          telemetry={telemetry} 
          status={status} 
          isConnected={isConnected} 
          onReset={handleReset} 
          onSetSpeed={handleSetSpeed}
          apiBase={API_BASE}
        />

        {/* Row 1: Orbit Map & Thermal Heatmap */}
        <OrbitalTracker telemetry={telemetry} />
        <ThermalGrid telemetry={telemetry} />

        {/* Row 2: Power Circuits & Comms Relay */}
        <PowerControl telemetry={telemetry} />
        <CommsRelay telemetry={telemetry} apiBase={API_BASE} />

        {/* Row 3: Operations & AI Copilot & Logs */}
        <OperationsConsole 
          telemetry={telemetry} 
          apiBase={API_BASE} 
          onInjectFault={handleInjectFault}
          onToggleWorkload={handleToggleWorkload}
        />
        <AgentCopilot telemetry={telemetry} apiBase={API_BASE} />
        <EventLog logs={logs} />
      </div>
    </div>
  );
}
