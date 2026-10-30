import { useState, useEffect } from 'react';
import { apiClient, api } from '../api';
import type { ReportsResponse } from '../api';

async function saveDownload(blob: Blob, fileName: string, expectedSha256?: string) {
  if (expectedSha256) {
    const bytes = await blob.arrayBuffer();
    const digest = await crypto.subtle.digest('SHA-256', bytes);
    const actualSha256 = Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('');
    if (actualSha256 !== expectedSha256) {
      throw new Error(`Checksum mismatch for ${fileName}`);
    }
  }

  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = fileName;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function downloadFile(filePath: string, fileName: string, sha256: string) {
  try {
    const response = await apiClient.downloadReportFile(filePath);
    await saveDownload(response.data, fileName, sha256);
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : 'Unknown error';
    alert(`Download failed: ${msg}`);
  }
}

async function downloadReport(reportId: string, fileName: string) {
  try {
    const response = await apiClient.downloadReport(reportId);
    await saveDownload(response.data, fileName, response.headers['x-checksum-sha256']);
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : 'Unknown error';
    alert(`Download failed: ${msg}`);
  }
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
      setReports(res.data);
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
      await apiClient.exportBaseline(scale, 20261022);
      setGenMsg(`✅ Exported baseline dataset files (scale: ${scale}). Refreshing reports…`);
      await fetchReports();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      const msg = err instanceof Error ? err.message : 'Export failed';
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
          {generating ? '⏳ Exporting…' : '🔄 Export Starter Baseline'}
        </button>
        <button
          id="generate-full-btn"
          className="btn btn-primary"
          onClick={() => generateAndExport('full')}
          disabled={generating}
          title="Generates CSV and JSON exports only; it does not modify database records."
        >
          {generating ? '⏳ Exporting…' : '🚀 Export Full Baseline'}
        </button>
        {!import.meta.env.DEV && (
          <div
            className="topbar-chip"
            style={{ fontSize: 11, color: 'var(--text-muted)', border: '1px solid var(--border)' }}
            title="Baseline export generation does not modify production database records."
          >
            🛡️ Production Database Protected
          </div>
        )}
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

      {reports?.reports && reports.reports.length > 0 && (
        <div className="card" style={{ marginBottom: 24 }}>
          <div className="card-header">
            <div className="card-title">📑 System Reports</div>
            <div className="card-subtitle">{reports.reports.length} available reports</div>
          </div>
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Report</th>
                  <th>Category</th>
                  <th>Format</th>
                  <th>Generated</th>
                  <th style={{ width: 180, textAlign: 'center' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {reports.reports.map(report => (
                  <tr key={report.report_id}>
                    <td>
                      <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{report.title}</div>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{report.description}</div>
                    </td>
                    <td>{report.category}</td>
                    <td><span className="badge badge-neutral">{report.format.toUpperCase()}</span></td>
                    <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                      {report.generated_at ? new Date(report.generated_at).toLocaleString() : '—'}
                    </td>
                    <td style={{ textAlign: 'center', whiteSpace: 'nowrap' }}>
                      {report.url && (
                        <a
                          className="btn btn-secondary btn-sm"
                          href={new URL(report.url, `${api.defaults.baseURL}/`).toString()}
                          target="_blank"
                          rel="noreferrer"
                          style={{ marginRight: 6 }}
                        >
                          View
                        </a>
                      )}
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={() => downloadReport(report.report_id, `${report.report_id}.${report.format === 'markdown' ? 'md' : 'json'}`)}
                      >
                        ⬇ Download
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
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
                            onClick={() => downloadFile(f.path, f.name, f.sha256)}
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
                            onClick={() => downloadFile(f.path, f.name, f.sha256)}
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
                            onClick={() => downloadFile(f.path, f.name, f.sha256)}
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
          <div className="card-title">⌨️ CLI & Operations Reference</div>
          <div className="card-subtitle">Commands run from the backend/ directory</div>
        </div>
        <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {/* Section 1: Local Development Seeding */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <span className="badge badge-warning" style={{ fontSize: 10, textTransform: 'uppercase' }}>Local Dev Only</span>
              <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>Synthetic Dataset Seeding</span>
            </div>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '0 0 10px 0' }}>
              Destructive <code style={{ color: 'var(--accent-warning)' }}>--clear</code> resets are strictly restricted to local SQLite development. They are blocked by production guards.
            </p>
            {[
              { cmd: 'python cli.py generate --scale starter --clear', desc: 'Seed local SQLite with ~50 starter complaints' },
              { cmd: 'python cli.py generate --scale full --clear --export', desc: 'Seed local SQLite with 2,000 complaints & export baseline files' },
              { cmd: 'python cli.py server --reload', desc: 'Start FastAPI local development server with auto-reload' },
              { cmd: 'python cli.py inject-anomalies --count 6', desc: 'Inject test anomaly patterns into local database' },
            ].map(({ cmd, desc }) => (
              <div key={cmd} style={{
                display: 'flex', gap: 16, alignItems: 'flex-start',
                padding: '8px 0', borderBottom: '1px solid var(--border)',
              }}>
                <code style={{
                  fontFamily: 'var(--font-mono)', fontSize: 12,
                  background: 'var(--bg-surface)', border: '1px solid var(--border)',
                  borderRadius: 6, padding: '3px 8px', color: 'var(--accent-primary)',
                  whiteSpace: 'nowrap', flexShrink: 0,
                }}>{cmd}</code>
                <span style={{ fontSize: 12, color: 'var(--text-muted)', paddingTop: 3 }}>{desc}</span>
              </div>
            ))}
          </div>

          {/* Section 2: Safe Environment-Agnostic Commands */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <span className="badge badge-info" style={{ fontSize: 10, textTransform: 'uppercase' }}>Operational</span>
              <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>Validation, Analytics & Reporting</span>
            </div>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '0 0 10px 0' }}>
              Safe read-only and analytical commands suitable for both local development and active environments.
            </p>
            {[
              { cmd: 'python cli.py validate', desc: 'Run all 5 validation domains (integrity, SLA, sentiment, priority, anomaly)' },
              { cmd: 'python cli.py detect-anomalies', desc: 'Run statistical anomaly detection & report precision/recall metrics' },
              { cmd: 'python cli.py reproduce --run-id <RUN_ID>', desc: 'Verify deterministic reproducibility against canonical baseline' },
              { cmd: 'python cli.py export --format both --output-dir ./exports', desc: 'Export active database tables as CSV and JSON' },
            ].map(({ cmd, desc }) => (
              <div key={cmd} style={{
                display: 'flex', gap: 16, alignItems: 'flex-start',
                padding: '8px 0', borderBottom: '1px solid var(--border)',
              }}>
                <code style={{
                  fontFamily: 'var(--font-mono)', fontSize: 12,
                  background: 'var(--bg-surface)', border: '1px solid var(--border)',
                  borderRadius: 6, padding: '3px 8px', color: 'var(--accent-primary)',
                  whiteSpace: 'nowrap', flexShrink: 0,
                }}>{cmd}</code>
                <span style={{ fontSize: 12, color: 'var(--text-muted)', paddingTop: 3 }}>{desc}</span>
              </div>
            ))}
          </div>

          {/* Section 3: Production Administration & Restoration */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <span className="badge badge-success" style={{ fontSize: 10, textTransform: 'uppercase' }}>Production</span>
              <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>Administrative Migration & Restoration</span>
            </div>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '0 0 10px 0' }}>
              Production dataset restoration never uses synthetic generators. Restorations must be performed using the verified administrative migration utility with atomic transaction rollback and count verification.
            </p>
            {[
              { cmd: 'python backend/scripts/migrate_sqlite_to_pg.py --sqlite-path <backup.db> --dry-run', desc: 'Read-only inspection of source backup tables and counts' },
              { cmd: 'python backend/scripts/migrate_sqlite_to_pg.py --sqlite-path <backup.db> --pg-url <URL> --clean-destination-for-restore', desc: 'Execute atomic restore: clears destination in reverse FK order, restores all 18 tables, syncs sequences, and validates 100% row counts' },
            ].map(({ cmd, desc }) => (
              <div key={cmd} style={{
                display: 'flex', gap: 16, alignItems: 'flex-start',
                padding: '8px 0', borderBottom: '1px solid var(--border)',
              }}>
                <code style={{
                  fontFamily: 'var(--font-mono)', fontSize: 11,
                  background: 'var(--bg-surface)', border: '1px solid var(--border)',
                  borderRadius: 6, padding: '3px 8px', color: 'var(--accent-success)',
                  whiteSpace: 'nowrap', flexShrink: 0,
                }}>{cmd}</code>
                <span style={{ fontSize: 12, color: 'var(--text-muted)', paddingTop: 3 }}>{desc}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
