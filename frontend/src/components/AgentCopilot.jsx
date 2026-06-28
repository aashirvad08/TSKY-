import React, { useState, useRef, useEffect } from 'react';

export default function AgentCopilot({ telemetry, apiBase }) {
  const [messages, setMessages] = useState([
    {
      sender: 'tsky',
      text: 'TSKY-1 AI Autopilot online. Ask me anything regarding current telemetry, thermal hazards, or active workloads.',
      time: new Date().toLocaleTimeString()
    }
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const chatContainerRef = useRef(null);

  // Suggested questions
  const suggestions = [
    "Why is the temperature rising?",
    "Check ammonia cooling loop integrity.",
    "Explain power reserves & solar input.",
    "Active fault status & recovery protocols."
  ];

  // Scroll to bottom locally within container
  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  const handleSend = async (textToSend) => {
    const text = textToSend || inputValue;
    if (!text.trim()) return;

    if (!textToSend) {
      setInputValue('');
    }

    // Add user message
    const userMsg = {
      sender: 'user',
      text: text,
      time: new Date().toLocaleTimeString()
    };
    setMessages(prev => [...prev, userMsg]);
    setIsLoading(true);

    try {
      const res = await fetch(`${apiBase}/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: text })
      });
      const data = await res.json();
      
      const tskyMsg = {
        sender: 'tsky',
        text: data.answer || 'No response received from core terminal.',
        time: new Date().toLocaleTimeString()
      };
      setMessages(prev => [...prev, tskyMsg]);
    } catch (e) {
      const errorMsg = {
        sender: 'tsky',
        text: 'COMMS FAILURE: Unable to reach TSKY uplink. Verify backend server is running.',
        time: new Date().toLocaleTimeString()
      };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="cyber-card col-4" style={{ height: '390px' }}>
      <div className="corner-accent accent-tl"></div>
      <div className="corner-accent accent-tr"></div>
      <div className="corner-accent accent-bl"></div>
      <div className="corner-accent accent-br"></div>

      <div className="card-header">
        <div className="card-title">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
          </svg>
          TSKY Autonomous Agent Copilot
        </div>
      </div>

      <div className="card-body" style={{ padding: '12px', display: 'flex', flexDirection: 'column', height: '100%' }}>
        
        {/* Chat History Panel */}
        <div 
          ref={chatContainerRef}
          style={{
            flex: 1,
            background: 'rgba(5, 7, 12, 0.7)',
            border: '1px solid rgba(0, 240, 255, 0.08)',
            borderRadius: '4px',
            padding: '10px',
            overflowY: 'auto',
            display: 'flex',
            flexDirection: 'column',
            gap: '10px',
            marginBottom: '8px'
          }}
        >
          {messages.map((msg, idx) => (
            <div 
              key={idx} 
              style={{
                alignSelf: msg.sender === 'user' ? 'flex-end' : 'flex-start',
                maxWidth: '85%',
                background: msg.sender === 'user' ? 'rgba(0, 240, 255, 0.08)' : 'rgba(189, 0, 255, 0.05)',
                border: `1px solid ${msg.sender === 'user' ? 'rgba(0, 240, 255, 0.2)' : 'rgba(189, 0, 255, 0.15)'}`,
                padding: '6px 10px',
                borderRadius: '6px',
                position: 'relative'
              }}
            >
              <div style={{
                fontFamily: 'var(--font-cyber)',
                fontSize: '0.55rem',
                color: msg.sender === 'user' ? 'var(--color-cyan)' : 'var(--color-purple)',
                display: 'flex',
                justifyContent: 'space-between',
                gap: '10px',
                marginBottom: '3px'
              }}>
                <span>{msg.sender === 'user' ? 'OPERATOR' : 'TSKY-1'}</span>
                <span style={{ opacity: 0.5 }}>{msg.time}</span>
              </div>
              <div style={{ fontSize: '0.75rem', lineHeight: '1.25', wordBreak: 'break-word', color: 'var(--color-text)' }}>
                {msg.text}
              </div>
            </div>
          ))}
          {isLoading && (
            <div style={{ alignSelf: 'flex-start', padding: '6px 10px', background: 'rgba(189, 0, 255, 0.05)', border: '1px solid rgba(189, 0, 255, 0.15)', borderRadius: '6px' }}>
              <div className="pulse" style={{ fontSize: '0.65rem', color: 'var(--color-purple)', fontFamily: 'var(--font-cyber)' }}>
                TSKY UPLINK THINKING...
              </div>
            </div>
          )}
        </div>

        {/* Suggestion Chips */}
        <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', marginBottom: '8px' }}>
          {suggestions.map((s, idx) => (
            <button
              key={idx}
              className="btn-cyber"
              style={{
                fontSize: '0.55rem',
                padding: '3px 6px',
                textTransform: 'none',
                borderColor: 'rgba(0,240,255,0.1)',
                background: 'rgba(0,0,0,0.2)'
              }}
              onClick={() => handleSend(s)}
              disabled={isLoading}
            >
              {s}
            </button>
          ))}
        </div>

        {/* Input area */}
        <div style={{ display: 'flex', gap: '8px' }}>
          <input 
            type="text" 
            className="input-cyber"
            placeholder="Query TSKY autopilot system..."
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSend();
            }}
            disabled={isLoading}
            style={{ flex: 1 }}
          />
          <button 
            className="btn-cyber"
            style={{ padding: '8px 14px' }}
            onClick={() => handleSend()}
            disabled={isLoading || !inputValue.trim()}
          >
            SEND
          </button>
        </div>

      </div>
    </div>
  );
}
