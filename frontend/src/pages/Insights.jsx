import { useState, useEffect } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  PieChart, Pie, Legend,
} from 'recharts';
import { getSpending, getVendors, getInsightsSummary } from '../api/client';
import toast from 'react-hot-toast';
import Layout from '../components/Layout';
import './Insights.css';

const COLORS = ['#FFB800', '#4ADE80', '#60A5FA', '#FBBF24', '#F472B6', '#A78BFA'];

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tooltip">
      {label && <p className="ct-label">{label}</p>}
      <p className="ct-value">${payload[0].value?.toFixed(2)}</p>
    </div>
  );
};

export default function Insights() {
  const [summary, setSummary] = useState(null);
  const [spending, setSpending] = useState(null);
  const [vendors, setVendors] = useState([]);
  const [month, setMonth] = useState('');
  const [loading, setLoading] = useState(true);

  const fetchAll = async (monthFilter = '') => {
    setLoading(true);
    try {
      const [sumRes, spendRes, vendRes] = await Promise.all([
        getInsightsSummary(),
        getSpending(monthFilter ? { month: monthFilter } : {}),
        getVendors(),
      ]);
      setSummary(sumRes.data);
      setSpending(spendRes.data);
      setVendors(vendRes.data.vendors || []);
    } catch (err) {
      toast.error('Failed to load insights');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchAll(); }, []);

  const handleMonthFilter = (e) => {
    const val = e.target.value;
    setMonth(val);
    fetchAll(val);
  };

  const pieData = Object.entries(summary?.by_type || {}).map(([name, value]) => ({ name: name.replace('_', ' '), value }));
  const vendorData = (spending?.vendor_breakdown || []).slice(0, 8).map((v) => ({ name: v.vendor, value: v.total }));

  return (
    <Layout>
      <div className="insights-page fade-up">
        <div className="insights-header">
          <div>
            <h1>Insights</h1>
            <p>SQL-powered analytics across your documents</p>
          </div>
          <input
            className="input month-filter"
            type="month"
            value={month}
            onChange={handleMonthFilter}
            title="Filter by month"
          />
        </div>

        {loading ? (
          <div className="insights-loading">
            <div className="spinner spinner-lg" />
            <p>Loading insights…</p>
          </div>
        ) : (
          <>
            {/* KPI cards */}
            <div className="kpi-row">
              <div className="kpi-card">
                <span className="kpi-label">Total Spent</span>
                <span className="kpi-value accent">${spending?.total?.toFixed(2) || '0.00'}</span>
                <span className="kpi-sub">{spending?.record_count || 0} documents</span>
              </div>
              <div className="kpi-card">
                <span className="kpi-label">Documents</span>
                <span className="kpi-value">{summary?.total_documents || 0}</span>
                <span className="kpi-sub">total processed</span>
              </div>
              <div className="kpi-card">
                <span className="kpi-label">Vendors</span>
                <span className="kpi-value">{vendors.length}</span>
                <span className="kpi-sub">unique vendors</span>
              </div>
              <div className="kpi-card">
                <span className="kpi-label">Top Vendor</span>
                <span className="kpi-value vendor-val">{vendors[0]?.vendor || '—'}</span>
                <span className="kpi-sub">${vendors[0]?.total_spent?.toFixed(2) || '0'} spent</span>
              </div>
            </div>

            <div className="charts-grid">
              {/* Vendor bar chart */}
              <div className="chart-card">
                <h3>Spending by Vendor</h3>
                {vendorData.length === 0 ? (
                  <div className="empty-state"><div className="es-icon">▦</div><p>No spending data yet</p></div>
                ) : (
                  <ResponsiveContainer width="100%" height={260}>
                    <BarChart data={vendorData} margin={{ top: 8, right: 8, left: 8, bottom: 40 }}>
                      <XAxis
                        dataKey="name"
                        tick={{ fill: 'var(--text-3)', fontSize: 11, fontFamily: 'Outfit' }}
                        angle={-30}
                        textAnchor="end"
                        interval={0}
                        axisLine={false}
                        tickLine={false}
                      />
                      <YAxis
                        tick={{ fill: 'var(--text-3)', fontSize: 11 }}
                        axisLine={false}
                        tickLine={false}
                        tickFormatter={(v) => `$${v}`}
                      />
                      <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,184,0,0.06)' }} />
                      <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                        {vendorData.map((_, i) => (
                          <Cell key={i} fill={i === 0 ? 'var(--accent)' : '#2C2B27'} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </div>

              {/* Pie chart — doc types */}
              <div className="chart-card">
                <h3>Document Types</h3>
                {pieData.length === 0 ? (
                  <div className="empty-state"><div className="es-icon">◎</div><p>No documents yet</p></div>
                ) : (
                  <ResponsiveContainer width="100%" height={260}>
                    <PieChart>
                      <Pie
                        data={pieData}
                        cx="50%" cy="45%"
                        outerRadius={90}
                        innerRadius={50}
                        dataKey="value"
                        paddingAngle={3}
                      >
                        {pieData.map((_, i) => (
                          <Cell key={i} fill={COLORS[i % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip content={<CustomTooltip />} />
                      <Legend
                        formatter={(val) => <span style={{ color: 'var(--text-2)', fontSize: '0.8rem' }}>{val}</span>}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                )}
              </div>
            </div>

            {/* Records table */}
            {spending?.records?.length > 0 && (
              <div className="records-card">
                <h3>Transaction Records</h3>
                <div className="records-table-wrap">
                  <table className="records-table">
                    <thead>
                      <tr>
                        <th>Vendor</th>
                        <th>Type</th>
                        <th>Date</th>
                        <th>Amount</th>
                        <th>File</th>
                      </tr>
                    </thead>
                    <tbody>
                      {spending.records.map((r, i) => (
                        <tr key={i}>
                          <td className="td-vendor">{r.vendor}</td>
                          <td><span className={`badge badge-${r.doc_type}`}>{r.doc_type?.replace('_', ' ')}</span></td>
                          <td className="td-date mono">{r.date || '—'}</td>
                          <td className="td-amount accent">${r.amount?.toFixed(2)}</td>
                          <td className="td-file text-muted">{r.filename}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </Layout>
  );
}
