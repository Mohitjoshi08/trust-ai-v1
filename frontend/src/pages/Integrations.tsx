import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

interface Integration {
  id: string;
  platform: string;
  display_name: string;
  status: string;
}

export default function Integrations() {
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const navigate = useNavigate();

  useEffect(() => {
    // Fetch connected integrations
    fetch('/api/v1/integrations')
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) {
          setIntegrations(data);
        }
      })
      .catch(console.error);
  }, []);

  return (
    <div style={{ padding: '2rem' }}>
      <h1>Integrations</h1>
      <button 
        onClick={() => navigate('/integrations/connect')}
        style={{ padding: '0.5rem 1rem', background: '#0070f3', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', marginBottom: '2rem' }}
      >
        Add New Integration
      </button>

      <div>
        <h2>Connected Platforms</h2>
        {integrations.length === 0 ? (
          <p>No integrations connected yet.</p>
        ) : (
          <ul style={{ listStyle: 'none', padding: 0 }}>
            {integrations.map(integration => (
              <li key={integration.id} style={{ border: '1px solid #ddd', padding: '1rem', marginBottom: '1rem', borderRadius: '8px' }}>
                <h3>{integration.display_name} ({integration.platform})</h3>
                <p>Status: {integration.status}</p>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
