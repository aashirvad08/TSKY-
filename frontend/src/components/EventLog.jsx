import React, { useEffect, useRef } from 'react';

export default function EventLog({ logs }) {
  const containerRef = useRef(null);

  // Auto scroll to bottom of logs locally within container
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [logs]);

  const getLogColor = (type) => {
    switch (type?.toLowerCase()) {
      case 'critical':
      case 'red':
        return 'var(--color-red)';
      case 'warning':
      case 'amber':
        return 'var(--color-amber)';
      case 'recovery':
      case 'success':
        return 'var(--color-green)';
      case 'failure':
        return 'var(--color-purple)';
      case 'info':
      default:
        return 'var(--color-cyan)';
    }
  };

  return (
    <div className="cyber-card col-3" style={{ height: '390px' }}>
      <div className="corner-accent accent-tl"></div>
      <div className="corner-accent accent-tr"></div>
      <div className="corner-accent accent-bl"></div>
      <div className="corner-accent accent-br"></div>

      <div className="card-header">
        <div className="card-title">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="4 17 10 11 12 13 18 7"></polyline>
            <polyline points="12 5 19 5 19 12"></polyline>
          </svg>
          Uplink Telemetry Log Feed
        </div>
      </div>

      <div className="card-body" style={{ padding: '10px', background: 'rgba(3, 4, 7, 0.95)', fontFamily: 'var(--font-cyber)', display: 'flex', flexDirection: 'column', height: '100%' }}>
        
        {/* Terminal Logs Container */}
        <div 
          ref={containerRef}
          style={{
            flex: 1,
            overflowY: 'auto',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
            paddingRight: '4px'
          }}
        >
          {logs && logs.length > 0 ? (
            logs.map((log, idx) => (
              <div 
                key={idx} 
                style={{ 
                  fontSize: '0.65rem', 
                  lineHeight: '1.4', 
                  borderBottom: '1px solid rgba(255,255,255,0.02)',
                  paddingBottom: '4px',
                  wordBreak: 'break-word'
                }}
              >
                <span style={{ color: 'var(--color-text-dim)', marginRight: '6px' }}>
                  [{log.time || '00:00:00'}]
                </span>
                <span style={{ color: getLogColor(log.type), marginRight: '6px', fontWeight: 'bold' }}>
                  [{log.type ? log.type.toUpperCase() : 'INFO'}]
                </span>
                <span style={{ color: 'var(--color-text)' }}>
                  {log.message}
                </span>
              </div>
            ))
          ) : (
            <div style={{ color: 'var(--color-text-dim)', fontStyle: 'italic', fontSize: '0.7rem', padding: '10px 0', textAlign: 'center' }}>
              Uplink open. Waiting for telemetry packets...
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
