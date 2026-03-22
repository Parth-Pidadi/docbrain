import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { login, register, getMe } from '../api/client';
import toast from 'react-hot-toast';
import './Auth.css';

export default function Auth() {
  const [tab, setTab] = useState('login');
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({ email: '', password: '', full_name: '' });
  const { setUser, saveToken } = useAuth();
  const navigate = useNavigate();

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const { data } = await login(form.email, form.password);
      saveToken(data.access_token);
      const me = await getMe();
      setUser(me.data);
      toast.success('Welcome back!');
      navigate('/dashboard');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await register(form.email, form.password, form.full_name);
      // Auto-login after register
      const { data } = await login(form.email, form.password);
      saveToken(data.access_token);
      const me = await getMe();
      setUser(me.data);
      toast.success('Account created!');
      navigate('/dashboard');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Registration failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      {/* Left panel */}
      <div className="auth-left">
        <div className="auth-brand">
          <span className="auth-brand-mark">◈</span>
          <span className="auth-brand-name">DocBrain</span>
        </div>
        <div className="auth-headline">
          <h1><span>Upload.</span><br />Extract.<br />Ask Anything.</h1>
          <p>Turn unstructured documents into structured intelligence. Invoices, contracts, receipts — processed in seconds.</p>
        </div>
        <div className="auth-features">
          {[
            ['⬡', 'OCR-free document parsing with Donut AI'],
            ['◎', 'Natural language Q&A over your documents'],
            ['▦', 'Spending insights & financial analytics'],
          ].map(([icon, text]) => (
            <div key={text} className="auth-feature">
              <span className="af-icon">{icon}</span>
              <span>{text}</span>
            </div>
          ))}
        </div>
        <div className="auth-grid-bg" aria-hidden="true">
          {Array.from({ length: 12 }).map((_, i) => (
            <div key={i} className="grid-doc" style={{ animationDelay: `${i * 0.4}s` }} />
          ))}
        </div>
      </div>

      {/* Right panel */}
      <div className="auth-right">
        <div className="auth-card fade-up">
          <div className="auth-tabs">
            <button
              className={`auth-tab ${tab === 'login' ? 'active' : ''}`}
              onClick={() => setTab('login')}
            >
              Sign In
            </button>
            <button
              className={`auth-tab ${tab === 'register' ? 'active' : ''}`}
              onClick={() => setTab('register')}
            >
              Create Account
            </button>
          </div>

          {tab === 'login' ? (
            <form className="auth-form" onSubmit={handleLogin}>
              <div className="field">
                <label>Email</label>
                <input className="input" type="email" placeholder="you@company.com"
                  value={form.email} onChange={set('email')} required />
              </div>
              <div className="field">
                <label>Password</label>
                <input className="input" type="password" placeholder="••••••••"
                  value={form.password} onChange={set('password')} required />
              </div>
              <button className="btn btn-primary btn-full" type="submit" disabled={loading}>
                {loading ? <><div className="spinner" /> Signing in…</> : 'Sign In →'}
              </button>
            </form>
          ) : (
            <form className="auth-form" onSubmit={handleRegister}>
              <div className="field">
                <label>Full Name</label>
                <input className="input" type="text" placeholder="Your full name"
                  value={form.full_name} onChange={set('full_name')} />
              </div>
              <div className="field">
                <label>Email</label>
                <input className="input" type="email" placeholder="you@company.com"
                  value={form.email} onChange={set('email')} required />
              </div>
              <div className="field">
                <label>Password</label>
                <input className="input" type="password" placeholder="min 8 characters"
                  value={form.password} onChange={set('password')} required minLength={8} />
              </div>
              <button className="btn btn-primary btn-full" type="submit" disabled={loading}>
                {loading ? <><div className="spinner" /> Creating account…</> : 'Create Account →'}
              </button>
            </form>
          )}

          <p className="auth-footer-note">
            Your documents are private and isolated to your account.
          </p>
        </div>
      </div>
    </div>
  );
}
