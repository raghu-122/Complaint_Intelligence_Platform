import { useState, useEffect } from 'react';
import { apiClient, type AnomalyDetectionResult } from '../api';

const SEVERITY_COLORS: Record<string, string> = {
  critical: 'var(--p1)', high: 'var(--p2)', medium: 'var(--p3)', low: 'var(--p4)',
};

const SEVERITY_BADGE: Record<string, string> = {
  critical: 'badge-p1', high: 'badge-p2', medium: 'badge-p3', low: 'badge-p4',
};

function MetricCard({ label, value, desc, accent }: { label: string; value: string | number; desc?: string; accent?: string }) {
  return (
    <div className="stat-card" style={{ '--stat-accent': accent || 'var(--accent-primary)' } as React.CSSProperties}>
      <div className="stat-card-label">{label}</div>
      <div className="stat-card-value" style={{ fontSize: 28 }}>{value}</div>
      {desc && <div className="stat-card-change">{desc}</div>}
    </div>
  );
}

function extractErrorMessage(err: unknown, fallback: string): string {
  if (err && typeof err === 'object') {
    const maybeAxios = err as { response?: { data?: { detail?: string } }; message?: string };
    return maybeAxios.response?.data?.detail || maybeAxios.message || fallback;
  }
  return fallback;
}

