import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search } from 'lucide-react';
import { apiClient, type ComplaintListItem, type PaginatedResponse } from '../api';

const PRIORITY_LABELS: Record<string, string> = { P1: 'Critical', P2: 'High', P3: 'Medium', P4: 'Low' };
const CATEGORY_LABELS: Record<string, string> = {
  DELIVERY_DELAY: 'Delivery Delay', DAMAGED_PRODUCT: 'Damaged Product',
  PRODUCT_SAFETY: 'Product Safety', REFUND: 'Refund', PAYMENT: 'Payment',
  PRODUCT_QUALITY: 'Product Quality', WRONG_ITEM: 'Wrong Item',
  MISSING_ORDER: 'Missing Order', ACCOUNT_SERVICE: 'Account/Service', OTHER: 'Other',
};

function PriorityBadge({ p }: { p: string }) {
  return <span className={`badge badge-${p.toLowerCase()}`}>{p} — {PRIORITY_LABELS[p] || p}</span>;
}

function StatusBadge({ s }: { s: string }) {
  const label = s.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase());
  return <span className={`badge badge-${s}`}>{label}</span>;
}

function formatDate(iso?: string) {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }); }
  catch { return iso; }
}

export default function Complaints() {
  const navigate = useNavigate();
  const [data, setData] = useState<PaginatedResponse<ComplaintListItem> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [priorityFilter, setPriorityFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [safetyOnly, setSafetyOnly] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = { page, page_size: 20 };
      if (search) params.search = search;
      if (statusFilter) params.status = statusFilter;
      if (priorityFilter) params.priority = priorityFilter;
      if (categoryFilter) params.category_code = categoryFilter;
      if (safetyOnly) {
        params.safety_only = true;
        params.is_safety_incident = true;
      }
      const res = await apiClient.getComplaints(params);
      setData(res.data);
      setError(null);
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      const msg = err instanceof Error ? err.message : 'Failed to load complaints';
      setError(detail || msg);
    } finally {
      setLoading(false);
    }
  }, [page, search, statusFilter, priorityFilter, categoryFilter, safetyOnly]);

  useEffect(() => { fetchData(); }, [fetchData]);
  useEffect(() => { setPage(1); }, [search, statusFilter, priorityFilter, categoryFilter, safetyOnly]);

  return (
    <div>
      {/* Toolbar */}
      <div className="toolbar">
        <div className="search-input-wrapper">
          <Search className="search-input-icon" size={15} />
          <input
            id="complaint-search"
            className="search-input"
            placeholder="Search complaints, subjects, IDs…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        <select id="status-filter" className="filter-select" value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
          <option value="">All Statuses</option>
          <option value="open">Open</option>
          <option value="in_progress">In Progress</option>
          <option value="escalated">Escalated</option>
          <option value="resolved">Resolved</option>
          <option value="closed">Closed</option>
          <option value="reopened">Reopened</option>
        </select>
        <select id="priority-filter" className="filter-select" value={priorityFilter} onChange={e => setPriorityFilter(e.target.value)}>
          <option value="">All Priorities</option>
          <option value="P1">P1 — Critical</option>
          <option value="P2">P2 — High</option>
          <option value="P3">P3 — Medium</option>
          <option value="P4">P4 — Low</option>
        </select>
        <select id="category-filter" className="filter-select" value={categoryFilter} onChange={e => setCategoryFilter(e.target.value)}>
          <option value="">All Categories</option>
          {Object.entries(CATEGORY_LABELS).map(([code, label]) => (
            <option key={code} value={code}>{label}</option>
          ))}
        </select>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: 'var(--text-secondary)', cursor: 'pointer' }}>
          <input type="checkbox" checked={safetyOnly} onChange={e => setSafetyOnly(e.target.checked)} />
          Safety Only
        </label>
        <button className="btn btn-secondary btn-sm" onClick={fetchData}>↻</button>
      </div>

      {error && <div className="alert alert-error">⚠️ {error}</div>}

      <div className="card">
        {loading ? (
          <div className="loading-spinner"><div className="spinner" />Loading complaints…</div>
        ) : !data?.items.length ? (
          <div className="empty-state">
            <div className="empty-state-icon">📭</div>
            <h3>No complaints found</h3>
            <p>Try adjusting your filters or generate data from the Dashboard.</p>
          </div>
        ) : (
          <>
            <div className="table-wrapper">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Subject</th>
                    <th>Status</th>
                    <th>Priority</th>
                    <th>Category</th>
                    <th>Customer</th>
                    <th>Channel</th>
                    <th>Created</th>
                    <th>Flags</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map(c => (
                    <tr key={c.complaint_id} onClick={() => navigate(`/complaints/${c.complaint_id}`)}>
                      <td><span className="table-id">{c.complaint_id}</span></td>
                      <td style={{ maxWidth: 280 }}>
                        <div style={{ color: 'var(--text-primary)', fontWeight: 500, fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {c.subject}
                        </div>
                      </td>
                      <td><StatusBadge s={c.status} /></td>
                      <td><PriorityBadge p={c.priority} /></td>
                      <td style={{ fontSize: 12 }}>{CATEGORY_LABELS[c.category_code] || c.category_code}</td>
                      <td>
                        <div style={{ fontSize: 12 }}>{c.customer_name || c.customer_id}</div>
                      </td>
                      <td style={{ fontSize: 12, color: 'var(--text-muted)', textTransform: 'capitalize' }}>{c.channel}</td>
                      <td style={{ fontSize: 12, whiteSpace: 'nowrap' }}>{formatDate(c.created_at)}</td>
                      <td>
                        <div style={{ display: 'flex', gap: 4 }}>
                          {c.is_safety_incident && <span className="badge badge-safety" title="Safety Incident">⚠️</span>}
                          {c.is_escalated && <span className="badge badge-p2" title="Escalated">🔺</span>}
                          {c.is_anomaly && <span className="badge badge-anomaly" title="Anomaly">🔍</span>}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            <div className="pagination">
              <div className="pagination-info">
                Showing {((page - 1) * 20) + 1}–{Math.min(page * 20, data.total)} of {data.total.toLocaleString()} complaints
              </div>
              <div className="pagination-controls">
                <button id="prev-page" className="page-btn" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>‹</button>
                {Array.from({ length: Math.min(5, data.total_pages) }, (_, i) => {
                  const p = Math.max(1, Math.min(page - 2, data.total_pages - 4)) + i;
                  if (p < 1 || p > data.total_pages) return null;
                  return (
                    <button key={p} className={`page-btn ${p === page ? 'active' : ''}`} onClick={() => setPage(p)}>{p}</button>
                  );
                })}
                <button id="next-page" className="page-btn" disabled={page >= data.total_pages} onClick={() => setPage(p => p + 1)}>›</button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
