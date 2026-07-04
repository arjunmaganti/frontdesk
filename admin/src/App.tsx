import React, { useState, useEffect } from 'react';
import { supabase } from './supabase';
import Papa from 'papaparse';
import {
  LayoutDashboard,
  UserPlus,
  Building2,
  FileText,
  UploadCloud,
  ArrowRight,
  ShieldAlert,
  Loader
} from 'lucide-react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer
} from 'recharts';

interface Business {
  business_id: string;
  business_name: string;
  agent_name: string;
  website_url: string;
  business_phone: string | null;
  business_address: string | null;
  business_email: string | null;
  flyer_url: string | null;
  owner_qr_url: string | null;
}

interface CrawlJob {
  id: string;
  business_id: string;
  website_url: string;
  status: string;
  error_message: string | null;
  created_at: string;
}

interface Escalation {
  visitor_chat_id: string;
  pending_question: string;
  business_id: string;
  business_name?: string;
}

interface UsageData {
  usage_date: string;
  message_count: number;
}

export default function App() {
  const [activeTab, setActiveTab] = useState<'dashboard' | 'onboarding'>('dashboard');
  const [loading, setLoading] = useState<boolean>(true);
  
  // Data States
  const [salons, setSalons] = useState<Business[]>([]);
  const [crawlJobs, setCrawlJobs] = useState<CrawlJob[]>([]);
  const [escalations, setEscalations] = useState<Escalation[]>([]);
  const [usageTrends, setUsageTrends] = useState<UsageData[]>([]);
  
  // Form States
  const [newSalon, setNewSalon] = useState({
    business_id: '',
    business_name: '',
    agent_name: 'Sarah',
    website_url: '',
    business_phone: '',
    business_address: '',
    business_email: '',
    map_url: ''
  });
  
  // Feedback Messages
  const [formMsg, setFormMsg] = useState<{ type: 'success' | 'error', text: string } | null>(null);
  const [csvMsg, setCsvMsg] = useState<{ type: 'success' | 'error', text: string } | null>(null);

  // Load Database Metrics
  const loadData = async () => {
    try {
      setLoading(true);
      
      // A. Load Salons
      const { data: bData } = await supabase
        .from('businesses')
        .select('business_id, business_name, agent_name, website_url, business_phone, business_address, business_email, flyer_url, owner_qr_url');
      setSalons(bData || []);

      // B. Load Recent Crawl Jobs
      const { data: cData } = await supabase
        .from('crawl_jobs')
        .select('id, business_id, website_url, status, error_message, created_at')
        .order('created_at', { ascending: false })
        .limit(6);
      setCrawlJobs(cData || []);

      // C. Load Active Escalations (where AI is paused)
      const { data: rData } = await supabase
        .from('admin_relay')
        .select('visitor_chat_id, pending_question, business_id')
        .eq('is_paused', true);
        
      const mappedEscalations = (rData || []).map(esc => {
        const match = (bData || []).find(b => b.business_id === esc.business_id);
        return {
          ...esc,
          business_name: match ? match.business_name : esc.business_id
        };
      });
      setEscalations(mappedEscalations);

      // D. Load Daily Usage Trends
      const { data: uData } = await supabase
        .from('daily_usage')
        .select('usage_date, message_count')
        .order('usage_date', { ascending: true })
        .limit(14);
        
      setUsageTrends(uData || []);

    } catch (err: any) {
      console.error("Error loading metrics:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    // Auto-refresh stats every 15 seconds
    const interval = setInterval(loadData, 15000);
    return () => clearInterval(interval);
  }, []);

  // Form Submit (Manual Single Salon)
  const handleSingleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormMsg(null);
    
    // Simple Validation
    if (!newSalon.business_id || !newSalon.business_name || !newSalon.website_url) {
      setFormMsg({ type: 'error', text: 'Please fill in the ID, Name, and Website URL.' });
      return;
    }

    try {
      // Ingest into business_load
      const { error } = await supabase.from('business_load').insert([{
        business_id: newSalon.business_id.trim().toLowerCase(),
        business_name: newSalon.business_name.trim(),
        agent_name: newSalon.agent_name.trim(),
        website_url: newSalon.website_url.trim(),
        business_phone: newSalon.business_phone.trim() || null,
        business_address: newSalon.business_address.trim() || null,
        business_email: newSalon.business_email.trim() || null,
        map_url: newSalon.map_url.trim() || null,
        status: 'pending'
      }]);

      if (error) throw error;

      setFormMsg({ type: 'success', text: `Successfully registered ${newSalon.business_name}! Scraper triggered.` });
      setNewSalon({
        business_id: '',
        business_name: '',
        agent_name: 'Sarah',
        website_url: '',
        business_phone: '',
        business_address: '',
        business_email: '',
        map_url: ''
      });
      loadData();
    } catch (err: any) {
      setFormMsg({ type: 'error', text: `Failed: ${err.message}` });
    }
  };

  // CSV Drag and Drop / File Input Handler
  const handleCsvUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    setCsvMsg(null);
    const file = e.target.files?.[0];
    if (!file) return;

    Papa.parse(file, {
      header: true,
      skipEmptyLines: true,
      complete: async (results) => {
        try {
          // Parse columns mapping and clean values
          const cleanRows = results.data.map((row: any) => ({
            business_id: (row.business_id || row.id || '').trim().toLowerCase(),
            business_name: (row.business_name || row.name || '').trim(),
            agent_name: (row.agent_name || 'Sarah').trim(),
            website_url: (row.website_url || row.website || '').trim(),
            business_phone: (row.business_phone || row.phone || '').trim() || null,
            business_address: (row.business_address || row.address || '').trim() || null,
            business_email: (row.business_email || row.email || '').trim() || null,
            map_url: (row.map_url || '').trim() || null,
            status: 'pending'
          })).filter(row => row.business_id && row.business_name && row.website_url);

          if (cleanRows.length === 0) {
            setCsvMsg({ type: 'error', text: 'No valid rows found in CSV. Required headers: business_id, business_name, website_url.' });
            return;
          }

          // Insert array into business_load
          const { error } = await supabase.from('business_load').insert(cleanRows);
          if (error) throw error;

          setCsvMsg({ type: 'success', text: `Successfully imported ${cleanRows.length} salons! Scraper queue updated.` });
          loadData();
        } catch (err: any) {
          setCsvMsg({ type: 'error', text: `CSV Import failed: ${err.message}` });
        }
      },
      error: (err) => {
        setCsvMsg({ type: 'error', text: `CSV parsing error: ${err.message}` });
      }
    });
  };

  return (
    <div className="app-container">
      {/* 1. Sidebar Navigation */}
      <aside className="sidebar">
        <div className="brand-header">
          <Building2 size={28} style={{ color: '#6366F1' }} />
          <h1 className="brand-header brand-logo">frontdesk</h1>
        </div>
        <nav className="nav-links">
          <button 
            className={`nav-btn ${activeTab === 'dashboard' ? 'active' : ''}`}
            onClick={() => setActiveTab('dashboard')}
          >
            <LayoutDashboard size={18} />
            SaaS Dashboard
          </button>
          <button 
            className={`nav-btn ${activeTab === 'onboarding' ? 'active' : ''}`}
            onClick={() => setActiveTab('onboarding')}
          >
            <UserPlus size={18} />
            Onboard Salons
          </button>
        </nav>
      </aside>

      {/* 2. Main content block */}
      <main className="main-content">
        
        {/* Dynamic Page Header */}
        <header className="page-header">
          <div>
            <h2 className="page-title">{activeTab === 'dashboard' ? 'SaaS Management Dashboard' : 'Salon Onboarding Panel'}</h2>
            <p className="page-subtitle">
              {activeTab === 'dashboard' 
                ? 'Real-time performance metrics and pipeline monitoring' 
                : 'Bulk load or register salon profiles into staging'}
            </p>
          </div>
          {loading && <Loader size={20} className="animate-spin text-mute" style={{ animation: 'spin 1s linear infinite' }} />}
        </header>

        {/* ================= TAB 1: DASHBOARD ================= */}
        {activeTab === 'dashboard' && (
          <>
            {/* KPI Metric Grid */}
            <div className="metrics-grid">
              <div className="metric-card">
                <div className="metric-info">
                  <span className="metric-label">Active Salons</span>
                  <span className="metric-val">{salons.length}</span>
                </div>
                <div className="metric-icon indigo">
                  <Building2 size={24} />
                </div>
              </div>
              
              <div className="metric-card">
                <div className="metric-info">
                  <span className="metric-label">Live Handoff Takeovers</span>
                  <span className="metric-val">{escalations.length}</span>
                </div>
                <div className="metric-icon rose">
                  <ShieldAlert size={24} />
                </div>
              </div>

              <div className="metric-card">
                <div className="metric-info">
                  <span className="metric-label">Completed Scrapes</span>
                  <span className="metric-val">
                    {crawlJobs.filter(j => j.status === 'completed').length}
                  </span>
                </div>
                <div className="metric-icon emerald">
                  <FileText size={24} />
                </div>
              </div>

              <div className="metric-card">
                <div className="metric-info">
                  <span className="metric-label">AI Queue Health</span>
                  <span className="metric-val">
                    {crawlJobs.filter(j => j.status === 'pending' || j.status === 'processing').length} Active
                  </span>
                </div>
                <div className="metric-icon gold">
                  <Loader size={24} />
                </div>
              </div>
            </div>

            {/* Trends, Escalations, and Queue Layout */}
            <div className="sections-grid">
              
              {/* Daily Conversations Trend Chart */}
              <div className="section-card">
                <h3 className="section-title">Daily Messages & Conversations Volume</h3>
                <div className="chart-container">
                  {usageTrends.length > 0 ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={usageTrends} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                        <defs>
                          <linearGradient id="colorUsage" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#6366F1" stopOpacity={0.4}/>
                            <stop offset="95%" stopColor="#6366F1" stopOpacity={0}/>
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                        <XAxis dataKey="usage_date" stroke="#9CA3AF" style={{ fontSize: '11px' }} />
                        <YAxis stroke="#9CA3AF" style={{ fontSize: '11px' }} />
                        <Tooltip contentStyle={{ backgroundColor: '#111827', borderColor: 'rgba(255,255,255,0.1)', color: '#F3F4F6' }} />
                        <Area type="monotone" dataKey="message_count" name="AI Messages" stroke="#6366F1" strokeWidth={2} fillOpacity={1} fill="url(#colorUsage)" />
                      </AreaChart>
                    </ResponsiveContainer>
                  ) : (
                    <div style={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center', color: '#9CA3AF' }}>
                      No trend data captured yet.
                    </div>
                  )}
                </div>
              </div>

              {/* Live Handoff Panel */}
              <div className="section-card" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <h3 className="section-title">Active Handoff Takeovers</h3>
                <div className="escalations-list">
                  {escalations.length > 0 ? (
                    escalations.map((esc, i) => (
                      <div className="escalation-item" key={i}>
                        <div className="escalation-meta">
                          <span style={{ fontWeight: 600, color: '#C5A880' }}>{esc.business_name}</span>
                          <span>Chat ID: {esc.visitor_chat_id}</span>
                        </div>
                        <p className="escalation-msg">"{esc.pending_question}"</p>
                      </div>
                    ))
                  ) : (
                    <div style={{ padding: '2rem', textAlign: 'center', color: '#9CA3AF' }}>
                      <p>✅ All visitor chats are cleanly handled by the AI.</p>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Recent Crawl Jobs Queue Table */}
            <div className="section-card">
              <h3 className="section-title">Background Crawl Queue Status</h3>
              <div className="table-wrapper">
                <table>
                  <thead>
                    <tr>
                      <th>Salon ID</th>
                      <th>Scraped Website URL</th>
                      <th>Crawl Status</th>
                      <th>Created At</th>
                      <th>Error Logs</th>
                    </tr>
                  </thead>
                  <tbody>
                    {crawlJobs.map((job) => (
                      <tr key={job.id}>
                        <td style={{ fontWeight: 600 }}>{job.business_id}</td>
                        <td><code>{job.website_url}</code></td>
                        <td>
                          <span className={`badge ${job.status}`}>
                            {job.status}
                          </span>
                        </td>
                        <td>{new Date(job.created_at).toLocaleTimeString()}</td>
                        <td style={{ color: '#EF4444', fontSize: '0.85rem' }}>{job.error_message || '--'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}

        {/* ================= TAB 2: ONBOARDING ================= */}
        {activeTab === 'onboarding' && (
          <div className="onboarding-grid">
            
            {/* Single Salon Form */}
            <div className="section-card">
              <h3 className="section-title">Register Single Salon</h3>
              
              {formMsg && (
                <div style={{ padding: '1rem', borderRadius: '8px', marginBottom: '1.5rem', backgroundColor: formMsg.type === 'success' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)', color: formMsg.type === 'success' ? '#10B981' : '#EF4444', fontSize: '0.9rem' }}>
                  {formMsg.text}
                </div>
              )}

              <form onSubmit={handleSingleSubmit}>
                <div className="form-row">
                  <div className="form-group">
                    <label>Unique Business ID (Slug)*</label>
                    <input 
                      type="text" 
                      placeholder="e.g. dmhaircare"
                      value={newSalon.business_id}
                      onChange={(e) => setNewSalon({ ...newSalon, business_id: e.target.value })}
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label>Salon Name*</label>
                    <input 
                      type="text" 
                      placeholder="e.g. DM Hair Care"
                      value={newSalon.business_name}
                      onChange={(e) => setNewSalon({ ...newSalon, business_name: e.target.value })}
                      required
                    />
                  </div>
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label>AI Assistant Name</label>
                    <input 
                      type="text" 
                      placeholder="e.g. Sarah"
                      value={newSalon.agent_name}
                      onChange={(e) => setNewSalon({ ...newSalon, agent_name: e.target.value })}
                    />
                  </div>
                  <div className="form-group">
                    <label>Website URL (To Scrape)*</label>
                    <input 
                      type="url" 
                      placeholder="https://example.com"
                      value={newSalon.website_url}
                      onChange={(e) => setNewSalon({ ...newSalon, website_url: e.target.value })}
                      required
                    />
                  </div>
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label>Verified Phone (Override)</label>
                    <input 
                      type="text" 
                      placeholder="+14080001111"
                      value={newSalon.business_phone}
                      onChange={(e) => setNewSalon({ ...newSalon, business_phone: e.target.value })}
                    />
                  </div>
                  <div className="form-group">
                    <label>Verified Email (Override)</label>
                    <input 
                      type="email" 
                      placeholder="contact@example.com"
                      value={newSalon.business_email}
                      onChange={(e) => setNewSalon({ ...newSalon, business_email: e.target.value })}
                    />
                  </div>
                </div>

                <div className="form-group">
                  <label>Verified Address (Override)</label>
                  <input 
                    type="text" 
                    placeholder="123 Salon Way, San Jose, CA"
                    value={newSalon.business_address}
                    onChange={(e) => setNewSalon({ ...newSalon, business_address: e.target.value })}
                  />
                </div>

                <div className="form-group">
                  <label>Google Maps Link (Override)</label>
                  <input 
                    type="url" 
                    placeholder="https://maps.google.com/..."
                    value={newSalon.map_url}
                    onChange={(e) => setNewSalon({ ...newSalon, map_url: e.target.value })}
                  />
                </div>

                <button type="submit" className="submit-btn" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', marginTop: '1rem' }}>
                  Register and Start Crawling
                  <ArrowRight size={18} />
                </button>
              </form>
            </div>

            {/* CSV Import Zone */}
            <div className="section-card" style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              <h3 className="section-title">Bulk Import via CSV</h3>
              <p style={{ fontSize: '0.9rem', color: 'var(--text-mute)', lineHeight: '1.5' }}>
                Load multiple salon profiles directly into the system. The file must contain headers: 
                <code>business_id</code>, <code>business_name</code>, and <code>website_url</code>.
              </p>
              
              {csvMsg && (
                <div style={{ padding: '1rem', borderRadius: '8px', backgroundColor: csvMsg.type === 'success' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)', color: csvMsg.type === 'success' ? '#10B981' : '#EF4444', fontSize: '0.9rem' }}>
                  {csvMsg.text}
                </div>
              )}

              <label htmlFor="csv-input" className="upload-zone">
                <UploadCloud size={48} className="upload-icon" />
                <div>
                  <p style={{ fontWeight: 600, fontSize: '0.95rem', marginBottom: '0.25rem' }}>Click to select CSV File</p>
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-mute)' }}>File formats supported: .csv</p>
                </div>
                <input 
                  id="csv-input" 
                  type="file" 
                  accept=".csv" 
                  onChange={handleCsvUpload} 
                  style={{ display: 'none' }} 
                />
              </label>

              {/* Sample Template */}
              <div style={{ marginTop: '1.5rem', border: '1px solid var(--border-card)', padding: '1.25rem', borderRadius: '8px', backgroundColor: 'rgba(255,255,255,0.01)' }}>
                <h4 style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: '#C5A880' }}>Sample CSV Structure:</h4>
                <pre style={{ fontFamily: 'monospace', fontSize: '0.75rem', color: '#9CA3AF', whiteSpace: 'pre-wrap', lineHeight: '1.6' }}>
                  business_id,business_name,website_url,business_phone,business_address{"\n"}
                  simbiz,Sim Salon,https://example.com,+14080001111,"123 Main St"{"\n"}
                  glowhair,Glow Hair Studio,https://glowstudio.com,,
                </pre>
              </div>
            </div>

          </div>
        )}

      </main>
    </div>
  );
}
