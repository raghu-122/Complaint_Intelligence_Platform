import { useState, useRef, useCallback } from 'react';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface IngestionError {
  row: number;
  field: string;
  error: string;
}

interface IngestionResult {
  accepted: number;
  rejected: number;
  skipped_duplicates: number;
  total_rows_processed: number;
  errors: IngestionError[];
}

type TargetType = 'complaints' | 'customers';

function SchemaCard({ target }: { target: TargetType }) {
  const [schema, setSchema] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API_BASE}/api/v1/ingest/schema/${target}`);
      setSchema(await r.json());
    } catch {
      setSchema({ error: 'Failed to load schema.' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card" style={{ marginTop: '1rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ margin: 0 }}>Expected Schema</h3>
        <button className="btn" onClick={load} disabled={loading}>
          {loading ? 'Loading…' : 'View Schema'}
        </button>
      </div>
      {schema && (
        <pre style={{
          background: 'var(--bg-secondary, #1e1e2e)',
          borderRadius: '6px',
          padding: '1rem',
          overflow: 'auto',
          fontSize: '0.78rem',
          marginTop: '0.75rem',
          maxHeight: '300px',
        }}>
          {JSON.stringify(schema, null, 2)}
        </pre>
      )}
    </div>
  );
}

function DropZone({ onFile }: { onFile: (f: File) => void }) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) onFile(f);
  }, [onFile]);

  return (
    <div
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      style={{
        border: `2px dashed ${dragging ? 'var(--accent, #7c3aed)' : 'var(--border, #334155)'}`,
        borderRadius: '10px',
        padding: '2.5rem 1.5rem',
        textAlign: 'center',
        cursor: 'pointer',
        transition: 'border-color 0.2s',
        background: dragging ? 'rgba(124,58,237,0.07)' : 'transparent',
      }}
    >
      <div style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>📂</div>
      <p style={{ margin: 0, fontSize: '0.95rem', opacity: 0.8 }}>
        Drag &amp; drop a <strong>.csv</strong> or <strong>.json</strong> file here,<br />
        or click to browse
      </p>
      <p style={{ margin: '0.4rem 0 0', fontSize: '0.78rem', opacity: 0.5 }}>Max 10 MB</p>
      <input
        ref={inputRef}
        type="file"
        accept=".csv,.json"
        style={{ display: 'none' }}
        onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); }}
      />
    </div>
  );
}

function ResultPanel({ result, filename }: { result: IngestionResult; filename: string }) {
  const hasErrors = result.errors.length > 0;
  const allGood = result.accepted > 0 && !hasErrors;

  return (
    <div className="card" style={{ marginTop: '1.25rem' }}>
      <h3 style={{ margin: '0 0 1rem' }}>Ingestion Result — {filename}</h3>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.75rem', marginBottom: '1rem' }}>
        {[
          { label: 'Accepted', value: result.accepted, color: '#22c55e' },
          { label: 'Rejected', value: result.rejected, color: '#ef4444' },
          { label: 'Deduplicated', value: result.skipped_duplicates, color: '#f59e0b' },
          { label: 'Total Processed', value: result.total_rows_processed, color: '#60a5fa' },
        ].map(({ label, value, color }) => (
          <div key={label} style={{
            background: 'var(--bg-secondary, #1e1e2e)',
            borderRadius: '8px',
            padding: '0.75rem 1rem',
            textAlign: 'center',
          }}>
            <div style={{ fontSize: '1.6rem', fontWeight: 700, color }}>{value}</div>
            <div style={{ fontSize: '0.75rem', opacity: 0.7, marginTop: '0.2rem' }}>{label}</div>
          </div>
        ))}
      </div>

      {allGood && (
        <div style={{
          background: 'rgba(34,197,94,0.12)',
          border: '1px solid rgba(34,197,94,0.4)',
          borderRadius: '8px',
          padding: '0.75rem 1rem',
          color: '#4ade80',
          fontSize: '0.88rem',
        }}>
          ✅ All rows ingested successfully with no validation errors.
        </div>
      )}

      {hasErrors && (
        <>
          <h4 style={{ margin: '1rem 0 0.5rem', color: '#f87171' }}>
            ⚠️ Validation Errors ({result.errors.length})
          </h4>
          <div style={{ maxHeight: '280px', overflowY: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
              <thead>
                <tr style={{ background: 'var(--bg-secondary, #1e1e2e)' }}>
                  {['Row', 'Field', 'Error'].map(h => (
                    <th key={h} style={{
                      padding: '0.45rem 0.75rem',
                      textAlign: 'left',
                      borderBottom: '1px solid var(--border, #334155)',
                      fontWeight: 600,
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.errors.map((e, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid var(--border-subtle, #1e293b)' }}>
                    <td style={{ padding: '0.4rem 0.75rem', opacity: 0.7 }}>{e.row || '—'}</td>
                    <td style={{ padding: '0.4rem 0.75rem', color: '#fbbf24', fontFamily: 'monospace' }}>{e.field}</td>
                    <td style={{ padding: '0.4rem 0.75rem', color: '#f87171' }}>{e.error}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

export default function Ingestion() {
  const [target, setTarget] = useState<TargetType>('complaints');
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<IngestionResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFile = (f: File) => {
    setFile(f);
    setResult(null);
    setError(null);
  };

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setError(null);
    setResult(null);

    const form = new FormData();
    form.append('file', file);

    try {
      const r = await fetch(`${API_BASE}/api/v1/ingest/${target}`, {
        method: 'POST',
        body: form,
      });
      if (!r.ok) {
        const detail = await r.json().catch(() => ({ detail: r.statusText }));
        setError(detail.detail || `HTTP ${r.status}`);
      } else {
        setResult(await r.json());
      }
    } catch (err) {
      setError(`Network error: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div style={{ maxWidth: '860px', margin: '0 auto' }}>
      {/* Target selector */}
      <div className="card" style={{ marginBottom: '1.25rem' }}>
        <h2 style={{ margin: '0 0 0.75rem' }}>Data Ingestion Pipeline</h2>
        <p style={{ margin: '0 0 1rem', opacity: 0.7, fontSize: '0.9rem' }}>
          Upload CSV or JSON files to import complaint or customer records.
          The pipeline validates required fields, enum values, data types, and deduplicates by ID before persisting to the database.
        </p>

        <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1.25rem' }}>
          {(['complaints', 'customers'] as TargetType[]).map(t => (
            <button
              key={t}
              onClick={() => { setTarget(t); setResult(null); setError(null); setFile(null); }}
              className="btn"
              style={{
                background: target === t ? 'var(--accent, #7c3aed)' : 'var(--bg-secondary, #1e1e2e)',
                color: target === t ? '#fff' : undefined,
                textTransform: 'capitalize',
              }}
            >
              {t === 'complaints' ? '📋 Complaints' : '👥 Customers'}
            </button>
          ))}
        </div>

        <DropZone onFile={handleFile} />

        {file && (
          <div style={{ marginTop: '0.75rem', display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <span style={{ fontSize: '0.85rem', opacity: 0.8 }}>
              📄 {file.name} ({(file.size / 1024).toFixed(1)} KB)
            </span>
            <button
              className="btn"
              onClick={handleUpload}
              disabled={uploading}
              style={{ background: 'var(--accent, #7c3aed)', color: '#fff' }}
            >
              {uploading ? 'Uploading…' : `Ingest into ${target}`}
            </button>
            <button
              className="btn"
              onClick={() => { setFile(null); setResult(null); setError(null); }}
              style={{ opacity: 0.6 }}
            >
              Clear
            </button>
          </div>
        )}

        {error && (
          <div style={{
            marginTop: '0.75rem',
            background: 'rgba(239,68,68,0.12)',
            border: '1px solid rgba(239,68,68,0.4)',
            borderRadius: '8px',
            padding: '0.75rem 1rem',
            color: '#f87171',
            fontSize: '0.88rem',
          }}>
            ❌ {error}
          </div>
        )}
      </div>

      {/* Result panel */}
      {result && <ResultPanel result={result} filename={file?.name || 'upload'} />}

      {/* Schema card */}
      <SchemaCard target={target} />
    </div>
  );
}

