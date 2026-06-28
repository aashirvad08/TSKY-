import React, { useEffect, useState } from 'react';

export default function OrbitalTracker({ telemetry }) {
  const [history, setHistory] = useState([]);

  const lat = telemetry?.orbit?.latitude ?? 0;
  const lon = telemetry?.orbit?.longitude ?? 0;
  const altitude = telemetry?.orbit?.altitude_km ?? 550;
  const isSunlit = telemetry?.orbit?.is_sunlit ?? true;
  const debrisWarning = telemetry?.orbit?.debris_warning ?? false;
  const sunlightAvailability = telemetry?.sunlight?.sunlight_availability_pct ?? 95;
  const eclipseState = telemetry?.sunlight?.eclipse_state ?? 'FULL_SUN';

  // Map coordinates to SVG dimensions (width: 500, height: 250)
  const mapWidth = 500;
  const mapHeight = 250;

  const getX = (longitude) => {
    return ((longitude + 180) / 360) * mapWidth;
  };

  const getY = (latitude) => {
    // Latitude goes from 90 (top) to -90 (bottom)
    return ((90 - latitude) / 180) * mapHeight;
  };

  const currentX = getX(lon);
  const currentY = getY(lat);

  // Maintain coordinate history for drawing the path
  useEffect(() => {
    if (telemetry?.orbit) {
      setHistory((prev) => {
        const newPoint = { lat, lon, x: getX(lon), y: getY(lat), timestamp: Date.now() };
        // Check if last point is the same to avoid duplicates
        if (prev.length > 0) {
          const last = prev[prev.length - 1];
          if (Math.abs(last.lat - lat) < 0.001 && Math.abs(last.lon - lon) < 0.001) {
            return prev;
          }
        }
        
        // Keep last 50 points
        const updated = [...prev, newPoint];
        if (updated.length > 60) {
          return updated.slice(updated.length - 60);
        }
        return updated;
      });
    }
  }, [lat, lon, telemetry?.orbit]);

  // Clean history on reset (if elapsed time is low)
  useEffect(() => {
    if (telemetry?.sim_elapsed_s < 2) {
      setHistory([]);
    }
  }, [telemetry?.sim_elapsed_s]);

  // Generate SVG polyline points from history
  // To handle wrapping at longitude borders (180 to -180), we can draw separate segments
  const segments = [];
  let currentSegment = [];

  for (let i = 0; i < history.length; i++) {
    const pt = history[i];
    if (i > 0) {
      const prevPt = history[i - 1];
      // If there's a huge longitude jump, start a new segment
      if (Math.abs(pt.lon - prevPt.lon) > 180) {
        segments.push(currentSegment);
        currentSegment = [];
      }
    }
    currentSegment.push(`${pt.x},${pt.y}`);
  }
  if (currentSegment.length > 0) {
    segments.push(currentSegment);
  }

  // Draw day/night shadow terminator
  // Since Dawn-Dusk SSO orbits along the terminator, the sunlit side covers half the globe.
  // We can represent this with a vertical gradient/boundary representing day vs night.
  // We will offset it based on the satellite's longitude and orbit time to make it dynamic.
  const shadowX = ((Date.now() / 8000) % 1) * mapWidth;

  return (
    <div className="cyber-card col-6 alert-active" style={{ height: '390px' }}>
      <div className="corner-accent accent-tl"></div>
      <div className="corner-accent accent-tr"></div>
      <div className="corner-accent accent-bl"></div>
      <div className="corner-accent accent-br"></div>

      <div className="card-header">
        <div className="card-title">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10"></circle>
            <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
            <path d="M2 12h20"></path>
          </svg>
          Orbital Position & Trajectory
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          {debrisWarning && (
            <span style={{
              background: 'var(--color-red)',
              color: 'var(--color-text)',
              fontSize: '0.6rem',
              fontWeight: '700',
              padding: '2px 6px',
              borderRadius: '4px',
              animation: 'pulse-glow 1s infinite'
            }}>
              DEBRIS WARNING
            </span>
          )}
          <span style={{
            background: isSunlit ? 'rgba(0, 240, 255, 0.1)' : 'rgba(189, 0, 255, 0.1)',
            color: isSunlit ? 'var(--color-cyan)' : 'var(--color-purple)',
            border: `1px solid ${isSunlit ? 'var(--color-cyan)' : 'var(--color-purple)'}`,
            fontSize: '0.65rem',
            padding: '2px 6px',
            borderRadius: '4px'
          }}>
            {eclipseState}
          </span>
        </div>
      </div>

      <div className="card-body" style={{ position: 'relative', display: 'flex', flexDirection: 'column', gap: '12px' }}>
        
        {/* Tracking Map Screen */}
        <div style={{
          width: '100%',
          height: '215px',
          background: 'rgba(5, 7, 12, 0.8)',
          border: '1px solid rgba(0, 240, 255, 0.1)',
          borderRadius: '4px',
          overflow: 'hidden',
          position: 'relative'
        }}>
          {/* Scanning Line overlay */}
          <div style={{
            position: 'absolute',
            top: 0,
            left: 0,
            width: '100%',
            height: '100%',
            background: 'linear-gradient(rgba(0, 240, 255, 0) 95%, rgba(0, 240, 255, 0.05) 98%, rgba(0, 240, 255, 0.1) 100%)',
            animation: 'scanline 6s linear infinite',
            pointerEvents: 'none'
          }} />

          {/* SVG Map Projection */}
          <svg width="100%" height="100%" viewBox={`0 0 ${mapWidth} ${mapHeight}`} style={{ display: 'block' }}>
            {/* Grid Lines */}
            {Array.from({ length: 9 }).map((_, i) => (
              <line 
                key={`lon-${i}`} 
                x1={(mapWidth / 8) * i} 
                y1="0" 
                x2={(mapWidth / 8) * i} 
                y2={mapHeight} 
                stroke="rgba(0, 240, 255, 0.05)" 
                strokeWidth="1"
              />
            ))}
            {Array.from({ length: 5 }).map((_, i) => (
              <line 
                key={`lat-${i}`} 
                x1="0" 
                y1={(mapHeight / 4) * i} 
                x2={mapWidth} 
                y2={(mapHeight / 4) * i} 
                stroke="rgba(0, 240, 255, 0.05)" 
                strokeWidth="1"
              />
            ))}

            {/* Earth Continent Outline proxies - Simplified outlines for visual beauty */}
            {/* Americas */}
            <path d="M70,20 Q120,40 100,100 T120,160 T145,210 T140,240 T110,210 Q90,170 80,120 T50,80 T40,40 Z" fill="rgba(255, 255, 255, 0.02)" stroke="rgba(255, 255, 255, 0.04)" strokeWidth="1" />
            {/* Eurasia / Africa */}
            <path d="M220,20 Q280,30 350,15 T420,40 T450,100 T360,110 T320,130 Q330,170 360,200 Q260,220 220,120 T210,80 Z" fill="rgba(255, 255, 255, 0.02)" stroke="rgba(255, 255, 255, 0.04)" strokeWidth="1" />
            {/* Australia */}
            <path d="M420,170 Q460,165 470,185 T430,220 T400,200 Z" fill="rgba(255, 255, 255, 0.02)" stroke="rgba(255, 255, 255, 0.04)" strokeWidth="1" />

            {/* Orbit paths */}
            {segments.map((seg, index) => (
              <polyline
                key={`orbit-path-${index}`}
                fill="none"
                stroke="var(--color-cyan)"
                strokeWidth="1.5"
                strokeDasharray="2 3"
                opacity="0.6"
                points={seg.join(' ')}
              />
            ))}

            {/* Satellite Position Glowing marker */}
            {history.length > 0 && (
              <>
                <circle cx={currentX} cy={currentY} r="8" fill="none" stroke="var(--color-cyan)" strokeWidth="1.5" opacity="0.8">
                  <animate attributeName="r" values="5;15;5" dur="2s" repeatCount="indefinite" />
                  <animate attributeName="opacity" values="0.8;0;0.8" dur="2s" repeatCount="indefinite" />
                </circle>
                <circle cx={currentX} cy={currentY} r="3.5" fill={isSunlit ? "var(--color-cyan)" : "var(--color-purple)"} />
              </>
            )}

            {/* Current Position Text Box */}
            <g transform={`translate(${currentX > mapWidth - 110 ? currentX - 110 : currentX + 10}, ${currentY > mapHeight - 40 ? currentY - 45 : currentY + 10})`}>
              <rect width="100" height="35" rx="3" fill="rgba(10, 12, 22, 0.9)" stroke="rgba(0, 240, 255, 0.3)" strokeWidth="1" />
              <text x="5" y="14" fill="var(--color-text)" fontSize="7.5" fontFamily="var(--font-cyber)" fontWeight="bold">TSKY-1 NODE</text>
              <text x="5" y="26" fill="var(--color-cyan)" fontSize="8" fontFamily="var(--font-body)">{lat.toFixed(2)}°N, {lon.toFixed(2)}°E</text>
            </g>
          </svg>
        </div>

        {/* Telemetry readouts */}
        <div style={{ display: 'flex', justifyContent: 'space-between', background: 'rgba(0, 240, 255, 0.02)', padding: '10px', borderRadius: '4px', border: '1px solid rgba(0, 240, 255, 0.05)' }}>
          <div>
            <div className="cyber-label" style={{ fontSize: '0.6rem' }}>Altitude</div>
            <div className="cyber-value" style={{ fontSize: '1rem', color: 'var(--color-text)' }}>
              {altitude.toFixed(1)} <span style={{ fontSize: '0.7rem', color: 'var(--color-text-dim)' }}>KM</span>
            </div>
          </div>
          <div>
            <div className="cyber-label" style={{ fontSize: '0.6rem' }}>Daylight Access</div>
            <div className="cyber-value" style={{ fontSize: '1rem', color: 'var(--color-cyan)' }}>
              {sunlightAvailability.toFixed(1)}<span style={{ fontSize: '0.7rem' }}>%</span>
            </div>
          </div>
          <div>
            <div className="cyber-label" style={{ fontSize: '0.6rem' }}>Position (Lat/Lon)</div>
            <div className="cyber-value" style={{ fontSize: '1rem' }}>
              {lat.toFixed(3)}° / {lon.toFixed(3)}°
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
