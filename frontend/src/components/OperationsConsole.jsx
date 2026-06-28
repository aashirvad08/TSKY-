import React, { useState } from 'react';

export default function OperationsConsole({ telemetry, apiBase, onInjectFault, onToggleWorkload }) {
  const scheduler = telemetry?.scheduler ?? { gpu_load_kw: 0.0, workloads: [] };
  const workloads = scheduler.workloads ?? [];
  const faults = telemetry?.faults ?? [];

  const [loadingWorkload, setLoadingWorkload] = useState(null);

  const faultTypes = [
    { label: 'GPU Node Overheat', type: 'gpu_failure', color: 'var(--color-amber)' },
    { label: 'Debris Hull Strike', type: 'debris_strike', color: 'var(--color-red)' },
    { label: 'Solar Array Damage', type: 'solar_damage', color: 'var(--color-amber)' },
    { label: 'Battery Core Drain', type: 'battery_drain', color: 'var(--color-red)' }
  ];

  const handleToggle = async (workload) => {
    setLoadingWorkload(workload.name);
    await onToggleWorkload(workload.name, workload.status === 'active');
    setLoadingWorkload(null);
  };

  return (
    <div className="cyber-card col-5" style={{ height: '390px' }}>
      <div className="corner-accent accent-tl"></div>
      <div className="corner-accent accent-tr"></div>
      <div className="corner-accent accent-bl"></div>
      <div className="corner-accent accent-br"></div>

      <div className="card-header">
        <div className="card-title">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect>
            <line x1="8" y1="21" x2="16" y2="21"></line>
            <line x1="12" y1="17" x2="12" y2="21"></line>
          </svg>
          Workload Scheduler & Fault Injection Deck
        </div>
      </div>

      <div className="card-body" style={{ padding: '12px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
        
        {/* Workloads Section */}
        <div>
          <div className="cyber-label" style={{ marginBottom: '6px' }}>Mission Critical Workloads</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', maxHeight: '150px', overflowY: 'auto' }}>
            {workloads.map((wl) => {
              const isActive = wl.status === 'active';
              return (
                <div 
                  key={wl.name}
                  style={{
                    background: 'rgba(0,0,0,0.2)',
                    border: '1px solid rgba(0,240,255,0.06)',
                    borderRadius: '4px',
                    padding: '6px 10px',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{
                      width: '6px',
                      height: '6px',
                      borderRadius: '50%',
                      background: isActive ? 'var(--color-green)' : 'rgba(255,255,255,0.15)',
                      boxShadow: isActive ? 'var(--glow-green)' : 'none'
                    }} />
                    <div>
                      <div style={{ fontSize: '0.75rem', fontWeight: 'bold' }}>{wl.name}</div>
                      <div style={{ fontSize: '0.55rem', color: 'var(--color-text-dim)' }}>
                        Prio: {wl.priority} | Load: {wl.power}kW | Heat: {wl.heat}
                      </div>
                    </div>
                  </div>

                  <button
                    className="btn-cyber"
                    style={{
                      padding: '2px 8px',
                      fontSize: '0.6rem',
                      borderColor: isActive ? 'var(--color-amber)' : 'var(--color-green)',
                      color: isActive ? 'var(--color-amber)' : 'var(--color-green)',
                      minWidth: '65px'
                    }}
                    onClick={() => handleToggle(wl)}
                    disabled={loadingWorkload === wl.name}
                  >
                    {loadingWorkload === wl.name ? '...' : isActive ? 'PAUSE' : 'RESUME'}
                  </button>
                </div>
              );
            })}
            {workloads.length === 0 && (
              <div style={{ fontSize: '0.7rem', color: 'var(--color-text-dim)', fontStyle: 'italic', textAlign: 'center', padding: '10px' }}>
                No active workloads found in core bus.
              </div>
            )}
          </div>
        </div>

        {/* Fault Injection Section */}
        <div>
          <div className="cyber-label" style={{ marginBottom: '6px' }}>Stress Test / Fault Injection</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
            {faultTypes.map((f) => (
              <button
                key={f.type}
                className="btn-cyber btn-red"
                style={{
                  fontSize: '0.65rem',
                  padding: '6px',
                  borderColor: 'rgba(255,0,60,0.3)',
                  background: 'rgba(255,0,60,0.02)'
                }}
                onClick={() => onInjectFault(f.type)}
              >
                {f.label.toUpperCase()}
              </button>
            ))}
          </div>
        </div>

        {/* Active Alarms Indicator Panel */}
        <div style={{ 
          flex: 1, 
          background: faults.length > 0 ? 'rgba(255,0,60,0.06)' : 'rgba(0,255,102,0.03)', 
          border: `1px solid ${faults.length > 0 ? 'rgba(255,0,60,0.2)' : 'rgba(0,255,102,0.1)'}`, 
          borderRadius: '4px',
          padding: '6px 10px',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          overflowY: 'auto'
        }}>
          {faults.length === 0 ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--color-green)' }}>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                <polyline points="20 6 9 17 4 12"></polyline>
              </svg>
              <span style={{ fontSize: '0.7rem', fontFamily: 'var(--font-cyber)', fontWeight: 'bold', letterSpacing: '0.5px' }}>
                TSKY AUTOMATIC RUNTIME NOMINAL - NO FAULTS
              </span>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <div className="pulse" style={{ fontSize: '0.65rem', fontFamily: 'var(--font-cyber)', fontWeight: 'bold', color: 'var(--color-red)', display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '2px' }}>
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                  <polygon points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86 7.86 2"></polygon>
                  <line x1="12" y1="8" x2="12" y2="12"></line>
                </svg>
                WARNING: {faults.length} SYSTEM FAULTS ACTIVE
              </div>
              <div style={{ maxHeight: '45px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '3px' }}>
                {faults.map((f, idx) => (
                  <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.65rem', color: 'var(--color-text)' }}>
                    <span>⚠️ {f.name} ({f.subsystem}) - {f.severity}</span>
                    <span style={{ fontFamily: 'var(--font-cyber)', color: 'var(--color-red)' }}>RECOVERY: {f.remaining_s}s</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
