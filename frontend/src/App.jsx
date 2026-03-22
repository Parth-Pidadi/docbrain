import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { AuthProvider } from './contexts/AuthContext';
import PrivateRoute from './components/PrivateRoute';
import Auth from './pages/Auth';
import Dashboard from './pages/Dashboard';
import QA from './pages/QA';
import Insights from './pages/Insights';
import './App.css';

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Toaster
          position="top-right"
          toastOptions={{
            style: {
              background: '#1E1D1A',
              color: '#F0EDE4',
              border: '1px solid rgba(255,184,0,0.15)',
              fontFamily: 'Outfit, sans-serif',
              fontSize: '0.88rem',
            },
            success: { iconTheme: { primary: '#4ADE80', secondary: '#1E1D1A' } },
            error:   { iconTheme: { primary: '#FF5555', secondary: '#1E1D1A' } },
          }}
        />
        <Routes>
          <Route path="/auth"      element={<Auth />} />
          <Route path="/dashboard" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
          <Route path="/qa"        element={<PrivateRoute><QA /></PrivateRoute>} />
          <Route path="/insights"  element={<PrivateRoute><Insights /></PrivateRoute>} />
          <Route path="*"          element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
