import React, { useState, useEffect } from 'react';

export default function CommsRelay({ telemetry, apiBase }) {
  const [satellites, setSatellites] = useState([]);
  const [selectedSat, setSelectedSat] = useState('SAT-ALPHA');
  const [uploadFile, setUploadFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  
  // Transmission State
  const [txState, setTxState] = useState('idle'); // idle, uploading, complete, error
  const [txProgress, setTxProgress] = useState(0);
  const [txResult, setTxResult] = useState(null);
  const [txError, setTxError] = useState(null);

  // Fetch satellites list on load and periodically
  const fetchSatellites = async () => {
    try {
      const res = await fetch(`${apiBase}/satellites`);
      const data = await res.json();
      if (data && data.satellites) {
        setSatellites(data.satellites);
      }
    } catch (e) {
      console.error("Error fetching satellites list", e);
    }
  };

  useEffect(() => {
    fetchSatellites();
    const interval = setInterval(fetchSatellites, 5000);
    return () => clearInterval(interval);
  }, [apiBase]);

  // Handle file select
  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      setUploadFile(file);
      setPreviewUrl(URL.createObjectURL(file));
      setTxState('idle');
      setTxResult(null);
      setTxError(null);
    }
  };

  // Trigger file upload with sample image from backend
  const handleUseSample = async () => {
    try {
      setTxState('fetching_sample');
      // Fetch the sample image from the backend assets
      const res = await fetch(`${apiBase}/static/test_image.jpg`).catch(() => fetch(`${apiBase}/docs` /* fallback check */));
      
      // Let's grab it directly from our workspace if possible, or just generate a local mock image or request it
      // Actually, main.py has test_image.jpg at the root, FastAPI doesn't mount a static folder at /static, but we can download it by fetching it if the backend serves it, or we can use a standard public mock image
      // Wait, let's see if FastAPI has /static route or we can just fetch a dummy image from a CDN as sample
      const sampleUrl = 'https://raw.githubusercontent.com/ultralytics/assets/main/yolov8/bus.jpg';
      const imageRes = await fetch(sampleUrl);
      const blob = await imageRes.blob();
      const file = new File([blob], 'sample_bus.jpg', { type: 'image/jpeg' });
      
      setUploadFile(file);
      setPreviewUrl(sampleUrl);
      setTxState('idle');
      setTxResult(null);
      setTxError(null);
    } catch (e) {
      setTxError("Failed to download sample image.");
      setTxState('error');
    }
  };

  // Perform transmission
  const handleTransmit = async () => {
    if (!uploadFile) return;

    setTxState('uploading');
    setTxProgress(10);
    setTxError(null);

    // Get selected satellite details to calculate latency
    const sat = satellites.find(s => s.id === selectedSat) || { latency_ms: 100 };
    const simulatedLatency = Math.min(Math.max(sat.latency_ms, 200), 2000); // between 0.2s and 2s for visual feedback

    // Progress simulation
    const interval = setInterval(() => {
      setTxProgress((prev) => {
        if (prev >= 90) {
          clearInterval(interval);
          return 90;
        }
        return prev + 15;
      });
    }, simulatedLatency / 6);

    try {
      const formData = new FormData();
      formData.append('file', uploadFile);

      const res = await fetch(`${apiBase}/satellite/transmit/${selectedSat}`, {
        method: 'POST',
        body: formData,
      });

      clearInterval(interval);
      setTxProgress(100);

      const data = await res.json();
      
      if (data.success) {
        setTxResult(data);
        setTxState('complete');
      } else {
        setTxError(data.error || 'Transmission failed.');
        setTxState('error');
      }
    } catch (e) {
      clearInterval(interval);
      setTxError('Network timeout. Link lost.');
      setTxState('error');
    }
  };

  // Render sat list
  return (
    <div className="cyber-card col-12" style={{ minHeight: '390px' }}>
      <div className="corner-accent accent-tl"></div>
      <div className="corner-accent accent-tr"></div>
      <div className="corner-accent accent-bl"></div>
      <div className="corner-accent accent-br"></div>

      <div className="card-header">
        <div className="card-title">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M5 12h14M12 5l7 7-7 7"></path>
          </svg>
          Inter-Satellite Comms Relay & YOLO Deep Learning Hub
        </div>
      </div>

      <div className="card-body" style={{ display: 'grid', gridTemplateColumns: '1.2fr 1.8fr', gap: '16px' }}>
        
        {/* Left Side: Satellite Constellation Status */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', borderRight: '1px solid rgba(0, 240, 255, 0.1)', paddingRight: '16px' }}>
          <div className="cyber-label">Relay Satellite Constellation</div>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', overflowY: 'auto', maxHeight: '280px' }}>
            {satellites.map((sat) => {
              const isActive = selectedSat === sat.id;
              let statusColor = 'var(--color-green)';
              if (sat.link_quality_pct < 40) statusColor = 'var(--color-red)';
              else if (sat.link_quality_pct < 75) statusColor = 'var(--color-amber)';

              return (
                <div 
                  key={sat.id}
                  onClick={() => {
                    setSelectedSat(sat.id);
                    if (txState === 'complete') {
                      setTxState('idle');
                      setTxResult(null);
                    }
                  }}
                  style={{
                    background: isActive ? 'rgba(0, 240, 255, 0.05)' : 'rgba(0,0,0,0.2)',
                    border: `1px solid ${isActive ? 'var(--color-cyan)' : 'rgba(0, 240, 255, 0.1)'}`,
                    borderRadius: '4px',
                    padding: '8px 10px',
                    cursor: 'pointer',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    transition: 'all 0.2s ease',
                    boxShadow: isActive ? '0 0 8px rgba(0, 240, 255, 0.1)' : 'none'
                  }}
                >
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{ fontFamily: 'var(--font-cyber)', fontSize: '0.75rem', fontWeight: 'bold', color: isActive ? 'var(--color-cyan)' : 'var(--color-text)' }}>
                        {sat.name}
                      </span>
                      <span style={{ fontSize: '0.55rem', background: 'rgba(255,255,255,0.05)', padding: '1px 4px', borderRadius: '2px', color: 'var(--color-text-dim)' }}>
                        {sat.type}
                      </span>
                    </div>
                    <div style={{ fontSize: '0.6rem', color: 'var(--color-text-dim)', marginTop: '4px' }}>
                      Range: {sat.distance_km} km | Latency: {sat.latency_ms.toFixed(0)}ms
                    </div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '0.75rem', fontWeight: 'bold', color: statusColor }}>
                      {sat.link_quality_pct.toFixed(0)}%
                    </div>
                    <div className="cyber-label" style={{ fontSize: '0.5rem' }}>LINK QUALITY</div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right Side: Deep Learning Image Relay Transmitter */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div className="cyber-label">
            TSKY-1 RELAY TRANSPONDER (ROUTED VIA <span style={{ color: 'var(--color-cyan)', fontWeight: 'bold' }}>{selectedSat}</span>)
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1.8fr', gap: '16px', flex: 1 }}>
            
            {/* Upload Area */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div style={{
                border: '1px dashed rgba(0, 240, 255, 0.3)',
                borderRadius: '4px',
                height: '140px',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'center',
                alignItems: 'center',
                position: 'relative',
                background: 'rgba(0,0,0,0.3)',
                overflow: 'hidden'
              }}>
                {previewUrl ? (
                  <img 
                    src={previewUrl} 
                    alt="Upload preview" 
                    style={{ width: '100%', height: '100%', objectFit: 'cover' }} 
                  />
                ) : (
                  <div style={{ textAlign: 'center', padding: '10px' }}>
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--color-cyan)" strokeWidth="1.5" style={{ marginBottom: '8px' }}>
                      <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                      <circle cx="8.5" cy="8.5" r="1.5"></circle>
                      <polyline points="21 15 16 10 5 21"></polyline>
                    </svg>
                    <div className="cyber-label" style={{ fontSize: '0.6rem' }}>Select Image</div>
                  </div>
                )}
                <input 
                  type="file" 
                  accept="image/*"
                  onChange={handleFileChange}
                  style={{
                    position: 'absolute',
                    top: 0, left: 0, width: '100%', height: '100%',
                    opacity: 0, cursor: 'pointer'
                  }} 
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
                <button 
                  className="btn-cyber" 
                  style={{ fontSize: '0.65rem', padding: '6px' }}
                  onClick={handleUseSample}
                  disabled={txState === 'uploading' || txState === 'fetching_sample'}
                >
                  {txState === 'fetching_sample' ? 'LOADING...' : 'SAMPLE IMAGE'}
                </button>
                <button 
                  className="btn-cyber btn-purple" 
                  style={{ fontSize: '0.65rem', padding: '6px' }}
                  disabled={!uploadFile || txState === 'uploading' || txState === 'fetching_sample'}
                  onClick={handleTransmit}
                >
                  TRANSMIT
                </button>
              </div>
            </div>

            {/* Results Screen */}
            <div style={{ 
              background: 'rgba(0,0,0,0.4)', 
              border: '1px solid rgba(0, 240, 255, 0.1)', 
              borderRadius: '4px',
              padding: '10px',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'center',
              alignItems: 'center',
              height: '185px',
              position: 'relative',
              overflow: 'hidden'
            }}>
              {/* Scanline overlay */}
              {txState === 'uploading' && (
                <div style={{
                  position: 'absolute', top: 0, left: 0, width: '100%', height: '100%',
                  background: 'linear-gradient(rgba(0, 240, 255, 0) 95%, rgba(0, 240, 255, 0.1) 100%)',
                  animation: 'scanline 2s linear infinite',
                  zIndex: 2, pointerEvents: 'none'
                }} />
              )}

              {txState === 'idle' && (
                <div style={{ textAlign: 'center', color: 'var(--color-text-dim)' }}>
                  <div className="cyber-label">Receiver Status</div>
                  <div style={{ fontSize: '0.75rem', marginTop: '6px' }}>
                    Select a satellite, upload a file and press transmit.
                  </div>
                </div>
              )}

              {txState === 'uploading' && (
                <div style={{ width: '80%', textAlign: 'center' }}>
                  <div className="cyber-label" style={{ marginBottom: '8px' }}>TRANSMITTING PACKETS...</div>
                  <div style={{ height: '8px', background: 'rgba(255,255,255,0.05)', borderRadius: '4px', overflow: 'hidden', border: '1px solid rgba(0,240,255,0.1)' }}>
                    <div style={{ width: `${txProgress}%`, height: '100%', background: 'var(--color-cyan)', boxShadow: 'var(--glow-cyan)', transition: 'width 0.2s ease' }} />
                  </div>
                  <div style={{ fontSize: '0.65rem', color: 'var(--color-cyan)', marginTop: '6px', fontFamily: 'var(--font-cyber)' }}>
                    PROGRESS: {txProgress}%
                  </div>
                </div>
              )}

              {txState === 'error' && (
                <div style={{ textAlign: 'center', padding: '10px' }}>
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--color-red)" strokeWidth="2" style={{ marginBottom: '6px' }}>
                    <polygon points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86 7.86 2"></polygon>
                    <line x1="12" y1="8" x2="12" y2="12"></line>
                    <line x1="12" y1="16" x2="12.01" y2="16"></line>
                  </svg>
                  <div className="cyber-label" style={{ color: 'var(--color-red)' }}>TRANSMISSION FAULT</div>
                  <div style={{ fontSize: '0.7rem', marginTop: '4px', color: 'var(--color-text)' }}>
                    {txError}
                  </div>
                </div>
              )}

              {txState === 'complete' && txResult && (
                <div style={{ width: '100%', height: '100%', display: 'flex', gap: '8px' }}>
                  {/* Annotated Image */}
                  <div style={{ flex: 1.1, border: '1px solid rgba(0,240,255,0.2)', borderRadius: '2px', overflow: 'hidden', background: '#000' }}>
                    <img 
                      src={`data:image/jpeg;base64,${txResult.inference.annotated_image_b64}`} 
                      alt="Annotated detections" 
                      style={{ width: '100%', height: '100%', objectFit: 'contain' }} 
                    />
                  </div>
                  
                  {/* Detections List */}
                  <div style={{ flex: 0.9, display: 'flex', flexDirection: 'column', height: '100%' }}>
                    <div className="cyber-label" style={{ fontSize: '0.55rem', borderBottom: '1px solid rgba(255,255,255,0.05)', paddingBottom: '3px' }}>
                      INFERENCE ENGINE ({txResult.inference.device.toUpperCase()})
                    </div>
                    
                    <div style={{ overflowY: 'auto', flex: 1, marginTop: '4px', display: 'flex', flexDirection: 'column', gap: '3px' }}>
                      {txResult.inference.detections.length === 0 ? (
                        <div style={{ fontSize: '0.65rem', color: 'var(--color-text-dim)', fontStyle: 'italic', padding: '10px 0' }}>
                          No hazards or targets detected in frame.
                        </div>
                      ) : (
                        txResult.inference.detections.map((det, idx) => (
                          <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.65rem', background: 'rgba(255,255,255,0.03)', padding: '2px 4px', borderRadius: '2px', borderLeft: '2px solid var(--color-green)' }}>
                            <span style={{ textTransform: 'capitalize', fontWeight: 'bold' }}>{det.class}</span>
                            <span style={{ color: 'var(--color-cyan)' }}>{(det.confidence * 100).toFixed(0)}%</span>
                          </div>
                        ))
                      )}
                    </div>
                    
                    {/* Metadata */}
                    <div style={{ fontSize: '0.55rem', color: 'var(--color-text-dim)', borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '3px', marginTop: '4px' }}>
                      Delay: {txResult.link.latency_ms.toFixed(0)}ms | Quality: {(txResult.link.link_quality * 100).toFixed(0)}%
                    </div>
                  </div>
                </div>
              )}
            </div>

          </div>
        </div>

      </div>
    </div>
  );
}
