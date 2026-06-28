import React from 'react';

export default function PowerControl({ telemetry }) {
  const power = telemetry?.power ?? {};
  const isSunlit = telemetry?.orbit?.is_sunlit ?? true;
  const solarGen = power.solar_generation_kw ?? 0.0;
  const totalDemand = power.total_demand_kw ?? 0.0;
  const netPower = power.net_power_kw ?? 0.0;
  const solarHealth = power.solar_array_health_pct ?? 100.0;
  const batteryPct = power.battery_charge_pct ?? 100.0;
  const batteryAHealth = power.battery_a_health_pct ?? 100.0;
  const batteryBHealth = power.battery_b_health_pct ?? 100.0;
  const supercapPct = power.supercap_charge_pct ?? 100.0;
  const survivability = power.power_survivability_hours ?? 24.0;
  const recommendedState = power.recommended_power_state ?? 'NOMINAL';
  const alerts = power.alerts ?? {};

  const isDischarging = netPower < 0;

  // Render animated circuit flows
  // Using stroke-dasharray and stroke-dashoffset animate dashes in SVG
  const flowActive = isSunlit && solarGen > 0;
  const dischargeActive = isDischarging && batteryPct > 0;

  return (
    <div className="cyber-card col-6 alert-active" style={{ height: '390px' }}>
      <div className="corner-accent accent-tl"></div>
      <div className="corner-accent accent-tr"></div>
      <div className="corner-accent accent-bl"></div>
      <div className="corner-accent accent-br"></div>

      <div className="card-header">
        <div className="card-title">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
          </svg>
          Power Management & Electrical Flow
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          {alerts.low_power && (
            <span style={{ background: 'var(--color-amber)', color: 'black', fontSize: '0.6rem', padding: '2px 6px', borderRadius: '4px', fontWeight: 'bold', animation: 'pulse-glow 1s infinite' }}>
              LOW BATTERY
            </span>
          )}
          {alerts.critical_power && (
            <span style={{ background: 'var(--color-red)', color: 'white', fontSize: '0.6rem', padding: '2px 6px', borderRadius: '4px', fontWeight: 'bold', animation: 'pulse-glow 0.8s infinite' }}>
              CRITICAL POWER
            </span>
          )}
          <span style={{
            background: 'rgba(0,0,0,0.3)',
            border: `1px solid ${isDischarging ? 'var(--color-amber)' : 'var(--color-green)'}`,
            padding: '2px 6px',
            borderRadius: '4px',
            fontSize: '0.65rem',
            color: isDischarging ? 'var(--color-amber)' : 'var(--color-green)'
          }}>
            {isDischarging ? 'DISCHARGING' : 'NET CHARGING'}
          </span>
        </div>
      </div>

      <div className="card-body" style={{ gap: '12px', overflow: 'hidden' }}>
        
        {/* Animated Flow Layout */}
        <div style={{
          width: '100%',
          height: '115px',
          background: 'rgba(5, 7, 12, 0.5)',
          border: '1px solid rgba(0, 240, 255, 0.08)',
          borderRadius: '4px',
          position: 'relative',
          padding: '8px'
        }}>
          {/* SVG routing lines */}
          <svg width="100%" height="100%" viewBox="0 0 440 100" style={{ position: 'absolute', top: 0, left: 0 }}>
            {/* Definitions for glow filters */}
            <defs>
              <filter id="glow-cyan-svg" x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur stdDeviation="3" result="blur" />
                <feComposite in="SourceGraphic" in2="blur" operator="over" />
              </filter>
            </defs>

            {/* Circuit paths */}
            {/* Solar Array (x: 20, y: 50) -> Power Bus (x: 220, y: 50) */}
            <path d="M 60 50 L 190 50" stroke={flowActive ? "rgba(0, 240, 255, 0.4)" : "rgba(255,255,255,0.05)"} strokeWidth="2" fill="none" />
            {flowActive && (
              <path d="M 60 50 L 190 50" stroke="var(--color-cyan)" strokeWidth="3" strokeDasharray="6,12" strokeDashoffset="0" fill="none" style={{ animation: 'dash 1.5s linear infinite' }} filter="url(#glow-cyan-svg)" />
            )}

            {/* Power Bus (x: 220, y: 50) -> Battery/Supercap (down to y: 85) */}
            <path d="M 220 50 L 220 80" stroke={dischargeActive ? "rgba(255, 157, 0, 0.4)" : flowActive ? "rgba(0, 240, 255, 0.4)" : "rgba(255,255,255,0.05)"} strokeWidth="2" fill="none" />
            {flowActive && !isDischarging && (
              <path d="M 220 50 L 220 80" stroke="var(--color-cyan)" strokeWidth="3" strokeDasharray="6,12" fill="none" style={{ animation: 'dash 1.5s linear infinite', animationDirection: 'normal' }} filter="url(#glow-cyan-svg)" />
            )}
            {isDischarging && (
              <path d="M 220 80 L 220 50" stroke="var(--color-amber)" strokeWidth="3" strokeDasharray="6,12" fill="none" style={{ animation: 'dash 1.5s linear infinite', animationDirection: 'normal' }} />
            )}

            {/* Power Bus (x: 220, y: 50) -> GPU Datacenter (x: 380, y: 50) */}
            <path d="M 250 50 L 380 50" stroke={totalDemand > 0 ? "rgba(0, 240, 255, 0.4)" : "rgba(255,255,255,0.05)"} strokeWidth="2" fill="none" />
            {totalDemand > 0 && (
              <path d="M 250 50 L 380 50" stroke={isDischarging ? "var(--color-amber)" : "var(--color-cyan)"} strokeWidth="3" strokeDasharray="6,12" fill="none" style={{ animation: 'dash 1.2s linear infinite' }} filter={isDischarging ? "none" : "url(#glow-cyan-svg)"} />
            )}
          </svg>

          {/* Node overlays */}
          {/* Solar Arrays */}
          <div style={{ position: 'absolute', left: '10px', top: '18px', width: '90px', padding: '6px', background: 'rgba(10,12,22,0.9)', border: '1px solid rgba(0,240,255,0.2)', borderRadius: '4px', textAlign: 'center' }}>
            <div className="cyber-label" style={{ fontSize: '0.55rem' }}>Solar Arrays</div>
            <div className="cyber-value" style={{ fontSize: '0.85rem', color: isSunlit ? 'var(--color-cyan)' : 'var(--color-text-dim)' }}>
              {isSunlit ? `${solarGen.toFixed(1)} kW` : 'ECLIPSE'}
            </div>
            <div className="cyber-label" style={{ fontSize: '0.5rem', color: 'rgba(255,255,255,0.3)' }}>HLT: {solarHealth.toFixed(0)}%</div>
          </div>

          {/* Central Bus */}
          <div style={{ position: 'absolute', left: '175px', top: '15px', width: '90px', padding: '6px', background: 'rgba(10,12,22,0.9)', border: '1px solid rgba(0,240,255,0.3)', borderRadius: '4px', textAlign: 'center', boxShadow: 'var(--glow-cyan)' }}>
            <div className="cyber-label" style={{ fontSize: '0.55rem' }}>Core Bus</div>
            <div className="cyber-value" style={{ fontSize: '0.85rem', color: netPower >= 0 ? 'var(--color-green)' : 'var(--color-amber)' }}>
              {netPower >= 0 ? `+${netPower.toFixed(1)}` : `${netPower.toFixed(1)}`} kW
            </div>
            <div className="cyber-label" style={{ fontSize: '0.5rem', color: 'rgba(255,255,255,0.4)' }}>SYS: {recommendedState}</div>
          </div>

          {/* Consumer Loads */}
          <div style={{ position: 'absolute', right: '10px', top: '18px', width: '90px', padding: '6px', background: 'rgba(10,12,22,0.9)', border: '1px solid rgba(0,240,255,0.2)', borderRadius: '4px', textAlign: 'center' }}>
            <div className="cyber-label" style={{ fontSize: '0.55rem' }}>Compute Load</div>
            <div className="cyber-value" style={{ fontSize: '0.85rem', color: 'var(--color-text)' }}>{totalDemand.toFixed(1)} kW</div>
            <div className="cyber-label" style={{ fontSize: '0.5rem', color: 'rgba(255,255,255,0.3)' }}>GPU+COOLING</div>
          </div>
        </div>

        {/* Energy Storage Meters */}
        <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 0.8fr', gap: '16px', flex: 1 }}>
          
          {/* Battery banks details */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
              <span className="cyber-label" style={{ fontSize: '0.6rem' }}>MAIN LITHIUM BATTERY BANKS</span>
              <span className="cyber-value" style={{ fontSize: '1.1rem', color: batteryPct < 25 ? 'var(--color-red)' : batteryPct < 50 ? 'var(--color-amber)' : 'var(--color-green)' }}>
                {batteryPct.toFixed(1)}%
              </span>
            </div>
            
            <div style={{ height: '12px', background: 'rgba(255,255,255,0.05)', borderRadius: '6px', overflow: 'hidden', border: '1px solid rgba(0,240,255,0.15)', display: 'flex' }}>
              <div style={{
                width: `${batteryPct}%`,
                height: '100%',
                background: batteryPct < 25 
                  ? 'linear-gradient(90deg, #ff0000, var(--color-red))' 
                  : batteryPct < 50 
                    ? 'linear-gradient(90deg, var(--color-amber), #ffc800)' 
                    : 'linear-gradient(90deg, var(--color-blue), var(--color-green))',
                boxShadow: batteryPct < 25 ? 'var(--glow-red)' : batteryPct < 50 ? 'var(--glow-amber)' : 'var(--glow-green)',
                transition: 'width 0.5s ease-in-out'
              }} />
            </div>

            {/* Individual Battery Health readouts */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginTop: '4px' }}>
              <div style={{ background: 'rgba(255,255,255,0.02)', padding: '6px', borderRadius: '4px', border: '1px solid rgba(255,255,255,0.03)' }}>
                <div className="cyber-label" style={{ fontSize: '0.5rem' }}>Bank A Health</div>
                <div style={{ fontFamily: 'var(--font-cyber)', fontSize: '0.75rem', fontWeight: 'bold' }}>{batteryAHealth.toFixed(1)}%</div>
              </div>
              <div style={{ background: 'rgba(255,255,255,0.02)', padding: '6px', borderRadius: '4px', border: '1px solid rgba(255,255,255,0.03)' }}>
                <div className="cyber-label" style={{ fontSize: '0.5rem' }}>Bank B Health</div>
                <div style={{ fontFamily: 'var(--font-cyber)', fontSize: '0.75rem', fontWeight: 'bold' }}>{batteryBHealth.toFixed(1)}%</div>
              </div>
            </div>
          </div>

          {/* Supercapacitor & Reserve Time */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', borderLeft: '1px solid rgba(0, 240, 255, 0.1)', paddingLeft: '16px' }}>
            <div>
              <div className="cyber-label" style={{ fontSize: '0.55rem' }}>Supercapacitor</div>
              <div style={{ display: 'flex', justifyItems: 'center', gap: '8px', marginTop: '2px' }}>
                <span className="cyber-value" style={{ fontSize: '1rem', color: 'var(--color-cyan)' }}>{supercapPct.toFixed(0)}%</span>
                <span style={{ fontSize: '0.65rem', color: 'var(--color-text-dim)', alignSelf: 'center' }}>(Transient Buff)</span>
              </div>
              <div style={{ height: '4px', background: 'rgba(255,255,255,0.05)', borderRadius: '2px', overflow: 'hidden', marginTop: '4px' }}>
                <div style={{ width: `${supercapPct}%`, height: '100%', background: 'var(--color-cyan)', boxShadow: 'var(--glow-cyan)' }} />
              </div>
            </div>

            <div>
              <div className="cyber-label" style={{ fontSize: '0.55rem' }}>Reserve Autonomy</div>
              <div className="cyber-value" style={{ fontSize: '1.2rem', color: survivability < 5 ? 'var(--color-red)' : 'var(--color-text)' }}>
                {survivability > 99 ? '>99' : survivability.toFixed(1)} <span style={{ fontSize: '0.75rem', color: 'var(--color-text-dim)' }}>HRS</span>
              </div>
              <div className="cyber-label" style={{ fontSize: '0.5rem', color: 'rgba(255,255,255,0.3)' }}>UNTIL COMPLETE DEPLETION</div>
            </div>
          </div>

        </div>

      </div>
    </div>
  );
}
