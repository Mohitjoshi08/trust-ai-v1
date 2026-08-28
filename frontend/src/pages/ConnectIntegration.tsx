import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

export default function ConnectIntegration() {
  const [step, setStep] = useState(1);
  const [platforms, setPlatforms] = useState<any[]>([]);
  const [selectedPlatform, setSelectedPlatform] = useState<any>(null);
  const [credentials, setCredentials] = useState<any>({});
  const [integrationId, setIntegrationId] = useState<string>('');
  const [mapping, setMapping] = useState<any>(null);
  const navigate = useNavigate();

  useEffect(() => {
    fetch('/api/v1/integrations/available')
      .then(res => res.json())
      .then(data => setPlatforms(data))
      .catch(console.error);
  }, []);

  const handleConnect = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await fetch('/api/v1/integrations/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          platform: selectedPlatform.platform,
          display_name: selectedPlatform.display_name,
          credentials
        })
      });
      if (res.ok) {
        const data = await res.json();
        setIntegrationId(data.id);
        setStep(2);
      } else {
        alert('Failed to connect. Check credentials.');
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleAutoMap = async () => {
    try {
      const res = await fetch(`/api/v1/integrations/${integrationId}/auto-map`, {
        method: 'POST'
      });
      if (res.ok) {
        const data = await res.json();
        setMapping(data.mapping);
        setStep(3);
      } else {
        alert('Failed to auto-map schema.');
      }
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div style={{ padding: '2rem', maxWidth: '600px', margin: '0 auto' }}>
      <h1>Connect Integration</h1>
      
      {step === 1 && (
        <div>
          <h2>Step 1: Credentials</h2>
          {!selectedPlatform ? (
            <div>
              <h3>Select a Platform</h3>
              <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                {platforms.map(p => (
                  <div 
                    key={p.platform} 
                    onClick={() => setSelectedPlatform(p)}
                    style={{ border: '1px solid #ddd', padding: '1rem', borderRadius: '8px', cursor: 'pointer', width: '200px' }}
                  >
                    <h4>{p.display_name}</h4>
                    <p>{p.description}</p>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <form onSubmit={handleConnect}>
              <h3>{selectedPlatform.display_name}</h3>
              {selectedPlatform.required_fields.map((field: any) => (
                <div key={field.name} style={{ marginBottom: '1rem' }}>
                  <label style={{ display: 'block', marginBottom: '0.5rem' }}>{field.label}</label>
                  <input 
                    type={field.type === 'password' ? 'password' : 'text'} 
                    required 
                    onChange={e => setCredentials({...credentials, [field.name]: e.target.value})}
                    style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #ccc' }}
                  />
                </div>
              ))}
              <div style={{ display: 'flex', gap: '1rem' }}>
                <button type="button" onClick={() => setSelectedPlatform(null)} style={{ padding: '0.5rem 1rem' }}>Back</button>
                <button type="submit" style={{ background: '#0070f3', color: 'white', border: 'none', padding: '0.5rem 1rem', borderRadius: '4px', cursor: 'pointer' }}>Connect</button>
              </div>
            </form>
          )}
        </div>
      )}

      {step === 2 && (
        <div>
          <h2>Step 2: AI Auto-Map</h2>
          <p>Connection successful! Let our AI automatically map your source schema to Trace.ai metrics.</p>
          <button 
            onClick={handleAutoMap}
            style={{ background: '#0070f3', color: 'white', border: 'none', padding: '0.5rem 1rem', borderRadius: '4px', cursor: 'pointer' }}
          >
            Auto-Map Schema
          </button>
        </div>
      )}

      {step === 3 && (
        <div>
          <h2>Step 3: Success!</h2>
          <p>Your integration is ready to sync.</p>
          <div style={{ background: '#f5f5f5', padding: '1rem', borderRadius: '8px', marginBottom: '2rem' }}>
            <h4>Detected Mapping</h4>
            <pre>{JSON.stringify(mapping, null, 2)}</pre>
          </div>
          <button 
            onClick={() => navigate('/integrations')}
            style={{ background: '#0070f3', color: 'white', border: 'none', padding: '0.5rem 1rem', borderRadius: '4px', cursor: 'pointer' }}
          >
            Go to Integrations
          </button>
        </div>
      )}
    </div>
  );
}
