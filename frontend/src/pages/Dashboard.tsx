import React, { useState, useEffect, useCallback } from 'react';
import { apiClient, type DashboardStats, type ChartData } from '../api';
import {
  BarChart, Bar, PieChart, Pie, Cell, LineChart, Line,
  XAxis, YAxis, Tooltip, ResponsiveContainer, Legend
} from 'recharts';

const PRIORITY_COLORS: Record<string, string> = {
  P1: '#ef4444', P2: '#f97316', P3: '#eab308', P4: '#22c55e',
};

const STATUS_COLORS: Record<string, string> = {
  open: '#4f7fff', in_progress: '#8b5cf6', escalated: '#f97316',
  resolved: '#10b981', closed: '#6b7280', reopened: '#f43f5e',
};

const CATEGORY_COLORS = [
  '#4f7fff', '#8b5cf6', '#06b6d4', '#10b981', '#f59e0b',
  '#ef4444', '#ec4899', '#3b82f6', '#14b8a6', '#f97316',
];

interface TooltipPayloadItem {
  name: string;
  value: string | number;
  color?: string;
  fill?: string;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: TooltipPayloadItem[];
  label?: string;
}

const CustomTooltip = ({ active, payload, label }: CustomTooltipProps) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: 'var(--bg-elevated)', border: '1px solid var(--border)',
      borderRadius: 8, padding: '10px 14px', fontSize: 12,
    }}>
      <p style={{ color: 'var(--text-muted)', marginBottom: 6 }}>{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color || p.fill }}>{p.name}: <strong>{p.value}</strong></p>
      ))}
    </div>
  );
};

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [charts, setCharts] = useState<ChartData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [generateMsg, setGenerateMsg] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [statsRes, chartsRes] = await Promise.allSettled([
        apiClient.getDashboardStats(),
        apiClient.getDashboardCharts(),
      ]);

      if (statsRes.status === 'fulfilled') {
        setStats(statsRes.value.data);
      }
      if (chartsRes.status === 'fulfilled') {
        setCharts(chartsRes.value.data);
      }

      if (statsRes.status === 'rejected' && chartsRes.status === 'rejected') {
        const err = statsRes.reason;
        const msg = err && typeof err === 'object' && 'message' in err ? String((err as { message: unknown }).message) : '';
        if (msg.toLowerCase().includes('timeout') || msg.toLowerCase().includes('network')) {
          setError('Backend is waking up (Render free tier cold start) or request timed out. Please retry.');
        } else {
          setError(msg || 'Failed to load dashboard data');
        }
      } else if (statsRes.status === 'rejected') {
        setError('Failed to load dashboard summary statistics.');
      } else if (chartsRes.status === 'rejected') {
        setError('Failed to load dashboard charts.');
      }
    } catch (err: unknown) {
      const msg = err && typeof err === 'object' && 'message' in err ? String((err as { message: unknown }).message) : '';
      if (msg.toLowerCase().includes('timeout') || msg.toLowerCase().includes('network')) {
        setError('Backend is waking up (Render free tier cold start) or request timed out. Please retry.');
      } else {
        setError(msg || 'Failed to load dashboard data');
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleGenerate = async (scale: 'starter' | 'full') => {
    setGenerating(true);
    setGenerateMsg(null);
    try {
      const res = await apiClient.generateData({ scale, seed: 20261022, clear_existing: true, export_baseline: true });
      setGenerateMsg(`✅ Generated ${res.data.counts.complaints || 0} complaints in ${res.data.duration_seconds.toFixed(1)}s (scale: ${scale})`);
      await fetchData();
    } catch (err: unknown) {
      const detail = err && typeof err === 'object'
        ? ((err as { response?: { data?: { detail?: string } }; message?: string }).response?.data?.detail || (err as { message?: string }).message)
        : String(err);
      setGenerateMsg(`❌ Generation failed: ${detail || 'Unknown error'}`);
    } finally {
      setGenerating(false);
    }
  };

  if (loading) return (
    <div className="loading-spinner">
      <div className="spinner" />
      Loading dashboard…
    </div>
  );

  const isEmpty = !stats || stats.total_complaints === 0;

  return (
    <div>
      {/* Generate Banner */}
      {isEmpty && (
        <div className="generate-banner">
          <div className="generate-banner-text">
            <h3>🚀 No data yet — generate synthetic dataset</h3>
            <p>Choose a scale to populate the platform with realistic complaint data (seed: 20261022)</p>
          </div>
          <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
            <button className="btn btn-secondary" onClick={() => handleGenerate('starter')} disabled={generating}>
              {generating ? '⏳ Generating…' : 'Starter (~50)'}
            </button>
            <button className="btn btn-primary" onClick={() => handleGenerate('full')} disabled={generating}>
              {generating ? '⏳ Generating…' : 'Full (2,000)'}
            </button>
          </div>
        </div>
      )}

      {generateMsg && (
        <div className={`alert ${generateMsg.startsWith('✅') ? 'alert-success' : 'alert-error'}`} style={{ marginBottom: 16 }}>
          {generateMsg}
        </div>
      )}

      {error && (
        <div className="alert alert-error">⚠️ {error} — <button onClick={fetchData} style={{ textDecoration: 'underline' }}>retry</button></div>
      )}

      {/* KPI Cards */}
      {stats && (
        <>
          <div className="grid-4">
            <StatCard
              label="Total Complaints"
              value={stats.total_complaints.toLocaleString()}
              icon="📋"
              accent="#4f7fff"
              change={`${stats.open_complaints} open`}
            />
            <StatCard
              label="Safety Incidents"
              value={stats.safety_incidents}
              icon="🚨"
              accent="#ef4444"
              change={stats.safety_incidents > 0 ? 'Requires immediate attention' : 'No active safety issues'}
              changeClass={stats.safety_incidents > 0 ? 'negative' : 'positive'}
            />
            <StatCard
              label="SLA Breached"
              value={stats.sla_breached_count}
              icon="⏰"
              accent="#f97316"
              change={`${stats.sla_compliance_rate.toFixed(1)}% compliance rate`}
              changeClass={stats.sla_compliance_rate >= 90 ? 'positive' : 'warning'}
            />
            <StatCard
              label="Avg Resolution"
              value={`${stats.avg_resolution_time_hours.toFixed(1)}h`}
              icon="⚡"
              accent="#10b981"
              change={`CSAT: ${stats.csat_average.toFixed(1)}/5`}
              changeClass="positive"
            />
          </div>

          <div className="grid-4" style={{ marginBottom: 24 }}>
            <StatCard
              label="Open Complaints"
              value={stats.open_complaints}
              icon="📂"
              accent="#4f7fff"
              change="Awaiting action"
            />
            <StatCard
              label="Escalated"
              value={stats.escalated_complaints}
              icon="🔺"
              accent="#f97316"
              change={stats.escalated_complaints > 0 ? 'Needs attention' : 'None escalated'}
              changeClass={stats.escalated_complaints > 0 ? 'warning' : 'positive'}
            />
            <StatCard
              label="Resolved"
              value={stats.resolved_complaints}
              icon="✅"
              accent="#10b981"
              change={`${stats.closed_complaints} closed`}
              changeClass="positive"
            />
            <StatCard
              label="Avg CSAT Rating"
              value={`${stats.csat_average.toFixed(1)} ★`}
              icon="⭐"
              accent="#eab308"
              change="Customer satisfaction"
              changeClass={stats.csat_average >= 4 ? 'positive' : 'warning'}
            />
          </div>
        </>
      )}

      {/* Charts Row */}
      {charts && (
        <>
          <div className="grid-2">
            {/* Category Breakdown */}
            <div className="card">
              <div className="card-header">
                <div>
                  <div className="card-title">📊 Category Breakdown</div>
                  <div className="card-subtitle">Complaints by type</div>
                </div>
              </div>
              <div className="card-body">
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={charts.category_breakdown} margin={{ left: -20 }}>
                    <XAxis dataKey="name" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} angle={-30} textAnchor="end" height={60} />
                    <YAxis tick={{ fontSize: 11, fill: 'var(--text-muted)' }} />
                    <Tooltip content={<CustomTooltip />} />
                    <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                      {charts.category_breakdown.map((_, i) => (
                        <Cell key={i} fill={CATEGORY_COLORS[i % CATEGORY_COLORS.length]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Priority Distribution */}
            <div className="card">
              <div className="card-header">
                <div>
                  <div className="card-title">🎯 Priority Distribution</div>
                  <div className="card-subtitle">P1 (Critical) to P4 (Low)</div>
                </div>
              </div>
              <div className="card-body">
                <ResponsiveContainer width="100%" height={260}>
                  <PieChart>
                    <Pie
                      data={charts.priority_breakdown}
                      cx="50%"
                      cy="50%"
                      innerRadius={65}
                      outerRadius={105}
                      paddingAngle={3}
                      dataKey="value"
                    >
                      {charts.priority_breakdown.map((entry, i) => (
                        <Cell key={i} fill={PRIORITY_COLORS[entry.code] || '#4f7fff'} />
                      ))}
                    </Pie>
                    <Tooltip content={<CustomTooltip />} />
                    <Legend
                      formatter={(value: string) => <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{value}</span>}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {/* Volume Trend */}
          <div className="card" style={{ marginBottom: 24 }}>
            <div className="card-header">
              <div>
                <div className="card-title">📈 30-Day Complaint Volume</div>
                <div className="card-subtitle">Daily intake trend</div>
              </div>
              <button className="btn btn-secondary btn-sm" onClick={fetchData}>↻ Refresh</button>
            </div>
            <div className="card-body">
              <ResponsiveContainer width="100%" height={180}>
                <LineChart data={charts.daily_trends} margin={{ left: -20 }}>
                  <XAxis dataKey="date" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} />
                  <YAxis tick={{ fontSize: 11, fill: 'var(--text-muted)' }} />
                  <Tooltip content={<CustomTooltip />} />
                  <Line
                    type="monotone"
                    dataKey="count"
                    stroke="var(--accent-primary)"
                    strokeWidth={2}
                    dot={false}
                    name="Complaints"
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* SLA Table */}
          <div className="card" style={{ marginBottom: 24 }}>
            <div className="card-header">
              <div>
                <div className="card-title">⏱️ SLA Compliance by Priority</div>
                <div className="card-subtitle">Resolution time tracking against thresholds</div>
              </div>
            </div>
            <div className="table-wrapper">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Priority</th>
                    <th>Total</th>
                    <th>Breached</th>
                    <th>Compliance</th>
                    <th>SLA Bar</th>
                  </tr>
                </thead>
                <tbody>
                  {charts.sla_stats.map((row) => (
                    <tr key={row.priority}>
                      <td><span className={`badge badge-${row.priority.toLowerCase()}`}>{row.priority}</span></td>
                      <td style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{row.total}</td>
                      <td style={{ color: row.breached > 0 ? 'var(--p1)' : 'var(--text-muted)' }}>{row.breached}</td>
                      <td>
                        <span style={{ color: row.compliance_pct >= 90 ? 'var(--accent-emerald)' : row.compliance_pct >= 75 ? 'var(--accent-amber)' : 'var(--p1)', fontWeight: 600 }}>
                          {row.compliance_pct.toFixed(1)}%
                        </span>
                      </td>
                      <td style={{ width: 160 }}>
                        <div style={{ background: 'var(--border)', borderRadius: 4, height: 8, overflow: 'hidden' }}>
                          <div style={{
                            height: '100%',
                            width: `${row.compliance_pct}%`,
                            background: row.compliance_pct >= 90 ? 'var(--accent-emerald)' : row.compliance_pct >= 75 ? 'var(--accent-amber)' : 'var(--p1)',
                            borderRadius: 4,
                            transition: 'width 0.8s ease',
                          }} />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Status Breakdown */}
          {charts.status_breakdown.length > 0 && (
            <div className="card" style={{ marginBottom: 24 }}>
              <div className="card-header">
                <div className="card-title">🔄 Status Distribution</div>
              </div>
              <div className="card-body" style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
                {charts.status_breakdown.map((item) => (
                  <div key={item.code} style={{
                    background: 'var(--bg-elevated)', border: '1px solid var(--border)',
                    borderRadius: 8, padding: '10px 16px', minWidth: 100, textAlign: 'center',
                  }}>
                    <div style={{ fontSize: 22, fontWeight: 800, color: STATUS_COLORS[item.code] || 'var(--text-primary)' }}>
                      {item.value}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4, textTransform: 'capitalize' }}>
                      {item.name.replace('_', ' ')}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {isEmpty && !loading && !error && (
        <div className="empty-state">
          <div className="empty-state-icon">📊</div>
          <h3>Dashboard Ready</h3>
          <p>Generate a dataset using the button above to populate charts and KPIs.</p>
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, icon, accent, change, changeClass }: {
  label: string; value: string | number; icon: string;
  accent: string; change?: string; changeClass?: string;
}) {
  return (
    <div className="stat-card" style={{ '--stat-accent': accent, '--stat-icon-bg': `${accent}20` } as React.CSSProperties}>
      <div className="stat-card-header">
        <div className="stat-card-label">{label}</div>
        <div className="stat-card-icon">{icon}</div>
      </div>
      <div className="stat-card-value">{value}</div>
      {change && <div className={`stat-card-change ${changeClass || ''}`}>{change}</div>}
    </div>
  );
}
