import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { login, register, getMe } from '../api/client';
import toast from 'react-hot-toast';
import './Auth.css';

function PasswordInput({ value, onChange, placeholder, id }) {
  const [show, setShow] = useState(false);
  return (
    <div className="password-wrap">
      <input
        id={id}
        className="input"
        type={show ? 'text' : 'password'}
        placeholder={placeholder}
        value={value}
        onChange={onChange}
        required
        minLength={8}
      />
      <button type="button" className="pw-toggle" onClick={() => setShow(s => !s)} tabIndex={-1}>
        {show ? '🙈' : '👁'}
      </button>
    </div>
  );
}

export default function Auth() {
  const [tab, setTab] = useState('login');
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({ email: '', password: '', confirm: '', full_name: '' });
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
    if (form.password !== form.confirm) {
      toast.error('Passwords do not match');
      return;
    }
    setLoading(true);
    try {
      await register(form.email, form.password, form.full_name);
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
          <h1>
            <em>Upload.</em><br />
            Extract.<br />
            Ask Anything.
          </h1>
          <p>Turn unstructured documents into structured intelligence. Invoices, contracts, receipts — processed in seconds.</p>
        </div>
        <div className="auth-features">
          {[
            'OCR-free document parsing with Donut AI',
            'Natural language Q&A over your documents',
            'Spending insights & financial analytics',
          ].map((text) => (
            <div key={text} className="auth-feature">
              <span className="af-line" />
              <span>{text}</span>
            </div>
          ))}
        </div>
        <div className="auth-ledger-deco" aria-hidden="true">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="ld-row">
              <div className="ld-cell" style={{ animationDelay: `${i * 0.25}s`, width: `${50 + (i * 17 % 80)}px` }} />
              <div className="ld-cell" style={{ animationDelay: `${i * 0.25 + 0.1}s`, width: `${30 + (i * 13 % 50)}px` }} />
              <div className="ld-cell" style={{ animationDelay: `${i * 0.25 + 0.2}s`, width: `${20 + (i * 11 % 40)}px` }} />
            </div>
          ))}
        </div>
      </div>

      {/* Right panel */}
      <div className="auth-right">
        <div className="auth-card">
          <p className="auth-eyebrow">Document Intelligence</p>
          <h2 className="auth-card-title">
            {tab === 'login' ? 'Welcome back.' : 'Get started.'}
          </h2>

          <div className="auth-tabs">
            <button className={`auth-tab ${tab === 'login' ? 'active' : ''}`} onClick={() => setTab('login')}>
              Sign In
            </button>
            <button className={`auth-tab ${tab === 'register' ? 'active' : ''}`} onClick={() => setTab('register')}>
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
                <PasswordInput value={form.password} onChange={set('password')} placeholder="••••••••" id="login-pw" />
              </div>
              <button className="btn btn-primary btn-full" type="submit" disabled={loading}>
                {loading ? <><div className="spinner" /> Signing in…</> : 'Sign In →'}
              </button>
            </form>
          ) : (
            <form className="auth-form" onSubmit={handleRegister}>
              <div className="field">
                <label>Full Name</label>
                <input className="input" type="text" placeholder="Jane Smith"
                  value={form.full_name} onChange={set('full_name')} />
              </div>
              <div className="field">
                <label>Email</label>
                <input className="input" type="email" placeholder="you@company.com"
                  value={form.email} onChange={set('email')} required />
              </div>
              <div className="field">
                <label>Password</label>
                <PasswordInput value={form.password} onChange={set('password')} placeholder="min 8 characters" id="reg-pw" />
              </div>
              <div className="field">
                <label>Confirm Password</label>
                <PasswordInput value={form.confirm} onChange={set('confirm')} placeholder="repeat password" id="reg-pw2" />
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
