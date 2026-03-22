import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
});

// Attach JWT token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('db_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Auto-logout on 401
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('db_token');
      window.location.href = '/auth';
    }
    return Promise.reject(err);
  }
);

// ── Auth ──
export const register = (email, password, full_name) =>
  api.post('/api/auth/register', { email, password, full_name });

export const login = (email, password) => {
  const form = new FormData();
  form.append('username', email);
  form.append('password', password);
  return api.post('/api/auth/login', form);
};

export const getMe = () => api.get('/api/auth/me');

// ── Documents ──
export const uploadDocument = (file) => {
  const form = new FormData();
  form.append('file', file);
  return api.post('/api/upload/', form);
};

export const extractDocument = (docId) => api.post(`/api/extract/${docId}`);

// ── Q&A ──
export const askQuestion = (question, doc_ids = null) =>
  api.post('/api/qa/', { question, doc_ids });

// ── Insights ──
export const getInsightsSummary = () => api.get('/api/insights/summary');
export const getSpending = (params = {}) => api.get('/api/insights/spending', { params });
export const getVendors = () => api.get('/api/insights/vendors');
export const getTransactions = (params = {}) => api.get('/api/insights/transactions', { params });

export default api;
