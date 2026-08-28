import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { onAuthStateChanged } from 'firebase/auth';
import type { User } from 'firebase/auth';
import { auth } from './firebase';
import Dashboard from './pages/Dashboard';
import Login from './pages/Login';
import SignUp from './pages/SignUp';
import Upload from './pages/Upload';
import Integrations from './pages/Integrations';
import ConnectIntegration from './pages/ConnectIntegration';

const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === 'true';

// Auth Guard Component — bypassed in demo mode
function RequireAuth({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(!DEMO_MODE);

  useEffect(() => {
    if (DEMO_MODE) return;
    const unsubscribe = onAuthStateChanged(auth, (currentUser) => {
      setUser(currentUser);
      setLoading(false);
    });
    return unsubscribe;
  }, []);

  if (DEMO_MODE) {
    return children;
  }

  if (loading) {
    return <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>Loading...</div>;
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return children;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<SignUp />} />
        
        <Route 
          path="/" 
          element={
            <RequireAuth>
              <Dashboard />
            </RequireAuth>
          } 
        />
        
        <Route 
          path="/upload" 
          element={
            <RequireAuth>
              <Upload />
            </RequireAuth>
          } 
        />

        <Route 
          path="/integrations" 
          element={
            <RequireAuth>
              <Integrations />
            </RequireAuth>
          } 
        />

        <Route 
          path="/integrations/connect" 
          element={
            <RequireAuth>
              <ConnectIntegration />
            </RequireAuth>
          } 
        />
      </Routes>
    </BrowserRouter>
  );
}