export default function Anomalies() {
  const [result, setResult] = useState<AnomalyDetectionResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [injecting, setInjecting] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [filter, setFilter] = useState('');

  const runDetection = async () => {
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const res = await apiClient.getAnomalies();
      setResult(res.data);
      setMessage(`✅ Detection complete: found ${res.data.detected_count} anomalies`);
    } catch (err: unknown) {
      setError(extractErrorMessage(err, 'Detection failed'));
    } finally {
      setLoading(false);
    }
  };

  const injectAnomalies = async () => {
    setInjecting(true);
    setError(null);
    try {
      const res = await apiClient.injectAnomalies(6);
      setMessage(res.data?.message || '✅ 6 anomalies injected. Re-running detection…');
      await runDetection();
    } catch (err: unknown) {
      setError(extractErrorMessage(err, 'Injection failed'));
    } finally {
      setInjecting(false);
    }
  };

  const resetAnomalies = async () => {
    setResetting(true);
    setError(null);
    try {
      await apiClient.resetAnomalies();
      setMessage('✅ Test anomalies reset to clean baseline. Re-running detection…');
      await runDetection();
    } catch (err: unknown) {
      setError(extractErrorMessage(err, 'Reset failed'));
    } finally {
      setResetting(false);
    }
  };

  useEffect(() => { runDetection(); }, []);

  const filteredAnomalies = result?.anomalies?.filter(a =>
    !filter || a.anomaly_type === filter || a.severity === filter
  ) || [];

  const anomalyTypes = [...new Set(result?.anomalies?.map(a => a.anomaly_type) || [])];

  return (
    <div>
      {/* Actions */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap' }}>
        <button
          id="run-detection-btn"
          className="btn btn-primary"
          onClick={runDetection}
          disabled={loading}
        >
          {loading ? '⏳ Running…' : '🔍 Run Detection'}
        </button>
        <button
          id="inject-anomalies-btn"
          className="btn btn-secondary"
          onClick={injectAnomalies}
          disabled={injecting}
          title="Inject test anomalies then re-run detection"
        >
          {injecting ? '⏳ Injecting…' : '💉 Inject Anomalies'}
        </button>
        <button
          id="reset-anomalies-btn"
          className="btn btn-secondary"
          onClick={resetAnomalies}
          disabled={resetting}
          title="Reset injected test anomalies and return to clean baseline"
        >
          {resetting ? '⏳ Resetting…' : '🔄 Reset Anomalies'}
        </button>
        {result && (
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
            <select
              className="filter-select"
              value={filter}
              onChange={e => setFilter(e.target.value)}
            >
              <option value="">All Types</option>
              {anomalyTypes.map(t => (
                <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>
              ))}
            </select>
          </div>
        )}
      </div>

      {message && (
        <div className={`alert ${message.startsWith('✅') ? 'alert-success' : 'alert-info'}`}>{message}</div>
      )}
      {error && <div className="alert alert-error">⚠️ {error}</div>}

      {loading && (
        <div className="loading-spinner"><div className="spinner" />Running anomaly detection…</div>
      )}

      {result && !loading && (
        <>
          {/* Metrics */}
          <div className="grid-4" style={{ marginBottom: 24 }}>
            <MetricCard
              label="Detected Anomalies"
              value={result.detected_count}
              desc="Total anomalies found"
              accent="var(--p2)"
            />
            <MetricCard
              label="Ground Truth"
              value={result.ground_truth_count}
              desc="Known anomaly records"
              accent="var(--accent-violet)"
            />
            <MetricCard
              label="Precision"
              value={result.ground_truth_count === 0 && result.detected_count === 0 ? 'N/A' : `${(result.precision * 100).toFixed(1)}%`}
              desc={result.ground_truth_count === 0 && result.detected_count === 0 ? 'Clean baseline (no ground truth)' : 'Positive predictive value'}
              accent={result.precision >= 0.8 ? 'var(--accent-emerald)' : 'var(--accent-amber)'}
            />
            <MetricCard
              label="F1 Score"
              value={result.ground_truth_count === 0 && result.detected_count === 0 ? 'N/A' : result.f1_score.toFixed(3)}
              desc={result.ground_truth_count === 0 && result.detected_count === 0 ? 'Clean baseline (no ground truth)' : `Recall: ${(result.recall * 100).toFixed(1)}%`}
              accent={result.f1_score >= 0.7 ? 'var(--accent-emerald)' : 'var(--p2)'}
            />
          </div>

          {/* Confusion Matrix Visual */}
          <div className="card" style={{ marginBottom: 24 }}>
            <div className="card-header">
              <div className="card-title">📊 Detection Performance</div>
              <div className="card-subtitle">Precision / Recall / F1</div>
            </div>
            <div className="card-body">
              <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', alignItems: 'flex-end' }}>
                {[
                  { label: 'Precision', value: result.precision, color: 'var(--accent-primary)' },
                  { label: 'Recall', value: result.recall, color: 'var(--accent-emerald)' },
                  { label: 'F1 Score', value: result.f1_score, color: 'var(--accent-violet)' },
                ].map(({ label, value, color }) => (
                  <div key={label} style={{ flex: 1, minWidth: 120 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                      <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{label}</span>
                      <span style={{ fontSize: 13, fontWeight: 700, color }}>{(value * 100).toFixed(1)}%</span>
                    </div>
                    <div style={{ background: 'var(--border)', borderRadius: 4, height: 8, overflow: 'hidden' }}>
                      <div style={{
                        height: '100%', width: `${Math.min(100, Math.max(0, value * 100))}%`, background: color,
                        borderRadius: 4, transition: 'width 1s ease',
                      }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Anomaly List */}
          <div className="card">
            <div className="card-header">
              <div className="card-title">🚨 Anomaly Records</div>
              <div className="card-subtitle">{filteredAnomalies.length} of {result.anomalies?.length || 0} shown</div>
            </div>
            {!filteredAnomalies.length ? (
              <div className="empty-state">
                <div className="empty-state-icon">✅</div>
                <h3>No anomalies detected</h3>
                <p>The dataset is clean — or try injecting test anomalies.</p>
              </div>
            ) : (
              <div className="table-wrapper">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Anomaly ID</th>
                      <th>Type</th>
                      <th>Severity</th>
                      <th>Description</th>
                      <th>Complaint ID</th>
                      <th>Ground Truth</th>
                      <th>Detected At</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredAnomalies.map((a, i) => (
                      <tr key={i}>
                        <td><span className="table-id">{a.anomaly_id || '—'}</span></td>
                        <td>
                          <span className={`badge ${SEVERITY_BADGE[a.severity] || 'badge-neutral'}`}>
                            {a.anomaly_type?.replace(/_/g, ' ')}
                          </span>
                        </td>
                        <td>
                          <span style={{ color: SEVERITY_COLORS[a.severity] || 'var(--text-muted)', fontWeight: 600, fontSize: 12 }}>
                            {a.severity?.toUpperCase()}
                          </span>
                        </td>
                        <td style={{ maxWidth: 300, fontSize: 12, color: 'var(--text-secondary)' }}>
                          <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {a.description}
                          </div>
                        </td>
                        <td><span className="table-id">{a.complaint_id || '—'}</span></td>
                        <td>
                          <span className={`badge ${a.is_ground_truth ? 'badge-success' : 'badge-neutral'}`}>
                            {a.is_ground_truth ? '✓ Yes' : 'Detected'}
                          </span>
                        </td>
                        <td style={{ fontSize: 12, whiteSpace: 'nowrap' }}>
                          {a.detected_at ? new Date(a.detected_at).toLocaleDateString() : '—'}
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
