import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { apiClient, type ComplaintDetail as TComplaintDetail } from '../api';

function formatDate(iso?: string) {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' }); }
  catch { return iso; }
}

function Badge({ text, className }: { text: string; className?: string }) {
  return <span className={`badge ${className || 'badge-neutral'}`}>{text}</span>;
}

function DetailField({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="detail-field">
      <div className="detail-field-label">{label}</div>
      <div className="detail-field-value">{value || '—'}</div>
    </div>
  );
}

export default function ComplaintDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [complaint, setComplaint] = useState<TComplaintDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'overview' | 'messages' | 'timeline' | 'resolution'>('overview');

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    apiClient.getComplaint(id)
      .then(res => { setComplaint(res.data); setError(null); })
      .catch(err => setError(err.response?.data?.detail || 'Complaint not found'))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return (
    <div className="loading-spinner"><div className="spinner" />Loading complaint…</div>
  );
  if (error) return (
    <div style={{ padding: 48, textAlign: 'center' }}>
      <div className="alert alert-error">{error}</div>
      <button className="btn btn-secondary" onClick={() => navigate('/complaints')}>← Back to Complaints</button>
    </div>
  );
  if (!complaint) return null;

  const priorityClass = `badge-${complaint.priority.toLowerCase()}`;
  const statusClass = `badge-${complaint.status}`;

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
        <button className="btn btn-secondary btn-sm" onClick={() => navigate('/complaints')}>← Back</button>
        <div style={{ flex: 1 }}>
          <span className="table-id" style={{ fontSize: 12 }}>{complaint.complaint_id}</span>
          <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)', marginTop: 2 }}>{complaint.subject}</h2>
        </div>
        <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
          <Badge text={complaint.priority} className={priorityClass} />
          <Badge text={complaint.status.replace('_', ' ')} className={statusClass} />
          {complaint.is_safety_incident && <Badge text="⚠️ Safety" className="badge-safety" />}
          {complaint.is_escalated && <Badge text="🔺 Escalated" className="badge-p2" />}
          {complaint.is_anomaly && <Badge text="🔍 Anomaly" className="badge-anomaly" />}
        </div>
      </div>

      {/* Tabs */}
      <div className="tabs">
        {(['overview', 'messages', 'timeline', 'resolution'] as const).map(tab => (
          <button
            key={tab}
            className={`tab ${activeTab === tab ? 'active' : ''}`}
            onClick={() => setActiveTab(tab)}
          >
            {tab === 'overview' && '📋 Overview'}
            {tab === 'messages' && `💬 Messages (${complaint.messages?.length || 0})`}
            {tab === 'timeline' && `📅 Timeline (${complaint.status_events?.length || 0})`}
            {tab === 'resolution' && '✅ Resolution & Survey'}
          </button>
        ))}
      </div>

      {/* Overview Tab */}
      {activeTab === 'overview' && (
        <div>
          <div className="grid-2" style={{ marginBottom: 16 }}>
            {/* Complaint Details */}
            <div className="card">
              <div className="card-header"><div className="card-title">📋 Complaint Details</div></div>
              <div className="card-body">
                <div className="detail-grid">
                  <DetailField label="Category" value={complaint.category?.name || complaint.category_code} />
                  <DetailField label="Channel" value={<span style={{ textTransform: 'capitalize' }}>{complaint.channel}</span>} />
                  <DetailField label="Sentiment" value={<span style={{ textTransform: 'capitalize' }}>{complaint.sentiment}</span>} />
                  <DetailField label="SLA Status" value={
                    complaint.sla_clock ? (
                      <Badge
                        text={complaint.sla_clock.is_breached ? '❌ Breached' : '✅ On Time'}
                        className={complaint.sla_clock.is_breached ? 'badge-p1' : 'badge-success'}
                      />
                    ) : '—'
                  } />
                  <DetailField label="Created" value={formatDate(complaint.created_at)} />
                  <DetailField label="Resolved" value={formatDate(complaint.resolved_at)} />
                  <DetailField label="Classification Confidence" value={
                    complaint.classification_confidence ? `${(complaint.classification_confidence * 100).toFixed(0)}%` : '—'
                  } />
                  <DetailField label="Refund Pending" value={complaint.is_refund_pending ? '💰 Yes' : 'No'} />
                </div>
                <div style={{ marginTop: 12 }}>
                  <div className="detail-field-label" style={{ marginBottom: 6 }}>Description</div>
                  <div style={{
                    background: 'var(--bg-surface)',
                    border: '1px solid var(--border)',
                    borderRadius: 8,
                    padding: '12px 14px',
                    fontSize: 13,
                    color: 'var(--text-secondary)',
                    lineHeight: 1.6,
                  }}>
                    {complaint.description || 'No description available.'}
                  </div>
                </div>
                {complaint.priority_explanation && (
                  <div style={{ marginTop: 12 }}>
                    <div className="detail-field-label" style={{ marginBottom: 6 }}>Priority Explanation</div>
                    <div style={{
                      background: 'var(--bg-surface)',
                      border: '1px solid var(--border)',
                      borderRadius: 8,
                      padding: '10px 14px',
                      fontSize: 12,
                      color: 'var(--text-muted)',
                      fontStyle: 'italic',
                    }}>
                      {complaint.priority_explanation}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Right column */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {/* Customer */}
              {complaint.customer && (
                <div className="card">
                  <div className="card-header"><div className="card-title">👤 Customer</div></div>
                  <div className="card-body">
                    <div className="detail-grid">
                      <DetailField label="Name" value={`${complaint.customer.name}`} />
                      <DetailField label="Tier" value={
                        <Badge text={complaint.customer.account_tier} className="badge-info" />
                      } />
                      <DetailField label="Email" value={
                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{complaint.customer.email}</span>
                      } />
                      <DetailField label="Vulnerable" value={complaint.customer.vulnerability_flag ? '⚠️ Yes' : 'No'} />
                    </div>
                  </div>
                </div>
              )}

              {/* Order */}
              {complaint.order && (
                <div className="card">
                  <div className="card-header"><div className="card-title">🛍️ Order</div></div>
                  <div className="card-body">
                    <div className="detail-grid">
                      <DetailField label="Order ID" value={
                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{complaint.order.order_id}</span>
                      } />
                      <DetailField label="Status" value={
                        <span style={{ textTransform: 'capitalize' }}>{complaint.order.status}</span>
                      } />
                      <DetailField label="Total" value={`$${complaint.order.total_amount}`} />
                      <DetailField label="Date" value={formatDate(complaint.order.ordered_at)} />
                    </div>
                  </div>
                </div>
              )}

              {/* Assignment */}
              {complaint.current_assignment && (
                <div className="card">
                  <div className="card-header"><div className="card-title">👨‍💼 Assigned To</div></div>
                  <div className="card-body">
                    <div className="detail-grid">
                      <DetailField label="Agent" value={complaint.current_assignment.agent_name} />
                      <DetailField label="Team" value={complaint.current_assignment.team_name} />
                      <DetailField label="Assigned" value={formatDate(complaint.current_assignment.assigned_at)} />
                    </div>
                  </div>
                </div>
              )}

              {/* SLA */}
              {complaint.sla_clock && (
                <div className="card">
                  <div className="card-header"><div className="card-title">⏱️ SLA Clock</div></div>
                  <div className="card-body">
                    <div className="detail-grid">
                      <DetailField label="Priority" value={complaint.sla_clock.priority} />
                      <DetailField label="Resolution SLA" value={`${complaint.sla_clock.resolution_hours}h`} />
                      <DetailField label="Status" value={
                        <Badge
                          text={complaint.sla_clock.is_breached ? '❌ Breached' : '✅ Compliant'}
                          className={complaint.sla_clock.is_breached ? 'badge-p1' : 'badge-success'}
                        />
                      } />
                      <DetailField label="Deadline" value={formatDate(complaint.sla_clock.original_deadline)} />
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Messages Tab */}
      {activeTab === 'messages' && (
        <div className="card">
          <div className="card-header">
            <div className="card-title">💬 Communication Thread</div>
            <div className="card-subtitle">{complaint.messages?.length || 0} messages</div>
          </div>
          <div className="card-body" style={{ padding: 20 }}>
            {!complaint.messages?.length ? (
              <div className="empty-state"><div className="empty-state-icon">💬</div><h3>No messages</h3></div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {complaint.messages.map((msg, i) => (
                  <div key={i} style={{
                    display: 'flex',
                    gap: 12,
                    flexDirection: msg.sender_type === 'agent' ? 'row-reverse' : 'row',
                  }}>
                    <div style={{
                      width: 32, height: 32, borderRadius: '50%', flexShrink: 0,
                      background: msg.sender_type === 'agent' ? 'var(--accent-primary-glow)' : 'var(--bg-elevated)',
                      border: `1px solid ${msg.sender_type === 'agent' ? 'var(--accent-primary)' : 'var(--border)'}`,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: 14,
                    }}>
                      {msg.sender_type === 'agent' ? '👨‍💼' : '👤'}
                    </div>
                    <div style={{ flex: 1, maxWidth: '75%' }}>
                      <div style={{
                        fontSize: 11, color: 'var(--text-muted)', marginBottom: 4,
                        textAlign: msg.sender_type === 'agent' ? 'right' : 'left',
                      }}>
                        {msg.sender_type === 'agent' ? 'Support Agent' : 'Customer'} · {formatDate(msg.sent_at)}
                      </div>
                      <div style={{
                        background: msg.sender_type === 'agent' ? 'var(--accent-primary-glow)' : 'var(--bg-elevated)',
                        border: `1px solid ${msg.sender_type === 'agent' ? 'rgba(79,127,255,0.2)' : 'var(--border)'}`,
                        borderRadius: msg.sender_type === 'agent' ? '12px 4px 12px 12px' : '4px 12px 12px 12px',
                        padding: '10px 14px',
                        fontSize: 13,
                        color: 'var(--text-secondary)',
                        lineHeight: 1.6,
                      }}>
                        {msg.body}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Timeline Tab */}
      {activeTab === 'timeline' && (
        <div className="card">
          <div className="card-header"><div className="card-title">📅 Status Timeline</div></div>
          <div className="card-body">
            {!complaint.status_events?.length ? (
              <div className="empty-state"><div className="empty-state-icon">📅</div><h3>No events</h3></div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
                {complaint.status_events.map((ev, i) => (
                  <div key={i} style={{ display: 'flex', gap: 16, position: 'relative' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                      <div style={{
                        width: 12, height: 12, borderRadius: '50%',
                        background: 'var(--accent-primary)', border: '2px solid var(--bg-card)',
                        flexShrink: 0, marginTop: 2,
                      }} />
                      {i < complaint.status_events.length - 1 && (
                        <div style={{ width: 1, flex: 1, background: 'var(--border)', minHeight: 24 }} />
                      )}
                    </div>
                    <div style={{ paddingBottom: i < complaint.status_events.length - 1 ? 20 : 0 }}>
                      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>
                        {formatDate(ev.occurred_at)}
                      </div>
                      <div style={{ fontSize: 13, color: 'var(--text-primary)', fontWeight: 500 }}>
                        {ev.from_status ? (
                          <>{ev.from_status} → {ev.to_status}</>
                        ) : (
                          <>Created as {ev.to_status}</>
                        )}
                      </div>
                      {ev.reason && (
                        <div style={{ fontSize: 12, color: 'var(--text-muted)', fontStyle: 'italic', marginTop: 2 }}>{ev.reason}</div>
                      )}
                      {ev.changed_by && (
                        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>by {ev.changed_by}</div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Resolution Tab */}
      {activeTab === 'resolution' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {complaint.resolutions && complaint.resolutions.length > 0 ? (
            complaint.resolutions.map((res, i) => (
              <div key={i} className="card">
                <div className="card-header"><div className="card-title">✅ Resolution #{i + 1}</div></div>
                <div className="card-body">
                  <div className="detail-grid">
                    <DetailField label="Type" value={
                      <span style={{ textTransform: 'capitalize' }}>{res.resolution_type?.replace(/_/g, ' ')}</span>
                    } />
                    <DetailField label="Resolved At" value={formatDate(res.resolved_at)} />
                    {res.refund_amount && (
                      <DetailField label="Refund Amount" value={`$${res.refund_amount}`} />
                    )}
                  </div>
                  {res.description && (
                    <div style={{ marginTop: 12 }}>
                      <div className="detail-field-label" style={{ marginBottom: 6 }}>Description</div>
                      <div style={{
                        background: 'var(--bg-surface)', border: '1px solid var(--border)',
                        borderRadius: 8, padding: '10px 14px', fontSize: 13, color: 'var(--text-secondary)',
                      }}>{res.description}</div>
                    </div>
                  )}
                </div>
              </div>
            ))
          ) : (
            <div className="card">
              <div className="card-body">
                <div className="empty-state"><div className="empty-state-icon">⏳</div><h3>Not yet resolved</h3></div>
              </div>
            </div>
          )}

          {complaint.surveys && complaint.surveys.length > 0 && (
            <div className="card">
              <div className="card-header"><div className="card-title">⭐ Customer Survey</div></div>
              <div className="card-body">
                {complaint.surveys.map((survey, i) => (
                  <div key={i}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
                      <div style={{ fontSize: 36, fontWeight: 800, color: survey.rating >= 4 ? 'var(--accent-emerald)' : survey.rating >= 3 ? 'var(--accent-amber)' : 'var(--p1)' }}>
                        {survey.rating}/5
                      </div>
                      <div>
                        {'★'.repeat(survey.rating)}{'☆'.repeat(5 - survey.rating)}
                      </div>
                      <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{formatDate(survey.submitted_at)}</div>
                    </div>
                    {survey.feedback && (
                      <div style={{
                        background: 'var(--bg-surface)', border: '1px solid var(--border)',
                        borderRadius: 8, padding: '10px 14px', fontSize: 13, color: 'var(--text-secondary)', fontStyle: 'italic',
                      }}>"{survey.feedback}"</div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
