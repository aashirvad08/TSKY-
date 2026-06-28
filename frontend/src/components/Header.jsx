import React from 'react';

export default function Header({ telemetry, status, isConnected, onReset, onSetSpeed, apiBase }) {
  const healthScore = status?.health_score ?? 100;
  const timeDilation = telemetry?.sim_elapsed_s !== undefined ? (telemetry?.adcs?.solar_array_health_pct !== undefined ? 600 : 1) : 600; // default indicator
  
  // Calculate health status text and color
  let healthColor = 'var(--color-green)';
  let healthText = 'NOMINAL';
  let healthGlow = 'var(--glow-green)';
  
  if (healthScore < 40) {
    healthColor = 'var(--color-red)';
    healthText = 'CRITICAL';
    healthGlow = 'var(--glow-red)';
  } else if (healthScore < 75) {
    healthColor = 'var(--color-amber)';
    healthText = 'DEGRADED';
    healthGlow = 'var(--glow-amber)';
  }

  // Get elapsed days
  const missionDays = telemetry?.mission_days !== undefined ? telemetry.mission_days.toFixed(4) : '0.0000';
  const elapsedSeconds = telemetry?.sim_elapsed_s !== undefined ? telemetry.sim_elapsed_s.toLocaleString() : '0';

  const speeds = [
    { label: 'Real-time (1x)', factor: 1 },
    { label: '60x (1m/s)', factor: 60 },
    { label: '600x (10m/s)', factor: 600 },
    { label: '3600x (1h/s)', factor: 3600 },
  ];

  const currentFactor = telemetry?.sim_elapsed_s !== undefined ? (telemetry?.sim_elapsed_s > 0 ? (telemetry?.sim_elapsed_s / telemetry?.mission_days / 86400) : 600) : 600;
  
  // Try to find matching factor, default to 600
  const activeFactor = [1, 60, 600, 3600].includes(Math.round(currentFactor)) ? Math.round(currentFactor) : 600;

  return (
    <header className="cyber-card col-12" style={{ padding: '16px', flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: '16px' }}>
      <div className="corner-accent accent-tl"></div>
      <div className="corner-accent accent-tr"></div>
      <div className="corner-accent accent-bl"></div>
      <div className="corner-accent accent-br"></div>

      {/* Title & Connection Status */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <div>
          <h1 style={{ fontFamily: 'var(--font-cyber)', fontSize: '1.6rem', fontWeight: 900, textTransform: 'uppercase', background: 'linear-gradient(90deg, #00f0ff, #bd00ff)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', letterSpacing: '2px', display: 'flex', alignItems: 'center', gap: '10px' }}>
            TSUKUYOMI-1
            <span style={{ fontSize: '0.65rem', fontFamily: 'var(--font-body)', border: '1px solid rgba(0, 240, 255, 0.3)', padding: '2px 6px', borderRadius: '4px', color: 'var(--color-cyan)', verticalAlign: 'middle', letterSpacing: '1px' }}>MISSION CONTROL</span>
          </h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '4px' }}>
            <span style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              backgroundColor: isConnected ? 'var(--color-green)' : 'var(--color-red)',
              boxShadow: isConnected ? 'var(--glow-green)' : 'var(--glow-red)',
              display: 'inline-block'
            }} />
            <span className="cyber-label" style={{ fontSize: '0.65rem' }}>
              TELEMETRY: {isConnected ? 'LINK ACTIVE (SSE)' : 'LINK DOWN'}
            </span>
          </div>
        </div>
      </div>

      {/* Clocks */}
      <div style={{ display: 'flex', gap: '24px' }}>
        <div style={{ borderLeft: '2px solid rgba(0,240,255,0.1)', paddingLeft: '12px' }}>
          <div className="cyber-label">Mission Elapsed</div>
          <div className="cyber-value" style={{ color: 'var(--color-cyan)', textShadow: 'var(--glow-cyan)' }}>
            {missionDays} <span style={{ fontSize: '0.75rem', color: 'var(--color-text-dim)' }}>DAYS</span>
          </div>
        </div>
        <div style={{ borderLeft: '2px solid rgba(0,240,255,0.1)', paddingLeft: '12px' }}>
          <div className="cyber-label">Simulated Time</div>
          <div className="cyber-value">
            {elapsedSeconds} <span style={{ fontSize: '0.75rem', color: 'var(--color-text-dim)' }}>SEC</span>
          </div>
        </div>
        <div style={{ borderLeft: '2px solid rgba(0,240,255,0.1)', paddingLeft: '12px' }}>
          <div className="cyber-label">Orbit Model</div>
          <div className="cyber-value" style={{ fontSize: '0.9rem', marginTop: '3px' }}>
            Dawn-Dusk SSO
          </div>
        </div>
      </div>

      {/* Health Score */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <div style={{ textAlign: 'right' }}>
          <div className="cyber-label">SYS Health Index</div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px', justifyContent: 'flex-end' }}>
            <span className="cyber-value" style={{ fontSize: '1.8rem', color: healthColor, textShadow: healthGlow }}>
              {healthScore}
            </span>
            <span style={{ fontSize: '0.75rem', color: 'var(--color-text-dim)' }}>%</span>
          </div>
        </div>
        
        {/* Health Ring/Bar */}
        <div style={{ width: '120px', height: '10px', background: 'rgba(255,255,255,0.05)', borderRadius: '5px', overflow: 'hidden', border: '1px solid rgba(0,240,255,0.1)' }}>
          <div style={{
            width: `${healthScore}%`,
            height: '100%',
            background: `linear-gradient(90deg, var(--color-blue), ${healthColor})`,
            boxShadow: healthGlow,
            transition: 'width 0.5s ease-in-out'
          }} />
        </div>
        <div className="cyber-label" style={{ color: healthColor, border: `1px solid ${healthColor}`, padding: '2px 6px', borderRadius: '4px', fontSize: '0.65rem' }}>
          {healthText}
        </div>
      </div>

      {/* Time Dilation & System Reset */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <span className="cyber-label" style={{ fontSize: '0.6rem', textAlign: 'center' }}>Time Dilation</span>
          <div style={{ display: 'flex', gap: '4px', background: 'rgba(0,0,0,0.3)', padding: '2px', borderRadius: '4px', border: '1px solid rgba(0, 240, 255, 0.1)' }}>
            {speeds.map((s) => (
              <button
                key={s.factor}
                className="btn-cyber"
                style={{
                  padding: '4px 8px',
                  fontSize: '0.65rem',
                  border: 'none',
                  background: activeFactor === s.factor ? 'var(--color-cyan)' : 'transparent',
                  color: activeFactor === s.factor ? 'var(--bg-deep)' : 'var(--color-cyan)',
                  borderRadius: '2px',
                  fontWeight: activeFactor === s.factor ? '700' : '500',
                  boxShadow: activeFactor === s.factor ? 'var(--glow-cyan)' : 'none'
                }}
                onClick={() => onSetSpeed(s.factor)}
              >
                {s.factor === 1 ? '1x' : s.factor === 60 ? '60x' : s.factor === 600 ? '600x' : '3.6k'}
              </button>
            ))}
          </div>
        </div>

        <button 
          className="btn-cyber btn-red"
          style={{ padding: '8px 12px', height: 'fit-content', fontSize: '0.75rem' }}
          onClick={onReset}
        >
          RESET NOMINAL
        </button>
      </div>
    </header>
  );
}
