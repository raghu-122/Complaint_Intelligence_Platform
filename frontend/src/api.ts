import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

// Types
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface DashboardStats {
  total_complaints: number;
  open_complaints: number;
  in_progress_complaints: number;
  resolved_complaints: number;
  closed_complaints: number;
  escalated_complaints: number;
  reopened_complaints: number;
  p1_complaints: number;
  safety_incidents: number;
  sla_breached_count: number;
  sla_compliance_rate: number;
  avg_resolution_time_hours: number;
  csat_average: number;
  total_customers: number;
  total_orders: number;
  vulnerable_customers_count: number;
  active_agents_count: number;
}

export interface ChartData {
  category_breakdown: { name: string; value: number; code: string }[];
  priority_breakdown: { name: string; value: number; code: string; color: string }[];
  status_breakdown: { name: string; value: number; code: string }[];
  daily_trends: { date: string; count: number }[];
  sla_stats: { priority: string; total: number; breached: number; compliance_pct: number }[];
}

export interface ComplaintListItem {
  complaint_id: string;
  subject: string;
  status: string;
  priority: string;
  category_code: string;
  channel: string;
  sentiment: string;
  is_safety_incident: boolean;
  is_escalated: boolean;
  is_anomaly: boolean;
  customer_name?: string;
  customer_id: string;
  order_id?: string;
  created_at: string;
  resolved_at?: string;
  sla_status?: string;
}

export interface ComplaintDetail extends ComplaintListItem {
  description: string;
  classification_confidence: number;
  classification_evidence?: string;
  priority_rule_applied?: string;
  priority_explanation?: string;
  sentiment_score?: number;
  is_refund_pending: boolean;
  is_reopened: boolean;
  reopen_count: number;
  closed_at?: string;
  customer?: { customer_id: string; name: string; email: string; account_tier: string; vulnerability_flag: boolean };
  order?: { order_id: string; total_amount: string; status: string; ordered_at: string };
  category?: { code: string; name: string; safety_risk: boolean };
  current_assignment?: { agent_name: string; team_name: string; assigned_at: string };
  sla_clock?: { priority: string; resolution_hours: number; is_breached: boolean; status: string; original_deadline: string };
  status_events: { from_status?: string; to_status: string; changed_by?: string; reason?: string; occurred_at: string }[];
  messages: { message_id: string; sender_type: string; body: string; sent_at: string; is_customer_visible: boolean }[];
  resolutions: { resolution_type: string; description: string; refund_amount?: string; resolved_at: string }[];
  surveys: { rating: number; feedback?: string; submitted_at: string }[];
}

export interface CustomerListItem {
  customer_id: string;
  first_name: string;
  last_name: string;
  email: string;
  account_tier: string;
  vulnerability_flag: boolean;
  is_active: boolean;
  complaint_count: number;
  created_at: string;
}

export interface ProductListItem {
  product_id: string;
  name: string;
  category: string;
  brand: string;
  unit_price: number;
  is_active: boolean;
  is_safety_flagged: boolean;
}

export interface TeamListItem {
  id: number;
  team_id: string;
  code: string;
  name: string;
  specializations: string[];
  agent_count: number;
  is_active: boolean;
}

export interface AnomalyItem {
  anomaly_id: string;
  anomaly_type: string;
  description: string;
  severity: string;
  complaint_id?: string;
  table_name?: string;
  evidence?: Record<string, unknown>;
  is_ground_truth: boolean;
  detected_at?: string;
}

export interface AnomalyDetectionResult {
  detected_count: number;
  ground_truth_count: number;
  precision: number;
  recall: number;
  f1_score: number;
  anomalies: AnomalyItem[];
}

export interface ValidationFinding {
  category: string;
  check_name: string;
  status: 'pass' | 'warn' | 'fail';
  message: string;
  record_id?: string;
  table_name?: string;
  details?: Record<string, unknown>;
}

export interface ValidationReport {
  summary: { passed: number; warned: number; failed: number; total: number; execution_time_seconds: number };
  findings: ValidationFinding[];
  generated_at: string;
}

export interface GenerateRequest {
  seed?: number;
  scale?: 'starter' | 'full';
  clear_existing?: boolean;
  export_baseline?: boolean;
}

export interface GenerateResponse {
  status: string;
  run_id: string;
  seed: number;
  scale: string;
  duration_seconds: number;
  counts: Record<string, number>;
  message: string;
}

// API functions
export const apiClient = {
  getDashboardStats: () => api.get<DashboardStats>('/api/v1/dashboard/stats'),
  getDashboardCharts: () => api.get<ChartData>('/api/v1/dashboard/charts'),

  getComplaints: (params?: Record<string, unknown>) =>
    api.get<PaginatedResponse<ComplaintListItem>>('/api/v1/complaints', { params }),
  getComplaint: (id: string) => api.get<ComplaintDetail>(`/api/v1/complaints/${id}`),

  getCustomers: (params?: Record<string, unknown>) =>
    api.get<PaginatedResponse<CustomerListItem>>('/api/v1/customers', { params }),

  getProducts: (params?: Record<string, unknown>) =>
    api.get<PaginatedResponse<ProductListItem>>('/api/v1/products', { params }),

  getTeams: () => api.get<{ items: TeamListItem[] }>('/api/v1/teams'),
  getAgents: (params?: Record<string, unknown>) => api.get('/api/v1/agents', { params }),

  getAnomalies: () => api.get<AnomalyDetectionResult>('/api/v1/anomalies'),
  injectAnomalies: (count: number) => api.post('/api/v1/anomalies/inject', { count }),

  getValidation: () => api.get<ValidationReport>('/api/v1/validate'),

  generateData: (req: GenerateRequest) => api.post<GenerateResponse>('/api/v1/generate', req),

  getReports: () => api.get('/api/v1/reports'),

  getHealth: () => api.get('/health'),
};
