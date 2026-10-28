import { useState } from 'react';
import { apiClient, type ValidationReport } from '../api';

const STATUS_ICON: Record<string, string> = { pass: '✅', warn: '⚠️', fail: '❌' };
const STATUS_COLOR: Record<string, string> = {
  pass: 'var(--accent-emerald)',
  warn: 'var(--accent-amber)',
  fail: 'var(--p1)',
};
const STATUS_BADGE: Record<string, string> = {
  pass: 'badge-success', warn: 'badge-anomaly', fail: 'badge-p1',
};

function formatSeconds(s: number) {
  return s < 1 ? `${(s * 1000).toFixed(0)}ms` : `${s.toFixed(2)}s`;
}

export default function Validation() {
  const [report, setReport] = useState<ValidationReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<'all' | 'pass' | 'warn' | 'fail'>('all');
  const [categoryFilter, setCategoryFilter] = useState('');

  const runValidation = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient.getValidation();
      setReport(res.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Validation failed');
    } finally {
      setLoading(false);
    }
  };

  const categories = [...new Set(report?.findings?.map(f => f.category) || [])];

  const filtered = report?.findings?.filter(f => {
    if (filter !== 'all' && f.status !== filter) return false;
    if (categoryFilter && f.category !== categoryFilter) return false;
    return true;
  }) || [];

  const summaryTotal = report ? report.summary.total : 0;
  const passedPct = report && summaryTotal > 0 ? ((report.summary.passed / summaryTotal) * 100).toFixed(0) : '0';

  return (
    <div>
      {/* Action Bar */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 20, alignItems: 'center' }}>
        <button
          id="run-validation-btn"
          className="btn btn-primary"
          onClick={runValidation}
          disabled={loading}
        >
          {loading ? '⏳ Running…' : '✅ Run Validation'}
        </button>
        {report && (
          <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>
            Last run: {new Date(report.generated_at).toLocaleString()} · {formatSeconds(report.summary.execution_time_seconds)}
          </span>
        )}
      </div>

      {error && <div className="alert alert-error">⚠️ {error}</div>}

      {loading && (
        <div className="loading-spinner"><div className="spinner" />Running validation checks…</div>
      )}

      {!report && !loading && (
        <div className="empty-state" style={{ paddingTop: 80 }}>
          <div className="empty-state-icon">🔬</div>
          <h3>No validation report yet</h3>
          <p>Click "Run Validation" to execute all schema, chronology, arithmetic, and business rule checks.</p>
        </div>
      )}

      {report && !loading && (
        <>
          {/* Summary Cards */}
          <div className="grid-4" style={{ marginBottom: 24 }}>
            <div className="stat-card" style={{ '--stat-accent': 'var(--accent-emerald)' } as React.CSSProperties}>
              <div className="stat-card-label">Passed</div>
              <div className="stat-card-value" style={{ color: 'var(--accent-emerald)' }}>{report.summary.passed}</div>
              <div className="stat-card-change positive">{passedPct}% pass rate</div>
            </div>
            <div className="stat-card" style={{ '--stat-accent': 'var(--accent-amber)' } as React.CSSProperties}>
              <div className="stat-card-label">Warnings</div>
              <div className="stat-card-value" style={{ color: report.summary.warned > 0 ? 'var(--accent-amber)' : 'var(--text-primary)' }}>
                {report.summary.warned}
              </div>
              <div className="stat-card-change warning">Require review</div>
            </div>
            <div className="stat-card" style={{ '--stat-accent': 'var(--p1)' } as React.CSSProperties}>
              <div className="stat-card-label">Failed</div>
              <div className="stat-card-value" style={{ color: report.summary.failed > 0 ? 'var(--p1)' : 'var(--text-primary)' }}>
                {report.summary.failed}
              </div>
              <div className="stat-card-change negative">Must be fixed</div>
            </div>
            <div className="stat-card" style={{ '--stat-accent': 'var(--accent-primary)' } as React.CSSProperties}>
              <div className="stat-card-label">Total Checks</div>
              <div className="stat-card-value">{report.summary.total}</div>
              <div className="stat-card-change">in {formatSeconds(report.summary.execution_time_seconds)}</div>
            </div>
          </div>

          {/* Category summary */}
          <div className="card" style={{ marginBottom: 24 }}>
            <div className="card-header">
              <div className="card-title">📊 Results by Category</div>
            </div>
            <div className="card-body">
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
                {categories.map(cat => {
                  const catFindings = report.findings.filter(f => f.category === cat);
                  const failed = catFindings.filter(f => f.status === 'fail').length;
                  const warned = catFindings.filter(f => f.status === 'warn').length;
                  const passed = catFindings.filter(f => f.status === 'pass').length;
                  return (
                    <div
                      key={cat}
                      onClick={() => setCategoryFilter(cat === categoryFilter ? '' : cat)}
                      style={{
                        background: cat === categoryFilter ? 'var(--accent-primary-glow)' : 'var(--bg-elevated)',
                        border: `1px solid ${cat === categoryFilter ? 'var(--accent-primary)' : 'var(--border)'}`,
                        borderRadius: 10, padding: '12px 16px', cursor: 'pointer', minWidth: 160,
                        transition: 'all 0.2s ease',
                      }}
                    >
                      <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8, textTransform: 'capitalize' }}>
                        {cat.replace(/_/g, ' ')}
                      </div>
                      <div style={{ display: 'flex', gap: 6 }}>
                        <span style={{ fontSize: 11, color: 'var(--accent-emerald)' }}>✅ {passed}</span>
                        {warned > 0 && <span style={{ fontSize: 11, color: 'var(--accent-amber)' }}>⚠️ {warned}</span>}
                        {failed > 0 && <span style={{ fontSize: 11, color: 'var(--p1)' }}>❌ {failed}</span>}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Filter Tabs */}
          <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
            {(['all', 'fail', 'warn', 'pass'] as const).map(f => (
              <button
                key={f}
                className={`btn ${filter === f ? 'btn-primary' : 'btn-secondary'} btn-sm`}
                onClick={() => setFilter(f)}
              >
                {f === 'all' ? `All (${report.summary.total})` :
                  f === 'fail' ? `❌ Failed (${report.summary.failed})` :
                    f === 'warn' ? `⚠️ Warnings (${report.summary.warned})` :
                      `✅ Passed (${report.summary.passed})`}
              </button>
            ))}
            {categoryFilter && (
              <button className="btn btn-secondary btn-sm" onClick={() => setCategoryFilter('')}>
                ✕ {categoryFilter.replace(/_/g, ' ')}
              </button>
            )}
          </div>

          {/* Findings Table */}
          <div className="card">
            <div className="card-header">
              <div className="card-title">🔍 Validation Findings</div>
              <div className="card-subtitle">{filtered.length} findings shown</div>
            </div>
            {!filtered.length ? (
              <div className="empty-state">
                <div className="empty-state-icon">✅</div>
                <h3>No findings match filter</h3>
              </div>
            ) : (
              <div className="table-wrapper">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Status</th>
                      <th>Category</th>
                      <th>Check</th>
                      <th>Message</th>
                      <th>Record</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((f, i) => (
                      <tr key={i}>
                        <td>
                          <span
                            className={`badge ${STATUS_BADGE[f.status]}`}
                            style={{ whiteSpace: 'nowrap' }}
                          >
                            {STATUS_ICON[f.status]} {f.status.toUpperCase()}
                          </span>
                        </td>
                        <td style={{ fontSize: 12, color: 'var(--text-muted)', textTransform: 'capitalize' }}>
                          {f.category?.replace(/_/g, ' ')}
                        </td>
                        <td style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-primary)', whiteSpace: 'nowrap' }}>
                          {f.check_name?.replace(/_/g, ' ')}
                        </td>
                        <td style={{ fontSize: 12, color: STATUS_COLOR[f.status] || 'var(--text-secondary)' }}>
                          {f.message}
                        </td>
                        <td>
                          {f.record_id && (
                            <span className="table-id">{f.record_id}</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
