import { useState } from 'react';
import { auth } from '../firebase';
import { signInWithEmailAndPassword } from 'firebase/auth';
import { useNavigate, Link } from 'react-router-dom';
import { BrainCircuit, AlertTriangle } from 'lucide-react';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    
    try {
      const userCredential = await signInWithEmailAndPassword(auth, email, password);
      if (!userCredential.user.emailVerified) {
        setError('Please verify your email before logging in.');
        await auth.signOut();
        setLoading(false);
        return;
      }
      navigate('/');
    } catch (err: any) {
      setError(err.message || 'Failed to login');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-layout" style={{ alignItems: 'center', justifyContent: 'center', width: '100%', minHeight: '100vh' }}>
      <div className="card" style={{ maxWidth: '400px', width: '100%', padding: '32px' }}>
        <div style={{ textAlign: 'center', marginBottom: '24px' }}>
          <BrainCircuit size={48} color="var(--primary)" style={{ margin: '0 auto 16px' }} />
          <h2 className="headline-md">Welcome Back</h2>
          <p className="text-muted body-md mt-2">Sign in to your Trace.ai account</p>
        </div>

        {error && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '12px', background: 'var(--error-container)', color: 'var(--on-error-container)', borderRadius: 'var(--radius-md)', marginBottom: '16px' }}>
            <AlertTriangle size={16} />
            <span className="label-md">{error}</span>
          </div>
        )}

        <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div>
            <label className="label-md">Email Address</label>
            <input 
              type="email" 
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              className="mt-1"
              style={{ width: '100%', padding: '10px', borderRadius: 'var(--radius-md)', border: '1px solid var(--outline)', background: 'var(--surface-container-lowest)', color: 'var(--on-surface)' }}
            />
          </div>
          <div>
            <label className="label-md">Password</label>
            <input 
              type="password" 
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              className="mt-1"
              style={{ width: '100%', padding: '10px', borderRadius: 'var(--radius-md)', border: '1px solid var(--outline)', background: 'var(--surface-container-lowest)', color: 'var(--on-surface)' }}
            />
          </div>
          <button type="submit" className="btn btn-primary mt-2" disabled={loading} style={{ justifyContent: 'center', padding: '12px' }}>
            {loading ? 'Signing In...' : 'Sign In'}
          </button>
        </form>

        <p className="body-md text-muted" style={{ textAlign: 'center', marginTop: '24px' }}>
          Don't have an account? <Link to="/signup" style={{ color: 'var(--primary)' }}>Sign Up</Link>
        </p>
      </div>
    </div>
  );
}
