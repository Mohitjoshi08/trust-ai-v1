import { useNavigate, useLocation } from 'react-router-dom';
import { BrainCircuit, X, LayoutDashboard, Database, LogOut } from 'lucide-react';
import { auth } from '../firebase';

export function Sidebar({ open, setOpen }: { open: boolean, setOpen: (val: boolean) => void }) {
  const navigate = useNavigate();
  const location = useLocation();
  const path = location.pathname;

  const handleLogout = async () => {
    try {
      if (import.meta.env.VITE_DEMO_MODE !== 'true') {
        await auth.signOut();
      }
      navigate('/login');
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <>
      {open && (
        <div className="sidebar-backdrop" onClick={() => setOpen(false)} />
      )}
      <nav className={`sidebar ${open ? 'open' : ''}`}>
        <div className="sidebar-header">
          <div className="flex items-center gap-2">
            <div className="sidebar-logo">
              <BrainCircuit size={16} />
            </div>
            <div className="title-lg">Trace.ai</div>
          </div>
          <button className="btn-icon" onClick={() => setOpen(false)}>
            <X size={18} />
          </button>
        </div>
        
        <div className="flex flex-col gap-2 mt-4">
          <button 
            className={`nav-item ${path === '/' ? 'active' : ''}`} 
            onClick={() => { navigate('/'); setOpen(false); }} 
            style={{ width: '100%', textAlign: 'left', background: path === '/' ? 'var(--surface-container)' : 'transparent' }}
          >
            <LayoutDashboard size={16} /> Dashboard
          </button>
          
          <button 
            className={`nav-item ${path === '/upload' ? 'active' : ''}`} 
            onClick={() => { navigate('/upload'); setOpen(false); }} 
            style={{ width: '100%', textAlign: 'left', background: path === '/upload' ? 'var(--surface-container)' : 'transparent' }}
          >
            <Database size={16} /> Data Sources
          </button>
        </div>
        
        <div style={{ marginTop: 'auto', display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <button 
            className="nav-item text-muted hover:text-error" 
            onClick={handleLogout} 
            style={{ width: '100%', textAlign: 'left', background: 'transparent' }}
          >
            <LogOut size={16} /> Log Out
          </button>
        </div>
      </nav>
    </>
  );
}
