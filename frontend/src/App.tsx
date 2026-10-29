import { BrowserRouter, Routes, Route, NavLink, useLocation } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Complaints from './pages/Complaints';
import ComplaintDetail from './pages/ComplaintDetail';
import Customers from './pages/Customers';
import Anomalies from './pages/Anomalies';
import Validation from './pages/Validation';
import Reports from './pages/Reports';
import Ingestion from './pages/Ingestion';
import './index.css';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const NAV_ITEMS = [
  { to: '/', icon: '📊', label: 'Dashboard', exact: true },
  { to: '/complaints', icon: '📋', label: 'Complaints' },
  { to: '/customers', icon: '👥', label: 'Customers' },
  { to: '/anomalies', icon: '🔍', label: 'Anomaly Detection' },
  { to: '/validation', icon: '✅', label: 'Validation' },
  { to: '/reports', icon: '📁', label: 'Reports' },
  { to: '/ingestion', icon: '📥', label: 'Data Ingestion' },
];

function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="brand-logo">
          <div className="brand-icon">🧠</div>
          <div>
            <div className="brand-name">YottaFlex AI</div>
          </div>
        </div>
        <div className="brand-tagline">Complaint Intelligence Platform</div>
      </div>

      <nav className="sidebar-nav">
        <div className="nav-section">
          <div className="nav-section-label">Platform</div>
          {NAV_ITEMS.map(({ to, icon, label, exact }) => (
            <NavLink
              key={to}
              to={to}
              end={exact}
              className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
            >
              <span className="nav-item-icon">{icon}</span>
              {label}
            </NavLink>
          ))}
        </div>

        <div className="nav-section">
          <div className="nav-section-label">Reference</div>
          <a
            href={`${API_BASE}/docs`}
            target="_blank"
            rel="noreferrer"
            className="nav-item"
          >
            <span className="nav-item-icon">📖</span>
            API Docs
          </a>
          <a
            href={`${API_BASE}/health`}
            target="_blank"
            rel="noreferrer"
            className="nav-item"
          >
            <span className="nav-item-icon">💚</span>
            Health Check
          </a>
        </div>
      </nav>

      <div className="sidebar-footer">
        <div className="sidebar-status">
          <div className="status-dot" />
          <span>API: {new URL(API_BASE).hostname}</span>
        </div>
      </div>
    </aside>
  );
}

function Topbar() {
  const location = useLocation();
  const titleMap: Record<string, { title: string; desc: string }> = {
    '/': { title: 'Dashboard', desc: 'Real-time complaint intelligence overview' },
    '/complaints': { title: 'Complaints', desc: 'Browse, filter, and manage all complaints' },
    '/customers': { title: 'Customers', desc: 'Customer profiles and complaint history' },
    '/anomalies': { title: 'Anomaly Detection', desc: 'Detected data quality and behavioral anomalies' },
    '/validation': { title: 'Validation Report', desc: 'Schema, chronology, and business rule checks' },
    '/reports': { title: 'Reports', desc: 'Export datasets and evaluation reports' },
    '/ingestion': { title: 'Data Ingestion', desc: 'Upload CSV/JSON records with validation and deduplication' },
  };

  const path = location.pathname.startsWith('/complaints/') ? '/complaints' : location.pathname;
  const info = titleMap[path] || { title: 'Complaint Intelligence', desc: '' };

  return (
    <header className="topbar">
      <div className="topbar-title">
        <h1>{info.title}</h1>
        {info.desc && <p>{info.desc}</p>}
      </div>
      <div className="topbar-actions">
        <div className="topbar-chip">
          <span>Seed</span>
          <span className="chip-label">20261022</span>
        </div>
        <div className="topbar-chip">
          <span>DB</span>
          <span className="chip-label">SQLite</span>
        </div>
      </div>
    </header>
  );
}

function AppLayout() {
  return (
    <div className="layout">
      <Sidebar />
      <div className="main-content">
        <Topbar />
        <main className="page-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/complaints" element={<Complaints />} />
            <Route path="/complaints/:id" element={<ComplaintDetail />} />
            <Route path="/customers" element={<Customers />} />
            <Route path="/anomalies" element={<Anomalies />} />
            <Route path="/validation" element={<Validation />} />
            <Route path="/reports" element={<Reports />} />
            <Route path="/ingestion" element={<Ingestion />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppLayout />
    </BrowserRouter>
  );
}
