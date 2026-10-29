import { useState, useEffect } from 'react';
import { apiClient, api } from '../api';

async function downloadFile(filePath: string, fileName: string) {
  try {
    const resp = await fetch(
      `${api.defaults.baseURL}/api/v1/reports/download?file=${encodeURIComponent(filePath)}`
    );
    if (!resp.ok) {
      const detail = await resp.text().catch(() => `HTTP ${resp.status}`);
      throw new Error(detail);
    }
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = fileName;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : 'Unknown error';
    alert(`Download failed: ${msg}`);
  }
}

interface ReportFile {
  name: string;
  path: string;
  size_bytes: number;
  type: string;
  modified_at?: string;
}

interface ReportsResponse {
  baseline_dir: string;
  files: ReportFile[];
  total_files: number;
  manifest?: Record<string, string>;
}

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function FileIcon({ name }: { name: string }) {
  if (name.endsWith('.csv')) return <>📊</>;
  if (name.endsWith('.json')) return <>📄</>;
  if (name.endsWith('.txt')) return <>📃</>;
  if (name.endsWith('.md')) return <>📝</>;
  return <>📁</>;
}

export default function Reports() {
  const [reports, setReports] = useState<ReportsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [genMsg, setGenMsg] = useState<string | null>(null);

  const fetchReports = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient.getReports();
      setReports(res.data as ReportsResponse);
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      const msg = err instanceof Error ? err.message : 'Failed to load reports';
      setError(detail || msg);
    } finally {
      setLoading(false);
    }
  };

  const generateAndExport = async (scale: 'starter' | 'full') => {
    setGenerating(true);
    setGenMsg(null);
    try {
      const res = await apiClient.generateData({ scale, seed: 20261022, clear_existing: true, export_baseline: true });
      setGenMsg(`✅ Generated ${res.data.counts.complaints || 0} complaints (scale: ${scale}). Refreshing reports…`);
      await fetchReports();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      const msg = err instanceof Error ? err.message : 'Generation failed';
      setGenMsg(`❌ ${detail || msg}`);
    } finally {
      setGenerating(false);
    }
  };

  useEffect(() => { fetchReports(); }, []);

  const csvFiles = reports?.files?.filter(f => f.name.endsWith('.csv')) || [];
  const jsonFiles = reports?.files?.filter(f => f.name.endsWith('.json')) || [];
  const otherFiles = reports?.files?.filter(f => !f.name.endsWith('.csv') && !f.name.endsWith('.json')) || [];

  return (
    <div>
      {/* Actions */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap', alignItems: 'center' }}>
        <button
          id="refresh-reports-btn"
          className="btn btn-secondary btn-sm"
          onClick={fetchReports}
          disabled={loading}
        >
          ↻ Refresh
        </button>
        <button
          id="generate-starter-btn"
          className="btn btn-secondary"
          onClick={() => generateAndExport('starter')}
          disabled={generating}
        >
          {generating ? '⏳ Generating…' : '🔄 Regenerate Starter'}
        </button>
        <button
          id="generate-full-btn"
          className="btn btn-primary"
          onClick={() => generateAndExport('full')}
          disabled={generating}
        >
          {generating ? '⏳ Generating…' : '🚀 Generate Full Dataset'}
        </button>
        {reports?.baseline_dir && (
          <div className="topbar-chip" style={{ marginLeft: 'auto' }}>
            <span>Output</span>
            <span className="chip-label" style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>
              {reports.baseline_dir.split(/[/\\]/).slice(-3).join('/')}
            </span>
          </div>
        )}
      </div>

      {genMsg && (
        <div className={`alert ${genMsg.startsWith('✅') ? 'alert-success' : 'alert-error'}`}>{genMsg}</div>
      )}
      {error && <div className="alert alert-error">⚠️ {error}</div>}

      {/* Summary */}
      {reports && (
        <div className="grid-4" style={{ marginBottom: 24 }}>
          <div className="stat-card" style={{ '--stat-accent': 'var(--accent-primary)' } as React.CSSProperties}>
            <div className="stat-card-label">Total Files</div>
            <div className="stat-card-value">{reports.total_files}</div>
            <div className="stat-card-change">exported artifacts</div>
          </div>
          <div className="stat-card" style={{ '--stat-accent': 'var(--accent-emerald)' } as React.CSSProperties}>
            <div className="stat-card-label">CSV Exports</div>
            <div className="stat-card-value">{csvFiles.length}</div>
            <div className="stat-card-change positive">tabular data</div>
          </div>
          <div className="stat-card" style={{ '--stat-accent': 'var(--accent-violet)' } as React.CSSProperties}>
            <div className="stat-card-label">JSON Exports</div>
            <div className="stat-card-value">{jsonFiles.length}</div>
            <div className="stat-card-change">structured data</div>
          </div>
          <div className="stat-card" style={{ '--stat-accent': 'var(--accent-amber)' } as React.CSSProperties}>
            <div className="stat-card-label">Total Size</div>
            <div className="stat-card-value" style={{ fontSize: 24 }}>
              {formatSize(reports.files?.reduce((a, f) => a + (f.size_bytes || 0), 0) || 0)}
            </div>
            <div className="stat-card-change">on disk</div>
          </div>
        </div>
      )}

      {loading ? (
        <div className="loading-spinner"><div className="spinner" />Loading reports…</div>
      ) : reports?.total_files === 0 ? (
        <div className="empty-state" style={{ paddingTop: 80 }}>
          <div className="empty-state-icon">📁</div>
          <h3>No exports yet</h3>
          <p>Generate a dataset with "Export Baseline" to create reports and export files.</p>
          <button className="btn btn-primary" style={{ marginTop: 16 }} onClick={() => generateAndExport('starter')}>
            🚀 Generate Starter Dataset
          </button>
        </div>
      ) : (
        <>
          {/* Manifest */}
          {reports?.manifest && Object.keys(reports.manifest).length > 0 && (
            <div className="card" style={{ marginBottom: 24 }}>
              <div className="card-header">
                <div className="card-title">🔐 Reproducibility Manifest (SHA-256)</div>
                <div className="card-subtitle">Verify dataset integrity with these checksums</div>
              </div>
              <div className="card-body">
                <div style={{
                  background: 'var(--bg-surface)',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  padding: '12px 16px',
                  fontFamily: 'var(--font-mono)',
                  fontSize: 11,
                  color: 'var(--text-secondary)',
                  maxHeight: 180,
                  overflowY: 'auto',
                }}>
                  {Object.entries(reports.manifest).map(([file, hash]) => (
                    <div key={file} style={{ display: 'flex', gap: 16, marginBottom: 6 }}>
                      <span style={{ color: 'var(--accent-primary)', minWidth: 200 }}>{file}</span>
                      <span style={{ color: 'var(--text-muted)', wordBreak: 'break-all' }}>{hash}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* CSV Files */}
          {csvFiles.length > 0 && (
            <div className="card" style={{ marginBottom: 24 }}>
              <div className="card-header">
                <div className="card-title">📊 CSV Exports</div>
                <div className="card-subtitle">{csvFiles.length} files</div>
              </div>
              <div className="table-wrapper">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>File</th>
                      <th>Type</th>
                      <th>Size</th>
                      <th>Modified</th>
                      <th style={{ width: 120, textAlign: 'center' }}>Export</th>
                    </tr>
                  </thead>
                  <tbody>
                    {csvFiles.map((f, i) => (
                      <tr key={i} style={{ cursor: 'default' }}>
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <span style={{ fontSize: 16 }}><FileIcon name={f.name} /></span>
                            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-primary)' }}>{f.name}</span>
                          </div>
                        </td>
                        <td>
                          <span className="badge badge-info">CSV</span>
                        </td>
                        <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>{formatSize(f.size_bytes || 0)}</td>
                        <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                          {f.modified_at ? new Date(f.modified_at).toLocaleString() : '—'}
                        </td>
                        <td style={{ textAlign: 'center' }}>
                          <button
                            className="btn btn-secondary btn-sm"
                            title={`Download ${f.name}`}
                            onClick={() => downloadFile(f.path, f.name)}
                            style={{ fontSize: 11, padding: '3px 10px', whiteSpace: 'nowrap' }}
                          >
                            ⬇ Export CSV
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* JSON Files */}
          {jsonFiles.length > 0 && (
            <div className="card" style={{ marginBottom: 24 }}>
              <div className="card-header">
                <div className="card-title">📄 JSON Exports</div>
                <div className="card-subtitle">{jsonFiles.length} files</div>
              </div>
              <div className="table-wrapper">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>File</th>
                      <th>Type</th>
                      <th>Size</th>
                      <th>Modified</th>
                      <th style={{ width: 120, textAlign: 'center' }}>Export</th>
                    </tr>
                  </thead>
                  <tbody>
                    {jsonFiles.map((f, i) => (
                      <tr key={i} style={{ cursor: 'default' }}>
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <span style={{ fontSize: 16 }}><FileIcon name={f.name} /></span>
                            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-primary)' }}>{f.name}</span>
                          </div>
                        </td>
                        <td>
                          <span className="badge badge-neutral">JSON</span>
                        </td>
                        <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>{formatSize(f.size_bytes || 0)}</td>
                        <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                          {f.modified_at ? new Date(f.modified_at).toLocaleString() : '—'}
                        </td>
                        <td style={{ textAlign: 'center' }}>
                          <button
                            className="btn btn-secondary btn-sm"
                            title={`Download ${f.name}`}
                            onClick={() => downloadFile(f.path, f.name)}
                            style={{ fontSize: 11, padding: '3px 10px', whiteSpace: 'nowrap' }}
                          >
                            ⬇ Export JSON
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Other Files */}
          {otherFiles.length > 0 && (
            <div className="card" style={{ marginBottom: 24 }}>
              <div className="card-header">
                <div className="card-title">📃 Other Files</div>
                <div className="card-subtitle">Manifests, checksums, and reports</div>
              </div>
              <div className="table-wrapper">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>File</th>
                      <th>Size</th>
                      <th>Modified</th>
                      <th style={{ width: 120, textAlign: 'center' }}>Export</th>
                    </tr>
                  </thead>
                  <tbody>
                    {otherFiles.map((f, i) => (
                      <tr key={i} style={{ cursor: 'default' }}>
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <span style={{ fontSize: 16 }}><FileIcon name={f.name} /></span>
                            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-primary)' }}>{f.name}</span>
                          </div>
                        </td>
                        <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>{formatSize(f.size_bytes || 0)}</td>
                        <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                          {f.modified_at ? new Date(f.modified_at).toLocaleString() : '—'}
                        </td>
                        <td style={{ textAlign: 'center' }}>
                          <button
                            className="btn btn-secondary btn-sm"
                            title={`Download ${f.name}`}
                            onClick={() => downloadFile(f.path, f.name)}
                            style={{ fontSize: 11, padding: '3px 10px', whiteSpace: 'nowrap' }}
                          >
                            ⬇ Export
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}

      {/* CLI Reference */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">⌨️ CLI Reference</div>
          <div className="card-subtitle">Run from the backend/ directory</div>
        </div>
        <div className="card-body">
          {[
            { cmd: 'python cli.py generate --scale starter --clear', desc: 'Generate ~50 complaints (starter scale)' },
            { cmd: 'python cli.py generate --scale full --clear --export', desc: 'Generate 2000 complaints + export baseline' },
            { cmd: 'python cli.py validate', desc: 'Run all 5 validation domains' },
            { cmd: 'python cli.py detect-anomalies', desc: 'Run anomaly detection + metrics' },
            { cmd: 'python cli.py inject-anomalies --count 6', desc: 'Inject test anomaly scenarios' },
            { cmd: 'python cli.py reproduce --run-id <RUN_ID>', desc: 'Verify dataset reproducibility' },
            { cmd: 'python cli.py export --format both --output-dir ./exports', desc: 'Export all data as CSV + JSON' },
            { cmd: 'python cli.py server --reload', desc: 'Start FastAPI development server' },
          ].map(({ cmd, desc }) => (
            <div key={cmd} style={{
              display: 'flex', gap: 16, alignItems: 'flex-start',
              padding: '10px 0', borderBottom: '1px solid var(--border)',
            }}>
              <code style={{
                fontFamily: 'var(--font-mono)', fontSize: 12,
                background: 'var(--bg-surface)', border: '1px solid var(--border)',
                borderRadius: 6, padding: '4px 8px', color: 'var(--accent-primary)',
                whiteSpace: 'nowrap', flexShrink: 0,
              }}>{cmd}</code>
              <span style={{ fontSize: 12, color: 'var(--text-muted)', paddingTop: 4 }}>{desc}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
