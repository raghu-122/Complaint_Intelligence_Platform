import { useState, useEffect, useCallback } from 'react';
import { Search } from 'lucide-react';
import { apiClient, type CustomerListItem, type PaginatedResponse } from '../api';

function formatDate(iso?: string) {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }); }
  catch { return iso; }
}

const TIER_CONFIG: Record<string, { label: string; className: string }> = {
  vip: { label: 'VIP', className: 'badge-p1' },
  premium: { label: 'Premium', className: 'badge-p2' },
  standard: { label: 'Standard', className: 'badge-neutral' },
};

function TierBadge({ tier }: { tier: string }) {
  const normalized = (tier || '').toLowerCase();
  const config = TIER_CONFIG[normalized] || {
    label: tier ? (tier.toUpperCase() === 'VIP' ? 'VIP' : tier.charAt(0).toUpperCase() + tier.slice(1)) : 'Standard',
    className: 'badge-neutral',
  };
  return <span className={`badge ${config.className}`}>{config.label}</span>;
}

export default function Customers() {
  const [data, setData] = useState<PaginatedResponse<CustomerListItem> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [tierFilter, setTierFilter] = useState('');
  const [vulnerableOnly, setVulnerableOnly] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = { page, page_size: 20 };
      if (search) params.search = search;
      if (tierFilter) params.account_tier = tierFilter;
      if (vulnerableOnly) {
        params.vulnerable_only = true;
        params.vulnerability_flag = true;
      }
      const res = await apiClient.getCustomers(params);
      setData(res.data);
      setError(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to load customers');
    } finally {
      setLoading(false);
    }
  }, [page, search, tierFilter, vulnerableOnly]);

  useEffect(() => { fetchData(); }, [fetchData]);
  useEffect(() => { setPage(1); }, [search, tierFilter, vulnerableOnly]);

  return (
    <div>
      <div className="toolbar">
        <div className="search-input-wrapper">
          <Search className="search-input-icon" size={15} />
          <input
            id="customer-search"
            className="search-input"
            placeholder="Search customers by name or email…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        <select id="tier-filter" className="filter-select" value={tierFilter} onChange={e => setTierFilter(e.target.value)}>
          <option value="">All Tiers</option>
          <option value="vip">VIP</option>
          <option value="premium">Premium</option>
          <option value="standard">Standard</option>
        </select>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: 'var(--text-secondary)', cursor: 'pointer' }}>
          <input type="checkbox" checked={vulnerableOnly} onChange={e => setVulnerableOnly(e.target.checked)} />
          Vulnerable Only
        </label>
        <button className="btn btn-secondary btn-sm" onClick={fetchData}>↻</button>
      </div>

      {error && <div className="alert alert-error">⚠️ {error}</div>}

      <div className="card">
        {loading ? (
          <div className="loading-spinner"><div className="spinner" />Loading customers…</div>
        ) : !data?.items.length ? (
          <div className="empty-state">
            <div className="empty-state-icon">👥</div>
            <h3>No customers found</h3>
            <p>Generate data from the Dashboard to populate customer records.</p>
          </div>
        ) : (
          <>
            <div className="table-wrapper">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Customer ID</th>
                    <th>Name</th>
                    <th>Email</th>
                    <th>Tier</th>
                    <th>Complaints</th>
                    <th>Status</th>
                    <th>Vulnerable</th>
                    <th>Member Since</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map(c => (
                    <tr key={c.customer_id} style={{ cursor: 'default' }}>
                      <td><span className="table-id">{c.customer_id}</span></td>
                      <td style={{ fontWeight: 500, color: 'var(--text-primary)' }}>
                        {c.first_name} {c.last_name}
                      </td>
                      <td style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                        {c.email}
                      </td>
                      <td><TierBadge tier={c.account_tier} /></td>
                      <td>
                        <span style={{
                          fontWeight: 700,
                          color: c.complaint_count > 5 ? 'var(--p1)' : c.complaint_count > 2 ? 'var(--p2)' : 'var(--text-primary)'
                        }}>
                          {c.complaint_count}
                        </span>
                      </td>
                      <td>
                        <span className={`badge ${c.is_active ? 'badge-success' : 'badge-neutral'}`}>
                          {c.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td>
                        {c.vulnerability_flag && (
                          <span className="badge badge-safety" title="Vulnerable Customer">⚠️ Yes</span>
                        )}
                      </td>
                      <td style={{ fontSize: 12 }}>{formatDate(c.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="pagination">
              <div className="pagination-info">
                Showing {((page - 1) * 20) + 1}–{Math.min(page * 20, data.total)} of {data.total.toLocaleString()} customers
              </div>
              <div className="pagination-controls">
                <button id="cust-prev-page" className="page-btn" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>‹</button>
                {Array.from({ length: Math.min(5, data.total_pages) }, (_, i) => {
                  const p = Math.max(1, Math.min(page - 2, data.total_pages - 4)) + i;
                  if (p < 1 || p > data.total_pages) return null;
                  return (
                    <button key={p} className={`page-btn ${p === page ? 'active' : ''}`} onClick={() => setPage(p)}>{p}</button>
                  );
                })}
                <button id="cust-next-page" className="page-btn" disabled={page >= data.total_pages} onClick={() => setPage(p => p + 1)}>›</button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
