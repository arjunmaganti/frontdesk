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
  Loader,
  Bot,
  Trash2,
  Search,
  ExternalLink
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
  business_timezone: string;
  admin_chat_id: string | null;
  created_at: string;
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

function FrontdeskLogo() {
  return (
    <div className="logo-container" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', padding: '1rem 0', width: '100%', marginBottom: '0.5rem' }}>
      <svg width="110" height="110" viewBox="0 0 200 200" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ marginBottom: '0.5rem' }}>
        <defs>
          <linearGradient id="logo-grad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#00D2FF" />
            <stop offset="100%" stopColor="#0066EB" />
          </linearGradient>
          <linearGradient id="logo-grad-dark" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#0A1C30" />
            <stop offset="100%" stopColor="#1E3E62" />
          </linearGradient>
        </defs>
        
        {/* Outer Circular Ring */}
        <path d="M 45,130 A 60,60 0 1,1 152,116" fill="none" stroke="url(#logo-grad)" strokeWidth="6" strokeLinecap="round" />
        
        {/* Platter / Base */}
        <path d="M 40,126 C 40,126 100,140 160,126 C 160,131 140,140 100,140 C 60,140 40,131 40,126 Z" fill="#0A1C30" />
        
        {/* Robot Body */}
        {/* Torso */}
        <path d="M 68,126 C 68,110 132,110 132,126 Z" fill="url(#logo-grad-dark)" stroke="#0A1C30" strokeWidth="2.5" />
        {/* Shirt Front */}
        <path d="M 80,126 C 80,114 120,114 120,126 Z" fill="#FFFFFF" />
        {/* Bow tie */}
        <polygon points="90,117 97,121 90,125" fill="#0A1C30" />
        <polygon points="110,117 103,121 110,125" fill="#0A1C30" />
        <circle cx="100" cy="121" r="2.5" fill="#0A1C30" />
        {/* Shirt buttons */}
        <circle cx="100" cy="129" r="2" fill="#0A1C30" />
        <circle cx="100" cy="135" r="2" fill="#0A1C30" />
        
        {/* Neck */}
        <rect x="94" y="98" width="12" height="12" rx="3" fill="#FFFFFF" stroke="#0A1C30" strokeWidth="2.5" />
        
        {/* Head */}
        <rect x="70" y="55" width="60" height="48" rx="24" fill="#FFFFFF" stroke="#0A1C30" strokeWidth="4" />
        {/* Screen */}
        <rect x="76" y="63" width="48" height="28" rx="14" fill="#0A1C30" />
        {/* Eyes */}
        <circle cx="89" cy="77" r="4.5" fill="#00D2FF" />
        <circle cx="111" cy="77" r="4.5" fill="#00D2FF" />
        {/* Smile */}
        <path d="M 95,83 Q 100,87 105,83" stroke="#00D2FF" strokeWidth="2.5" strokeLinecap="round" fill="none" />
        
        {/* Headset Band */}
        <path d="M 72,70 A 28,28 0 0,1 128,70" fill="none" stroke="#0A1C30" strokeWidth="4" />
        {/* Ear Cups */}
        <rect x="67" y="70" width="7" height="18" rx="3.5" fill="#0A1C30" />
        <rect x="126" y="70" width="7" height="18" rx="3.5" fill="#0A1C30" />
        {/* Mic Arm */}
        <path d="M 126,83 Q 118,97 104,95" fill="none" stroke="#0A1C30" strokeWidth="3.5" strokeLinecap="round" />
        {/* Mic Tip */}
        <circle cx="104" cy="95" r="2" fill="#0A1C30" />
        
        {/* Service Bell */}
        <rect x="136" y="119" width="22" height="4" rx="1.5" fill="#0A1C30" />
        <path d="M 138,119 C 138,109 156,109 156,119 Z" fill="#0A1C30" stroke="#0A1C30" strokeWidth="1" />
        <rect x="146" y="105" width="2" height="4" fill="#0A1C30" />
        <ellipse cx="147" cy="105" rx="4" ry="2" fill="#0A1C30" />
        
        {/* Speech Bubble */}
        <path d="M 128,58 Q 130,50 134,48 L 140,53 Z" fill="url(#logo-grad)" />
        <circle cx="143" cy="42" r="16" fill="url(#logo-grad)" />
        {/* Three dots */}
        <circle cx="136" cy="42" r="2" fill="#FFFFFF" />
        <circle cx="143" cy="42" r="2" fill="#FFFFFF" />
        <circle cx="150" cy="42" r="2" fill="#FFFFFF" />
      </svg>
      
      {/* Brand Name Text */}
      <h2 style={{ fontSize: '1.25rem', fontWeight: 800, letterSpacing: '0.08em', color: '#FFFFFF', margin: 0, textTransform: 'uppercase', fontFamily: "'Outfit', sans-serif" }}>
        Frontdesk
      </h2>
      
      {/* Sub-label with lines */}
      <div style={{ display: 'flex', alignItems: 'center', width: '100%', margin: '0.2rem 0', justifyContent: 'center' }}>
        <div style={{ flex: 1, height: '1px', backgroundColor: 'rgba(0, 210, 255, 0.2)' }} />
        <span style={{ fontSize: '0.75rem', fontWeight: 600, letterSpacing: '0.15em', color: '#00D2FF', padding: '0 0.4rem', textTransform: 'uppercase', fontFamily: "'Outfit', sans-serif" }}>
          Expert
        </span>
        <div style={{ flex: 1, height: '1px', backgroundColor: 'rgba(0, 210, 255, 0.2)' }} />
      </div>
      
      {/* Tagline */}
      <span style={{ fontSize: '0.5rem', fontWeight: 500, letterSpacing: '0.05em', color: 'var(--text-mute)', textTransform: 'uppercase' }}>
        AI-Powered. Always Here. Always Helping.
      </span>
    </div>
  );
}

const API_BASE = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000/api";

export default function App() {
  const [session, setSession] = useState<any>(null);
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [loginErr, setLoginErr] = useState('');

  const [activeTab, setActiveTab] = useState<'dashboard' | 'onboarding' | 'simulator' | 'directory'>('dashboard');
  const [loading, setLoading] = useState<boolean>(true);

  // Simulator States
  const [selectedBusinessId, setSelectedBusinessId] = useState<string>('');
  const [chatMessages, setChatMessages] = useState<{ role: 'user' | 'assistant', content: string }[]>([]);
  const [chatInput, setChatInput] = useState<string>('');
  const [chatLoading, setChatLoading] = useState<boolean>(false);
  const [threadId, setThreadId] = useState<string>(() => Math.random().toString(36).substring(7));
  
  // Directory Search States
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedDirectoryBusinessId, setSelectedDirectoryBusinessId] = useState<string>('');
  const [selectedBusinessChunks, setSelectedBusinessChunks] = useState<any[]>([]);
  const [chunksLoading, setChunksLoading] = useState<boolean>(false);
  
  // Data States
  const [businesses, setBusinesses] = useState<Business[]>([]);
  const [crawlJobs, setCrawlJobs] = useState<CrawlJob[]>([]);
  const [escalations, setEscalations] = useState<Escalation[]>([]);
  const [usageTrends, setUsageTrends] = useState<UsageData[]>([]);
  
  // Form States
  const [newBusiness, setNewBusiness] = useState({
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
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);

  // Auth Listener
  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
    });

    return () => subscription.unsubscribe();
  }, []);

  // Helper to fetch endpoints with Supabase Auth session JWT token
  const authenticatedFetch = async (url: string, options: RequestInit = {}) => {
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token;
    
    const headers = new Headers(options.headers || {});
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
    
    return fetch(url, {
      ...options,
      headers
    });
  };

  // Load Database Metrics
  const loadData = async () => {
    try {
      setLoading(true);
      
      // A. Load Businesses
      const resB = await authenticatedFetch(`${API_BASE}/businesses`);
      const bData = resB.ok ? await resB.json() : [];
      setBusinesses(bData || []);

      // B. Load Recent Crawl Jobs
      const resC = await authenticatedFetch(`${API_BASE}/crawl-jobs`);
      const cData = resC.ok ? await resC.json() : [];
      setCrawlJobs(cData || []);

      // C. Load Active Escalations
      const resR = await authenticatedFetch(`${API_BASE}/admin-relay`);
      const rData = resR.ok ? await resR.json() : [];
        
      const mappedEscalations = (rData || []).map((esc: any) => {
        const match = (bData || []).find((b: any) => b.business_id === esc.business_id);
        return {
          ...esc,
          business_name: match ? match.business_name : esc.business_id
        };
      });
      setEscalations(mappedEscalations);

      // D. Load Daily Usage Trends
      const resU = await authenticatedFetch(`${API_BASE}/daily-usage`);
      const uData = resU.ok ? await resU.json() : [];
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

  // Simulator fetch functions
  const loadChatHistory = async (businessId: string, currentThreadId: string) => {
    if (!businessId) return;
    try {
      const response = await authenticatedFetch(`${API_BASE}/chat/history?business_id=${businessId}&thread_id=${currentThreadId}`);
      const data = await response.json();
      if (data.history && data.history.length > 0) {
        setChatMessages(data.history);
      } else {
        // Fallback to initial greeting
        const business = businesses.find(s => s.business_id === businessId);
        const agentName = business?.agent_name || 'Kim';
        const businessName = business?.business_name || 'this business';
        setChatMessages([
          { role: 'assistant', content: `👋 Hello! I am ${agentName}, your virtual concierge for ${businessName}. Ask me anything about our services, hours, or policies!` }
        ]);
      }
    } catch (err) {
      console.error("Error loading chat history:", err);
      // Fallback greeting
      const business = businesses.find(s => s.business_id === businessId);
      const agentName = business?.agent_name || 'Kim';
      const businessName = business?.business_name || 'this business';
      setChatMessages([
        { role: 'assistant', content: `👋 Hello! I am ${agentName}, your virtual concierge for ${businessName}. Ask me anything about our services, hours, or policies!` }
      ]);
    }
  };

  const handleSendMessage = async (messageText?: string) => {
    const textToSend = messageText || chatInput;
    if (!textToSend.trim() || !selectedBusinessId) return;
    
    // Add user message to state
    const userMsg = { role: 'user' as const, content: textToSend };
    setChatMessages(prev => [...prev, userMsg]);
    if (!messageText) setChatInput('');
    setChatLoading(true);
    
    try {
      const response = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          business_id: selectedBusinessId,
          message: textToSend,
          thread_id: threadId
        })
      });
      const data = await response.json();
      
      setChatMessages(prev => [...prev, { role: 'assistant', content: data.reply }]);
    } catch (err) {
      console.error("Chat simulator error:", err);
      setChatMessages(prev => [...prev, { role: 'assistant', content: "⚠️ Failed to connect to the Chat API. Please ensure the agent service is running." }]);
    } finally {
      setChatLoading(false);
    }
  };

  useEffect(() => {
    if (selectedBusinessId) {
      loadChatHistory(selectedBusinessId, threadId);
    } else if (businesses.length > 0) {
      setSelectedBusinessId(businesses[0].business_id);
    }
  }, [selectedBusinessId, threadId, businesses]);

  // Directory fetch functions
  const loadBusinessChunks = async (bizId: string) => {
    if (!bizId) return;
    try {
      setChunksLoading(true);
      const response = await authenticatedFetch(`${API_BASE}/knowledge-chunks?business_id=${bizId}`);
      if (!response.ok) throw new Error("Failed to load chunks");
      const data = await response.json();
      setSelectedBusinessChunks(data || []);
    } catch (err) {
      console.error("Error loading chunks:", err);
      setSelectedBusinessChunks([]);
    } finally {
      setChunksLoading(false);
    }
  };

  useEffect(() => {
    if (selectedDirectoryBusinessId) {
      loadBusinessChunks(selectedDirectoryBusinessId);
    } else if (businesses.length > 0) {
      setSelectedDirectoryBusinessId(businesses[0].business_id);
    }
  }, [selectedDirectoryBusinessId, businesses]);

  const formatPhoneNumber = (phone: string | null | undefined): string => {
    if (!phone) return '';
    let clean = phone.replace(/[^\d+]/g, '');
    if (!clean.startsWith('+')) {
      const digits = clean.replace(/\D/g, '');
      if (digits.length === 10) {
        clean = `+1${digits}`;
      } else if (digits.length === 11 && digits.startsWith('1')) {
        clean = `+${digits}`;
      } else if (digits.length >= 7 && digits.length <= 15) {
        clean = `+${digits}`;
      }
    }
    return clean;
  };

  const validatePhone = (phone: string | null | undefined): boolean => {
    if (!phone) return true;
    const cleanPhone = phone.replace(/[\s()-]/g, '');
    return /^\+?[1-9]\d{6,14}$/.test(cleanPhone);
  };

  const validateEmail = (email: string | null | undefined): boolean => {
    if (!email) return true;
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  };

  const validateField = (field: string, value: string) => {
    let err = '';
    if (field === 'business_name') {
      if (!value.trim()) err = 'Business Name is required.';
    } else if (field === 'website_url') {
      if (!value.trim()) {
        err = 'Website URL is required.';
      } else {
        try {
          new URL(value);
        } catch {
          err = 'Invalid URL format (e.g., https://example.com).';
        }
      }
    } else if (field === 'business_email') {
      if (value && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
        err = 'Invalid email address format (e.g., contact@example.com).';
      }
    } else if (field === 'business_phone') {
      if (value) {
        const clean = value.replace(/[\s()-]/g, '');
        if (!/^\+?[1-9]\d{6,14}$/.test(clean)) {
          err = 'Invalid phone format (must be 7-15 digits, e.g., +14085551212).';
        }
      }
    }
    setErrors(prev => ({ ...prev, [field]: err }));
  };

  // Form Submit (Manual Single Business)
  const handleSingleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormMsg(null);
    
    // Validate all fields on submit
    const nameErr = !newBusiness.business_name.trim() ? 'Business Name is required.' : '';
    let webErr = '';
    if (!newBusiness.website_url.trim()) {
      webErr = 'Website URL is required.';
    } else {
      try {
        new URL(newBusiness.website_url);
      } catch {
        webErr = 'Invalid URL format (e.g., https://example.com).';
      }
    }
    let emailErr = '';
    if (newBusiness.business_email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(newBusiness.business_email)) {
      emailErr = 'Invalid email address format (e.g., contact@example.com).';
    }
    let phoneErr = '';
    const formattedPhone = formatPhoneNumber(newBusiness.business_phone);
    if (formattedPhone) {
      if (!/^\+?[1-9]\d{6,14}$/.test(formattedPhone)) {
        phoneErr = 'Invalid phone format (must be 7-15 digits, e.g., +14085551212).';
      }
    }

    if (nameErr || webErr || emailErr || phoneErr) {
      setErrors({
        business_name: nameErr,
        website_url: webErr,
        business_email: emailErr,
        business_phone: phoneErr
      });
      return;
    }

    try {
      // Ingest into business_load via Proxy API
      const res = await authenticatedFetch(`${API_BASE}/business-load`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          business_id: newBusiness.business_id.trim().toLowerCase(),
          business_name: newBusiness.business_name.trim(),
          agent_name: newBusiness.agent_name.trim(),
          website_url: newBusiness.website_url.trim(),
          business_phone: formattedPhone || null,
          business_address: newBusiness.business_address.trim() || null,
          business_email: newBusiness.business_email.trim() || null,
          map_url: newBusiness.map_url.trim() || null,
          status: 'pending'
        })
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || "Failed to register business");
      }

      setFormMsg({ type: 'success', text: `Successfully registered ${newBusiness.business_name}! Scraper triggered.` });
      setErrors({});
      setNewBusiness({
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
          const cleanRows: any[] = [];
          const validationErrors: string[] = [];

          results.data.forEach((row: any, index: number) => {
            const name = (row.business_name || row.name || '').trim();
            const website = (row.website_url || row.website || '').trim();
            if (!name && !website) return; // Skip completely empty rows

            let slug = (row.business_id || row.id || '').trim().toLowerCase();
            if (!slug && name) {
              slug = name
                .toLowerCase()
                .replace(/[^\w\s-]/g, '')
                .trim()
                .replace(/[\s_]+/g, '-')
                .replace(/-+/g, '-');
            }

            const rawPhone = (row.business_phone || row.phone || '').trim();
            const phone = formatPhoneNumber(rawPhone) || null;
            const email = (row.business_email || row.email || '').trim() || null;

            // Run format validation
            const isEmailValid = validateEmail(email);
            const isPhoneValid = validatePhone(phone);

            if (!isEmailValid || !isPhoneValid) {
              const errors = [];
              if (!isEmailValid) errors.push(`invalid email format "${email}"`);
              if (!isPhoneValid) errors.push(`invalid phone format "${phone}"`);
              validationErrors.push(`Row ${index + 2} (${name || 'Unnamed'}): ${errors.join(', ')}`);
              return;
            }

            cleanRows.push({
              business_id: slug,
              business_name: name,
              agent_name: (row.agent_name || 'Sarah').trim(),
              website_url: website,
              business_phone: phone,
              business_address: (row.business_address || row.address || '').trim() || null,
              business_email: email,
              map_url: (row.map_url || '').trim() || null,
              status: 'pending'
            });
          });

          if (validationErrors.length > 0) {
            setCsvMsg({ 
              type: 'error', 
              text: `Import blocked. Found validation errors:\n${validationErrors.slice(0, 5).join('\n')}${validationErrors.length > 5 ? `\n...and ${validationErrors.length - 5} more errors.` : ''}` 
            });
            return;
          }

          if (cleanRows.length === 0) {
            setCsvMsg({ type: 'error', text: 'No valid rows found in CSV. Required headers: business_name, website_url.' });
            return;
          }

          // Insert array into business_load via Proxy API
          const res = await authenticatedFetch(`${API_BASE}/business-load`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(cleanRows)
          });
          if (!res.ok) {
            const errorData = await res.json();
            throw new Error(errorData.detail || "Failed to import rows");
          }

          setCsvMsg({ type: 'success', text: `Successfully imported ${cleanRows.length} businesses! Scraper queue updated.` });
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

  const executeDeleteBusiness = async (bizId: string) => {
    try {
      // 1. Delete from main businesses table via Proxy API
      const resBiz = await authenticatedFetch(`${API_BASE}/businesses/${bizId}`, {
        method: 'DELETE'
      });
      if (!resBiz.ok) {
        const errData = await resBiz.json();
        throw new Error(errData.detail || "Failed to delete business profile");
      }
      
      // 2. Also delete from business_load staging table via Proxy API
      const resLoad = await authenticatedFetch(`${API_BASE}/business-load/${bizId}`, {
        method: 'DELETE'
      });
      if (!resLoad.ok) {
        const errData = await resLoad.json();
        throw new Error(errData.detail || "Failed to delete business staging row");
      }

      // 3. Clear selections if the deleted business was currently selected
      if (selectedDirectoryBusinessId === bizId) {
        setSelectedDirectoryBusinessId('');
      }
      if (selectedBusinessId === bizId) {
        setSelectedBusinessId('');
      }

      loadData();
    } catch (err: any) {
      alert(`Delete failed: ${err.message}`);
    }
  };

  if (!session) {
    const handleLoginSubmit = async (e: React.FormEvent) => {
      e.preventDefault();
      setLoginErr('');
      try {
        const { error } = await supabase.auth.signInWithPassword({
          email: loginEmail,
          password: loginPassword
        });
        if (error) throw error;
      } catch (err: any) {
        setLoginErr(err.message || 'Login failed. Please check your credentials.');
      }
    };

    return (
      <div className="login-wrapper">
        <div className="login-card">
          <div className="login-header">
            <h1>Frontdesk</h1>
            <p>SaaS Admin Control Panel</p>
          </div>
          <form className="login-form" onSubmit={handleLoginSubmit}>
            {loginErr && <div className="login-error">{loginErr}</div>}
            <div className="login-group">
              <label className="login-label">Email Address</label>
              <input 
                type="email" 
                className="login-input" 
                placeholder="admin@example.com"
                value={loginEmail}
                onChange={e => setLoginEmail(e.target.value)}
                required
              />
            </div>
            <div className="login-group">
              <label className="login-label">Password</label>
              <input 
                type="password" 
                className="login-input" 
                placeholder="••••••••"
                value={loginPassword}
                onChange={e => setLoginPassword(e.target.value)}
                required
              />
            </div>
            <button type="submit" className="login-btn">Sign In</button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="app-container">
      {/* 1. Sidebar Navigation */}
      <aside className="sidebar">
        <FrontdeskLogo />
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
            Onboard Businesses
          </button>
          <button 
            className={`nav-btn ${activeTab === 'simulator' ? 'active' : ''}`}
            onClick={() => setActiveTab('simulator')}
          >
            <Bot size={18} />
            Chat Simulator
          </button>
          <button 
            className={`nav-btn ${activeTab === 'directory' ? 'active' : ''}`}
            onClick={() => setActiveTab('directory')}
          >
            <Search size={18} />
            Search Directory
          </button>
        </nav>
        <div style={{ marginTop: 'auto', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          <div style={{ padding: '0.5rem 1rem', fontSize: '0.8rem', color: 'var(--text-mute)', borderTop: '1px solid var(--border-card)', paddingTop: '1rem' }}>
            Logged in as:
            <div style={{ color: 'var(--text-main)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', marginTop: '0.2rem' }}>
              {session.user.email}
            </div>
          </div>
          <button 
            className="nav-btn" 
            style={{ color: 'var(--rose)', marginTop: '0.5rem' }} 
            onClick={() => supabase.auth.signOut()}
          >
            <ShieldAlert size={18} />
            Sign Out
          </button>
        </div>
      </aside>

      {/* 2. Main content block */}
      <main className="main-content">
        
        {/* Dynamic Page Header */}
        <header className="page-header">
          <div>
            <h2 className="page-title">
              {activeTab === 'dashboard' && 'SaaS Management Dashboard'}
              {activeTab === 'onboarding' && 'Business Onboarding Panel'}
              {activeTab === 'simulator' && 'AI Chat Simulator'}
              {activeTab === 'directory' && 'Business Support Directory'}
            </h2>
            <p className="page-subtitle">
              {activeTab === 'dashboard' && 'Real-time performance metrics and pipeline monitoring'}
              {activeTab === 'onboarding' && 'Bulk load or register business profiles into staging'}
              {activeTab === 'simulator' && 'Interact with and test your customer reception AI in real-time'}
              {activeTab === 'directory' && 'Search onboarded businesses, inspect crawled knowledge bases, and view assets'}
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
                  <span className="metric-label">Active Businesses</span>
                  <span className="metric-val">{businesses.length}</span>
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
                            <stop offset="5%" stopColor="#00D2FF" stopOpacity={0.4}/>
                            <stop offset="95%" stopColor="#0066EB" stopOpacity={0}/>
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                        <XAxis dataKey="usage_date" stroke="#9CA3AF" style={{ fontSize: '11px' }} />
                        <YAxis stroke="#9CA3AF" style={{ fontSize: '11px' }} />
                        <Tooltip contentStyle={{ backgroundColor: '#111827', borderColor: 'rgba(255,255,255,0.1)', color: '#F3F4F6' }} />
                        <Area type="monotone" dataKey="message_count" name="AI Messages" stroke="#00D2FF" strokeWidth={2} fillOpacity={1} fill="url(#colorUsage)" />
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
                          <span style={{ fontWeight: 600, color: '#00D2FF' }}>{esc.business_name}</span>
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
                      <th>Business ID</th>
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
            
            {/* Single Business Form */}
            <div className="section-card">
              <h3 className="section-title">Register Single Business</h3>
              
              {formMsg && (
                <div style={{ padding: '1rem', borderRadius: '8px', marginBottom: '1.5rem', backgroundColor: formMsg.type === 'success' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)', color: formMsg.type === 'success' ? '#10B981' : '#EF4444', fontSize: '0.9rem' }}>
                  {formMsg.text}
                </div>
              )}

              <form onSubmit={handleSingleSubmit} noValidate>
                <div className="form-row">
                  <div className="form-group">
                    <label>Business Name <span style={{ color: '#EF4444' }}>*</span></label>
                    <input 
                      type="text" 
                      placeholder="e.g. DM Hair Care"
                      value={newBusiness.business_name}
                      onChange={(e) => {
                        const name = e.target.value;
                        const slug = name
                          .toLowerCase()
                          .replace(/[^\w\s-]/g, '')
                          .trim()
                          .replace(/[\s_]+/g, '-')
                          .replace(/-+/g, '-');
                        setNewBusiness({ 
                          ...newBusiness, 
                          business_name: name,
                          business_id: slug
                        });
                      }}
                      onBlur={(e) => validateField('business_name', e.target.value)}
                      required
                    />
                    {errors.business_name && (
                      <span style={{ color: '#EF4444', fontSize: '0.75rem', marginTop: '0.35rem', display: 'block' }}>
                        {errors.business_name}
                      </span>
                    )}
                  </div>
                  <div className="form-group">
                    <label>Website URL (To Scrape) <span style={{ color: '#EF4444' }}>*</span></label>
                    <input 
                      type="url" 
                      placeholder="https://example.com"
                      value={newBusiness.website_url}
                      onChange={(e) => setNewBusiness({ ...newBusiness, website_url: e.target.value })}
                      onBlur={(e) => validateField('website_url', e.target.value)}
                      required
                    />
                    {errors.website_url && (
                      <span style={{ color: '#EF4444', fontSize: '0.75rem', marginTop: '0.35rem', display: 'block' }}>
                        {errors.website_url}
                      </span>
                    )}
                  </div>
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label>AI Assistant Name</label>
                    <input 
                      type="text" 
                      placeholder="e.g. Sarah"
                      value={newBusiness.agent_name}
                      onChange={(e) => setNewBusiness({ ...newBusiness, agent_name: e.target.value })}
                    />
                  </div>
                  <div className="form-group">
                    <label>Verified Phone</label>
                    <input 
                      type="text" 
                      placeholder="+14080001111"
                      value={newBusiness.business_phone}
                      onChange={(e) => setNewBusiness({ ...newBusiness, business_phone: e.target.value })}
                      onBlur={(e) => {
                        const formatted = formatPhoneNumber(e.target.value);
                        setNewBusiness(prev => ({ ...prev, business_phone: formatted }));
                        validateField('business_phone', formatted);
                      }}
                    />
                    {errors.business_phone && (
                      <span style={{ color: '#EF4444', fontSize: '0.75rem', marginTop: '0.35rem', display: 'block' }}>
                        {errors.business_phone}
                      </span>
                    )}
                  </div>
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label>Verified Email</label>
                    <input 
                      type="email" 
                      placeholder="contact@example.com"
                      value={newBusiness.business_email}
                      onChange={(e) => setNewBusiness({ ...newBusiness, business_email: e.target.value })}
                      onBlur={(e) => validateField('business_email', e.target.value)}
                    />
                    {errors.business_email && (
                      <span style={{ color: '#EF4444', fontSize: '0.75rem', marginTop: '0.35rem', display: 'block' }}>
                        {errors.business_email}
                      </span>
                    )}
                  </div>
                  <div className="form-group">
                    <label>Verified Address</label>
                    <input 
                      type="text" 
                      placeholder="123 Business Way, San Jose, CA"
                      value={newBusiness.business_address}
                      onChange={(e) => setNewBusiness({ ...newBusiness, business_address: e.target.value })}
                    />
                  </div>
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
                Load multiple business profiles directly into the system. Required headers: <code>business_name</code> and <code>website_url</code> (unique slug IDs are automatically generated).
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
                <h4 style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: '#00D2FF' }}>Sample CSV Structure:</h4>
                <pre style={{ fontFamily: 'monospace', fontSize: '0.75rem', color: '#9CA3AF', whiteSpace: 'pre-wrap', lineHeight: '1.6' }}>
                  business_name,website_url,agent_name,business_phone,business_email,business_address{"\n"}
                  Sim Business,https://example.com,Sarah,+14080001111,contact@simbiz.com,"123 Main St"{"\n"}
                  Glow Hair Studio,https://glowstudio.com,Emma,,,
                </pre>
              </div>
            </div>

          </div>
        )}

        {/* ================= TAB 3: CHAT SIMULATOR ================= */}
        {activeTab === 'simulator' && (
          <div className="simulator-grid">
            {/* Left Controls Column */}
            <div className="section-card" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              <div>
                <h3 className="section-title" style={{ marginBottom: '0.5rem' }}>Simulator Controls</h3>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-mute)', lineHeight: '1.4' }}>
                  Select a registered business to test its custom receptionist AI chatbot. Conversations run using actual vector database search chunks.
                </p>
              </div>

              <div className="form-group" style={{ marginBottom: 0 }}>
                <label style={{ fontWeight: 600, fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Target Business Profile</label>
                {businesses.length > 0 ? (
                  <select 
                    value={selectedBusinessId} 
                    onChange={(e) => {
                      setSelectedBusinessId(e.target.value);
                      setThreadId(Math.random().toString(36).substring(7));
                      setChatMessages([]);
                    }}
                    style={{ width: '100%', marginTop: '0.35rem' }}
                  >
                    {businesses.map(s => (
                      <option key={s.business_id} value={s.business_id}>{s.business_name} ({s.business_id})</option>
                    ))}
                  </select>
                ) : (
                  <p style={{ fontSize: '0.85rem', color: '#EF4444', marginTop: '0.5rem' }}>⚠️ No businesses onboarded yet. Go to 'Onboard Businesses' tab to add one.</p>
                )}
              </div>

              {selectedBusinessId && (
                <div style={{ padding: '1rem', border: '1px solid var(--border-card)', borderRadius: '8px', backgroundColor: 'rgba(255, 255, 255, 0.01)', fontSize: '0.85rem' }}>
                  <h4 style={{ fontWeight: 600, color: 'var(--primary)', marginBottom: '0.5rem', textTransform: 'uppercase', fontSize: '0.75rem', letterSpacing: '0.05em' }}>Active AI Context</h4>
                  {(() => {
                    const business = businesses.find(s => s.business_id === selectedBusinessId);
                    if (!business) return <p>No profile data</p>;
                    return (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', color: 'var(--text-mute)' }}>
                        <p>👤 <b>Assistant Name:</b> {business.agent_name}</p>
                        <p>🌐 <b>Website:</b> <a href={business.website_url} target="_blank" rel="noreferrer" style={{ color: 'var(--primary)', textDecoration: 'underline' }}>{business.website_url}</a></p>
                        <p>📞 <b>Phone Override:</b> {business.business_phone || 'None (Extracted from crawl)'}</p>
                        <p>📍 <b>Address Override:</b> {business.business_address || 'None (Extracted from crawl)'}</p>
                      </div>
                    );
                  })()}
                </div>
              )}

              {/* Quick Prompts */}
              {selectedBusinessId && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  <label style={{ fontWeight: 600, fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Quick Test Prompts</label>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                    {[
                      "Are you open right now?",
                      "What services do you offer?",
                      "What is your phone number?",
                      "Where are you located?",
                      "I want to speak with a human",
                      "Hi, just wanted to check what you do!"
                    ].map((prompt, i) => (
                      <button
                        key={i}
                        onClick={() => handleSendMessage(prompt)}
                        disabled={chatLoading}
                        style={{
                          backgroundColor: 'rgba(0, 210, 255, 0.05)',
                          border: '1px solid rgba(0, 210, 255, 0.15)',
                          borderRadius: '20px',
                          padding: '0.4rem 0.8rem',
                          fontSize: '0.75rem',
                          color: '#00D2FF',
                          cursor: 'pointer',
                          transition: 'all 0.2s',
                        }}
                        onMouseOver={(e) => {
                          e.currentTarget.style.backgroundColor = 'rgba(0, 210, 255, 0.1)';
                          e.currentTarget.style.borderColor = 'rgba(0, 210, 255, 0.3)';
                        }}
                        onMouseOut={(e) => {
                          e.currentTarget.style.backgroundColor = 'rgba(0, 210, 255, 0.05)';
                          e.currentTarget.style.borderColor = 'rgba(0, 210, 255, 0.15)';
                        }}
                      >
                        {prompt}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <button 
                onClick={() => {
                  setThreadId(Math.random().toString(36).substring(7));
                  setChatMessages([]);
                }}
                className="submit-btn" 
                style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  justifyContent: 'center', 
                  gap: '0.5rem', 
                  marginTop: 'auto',
                  backgroundColor: 'rgba(239, 68, 68, 0.1)',
                  color: '#EF4444',
                  border: '1px solid rgba(239, 68, 68, 0.2)',
                  backgroundImage: 'none'
                }}
                onMouseOver={(e) => e.currentTarget.style.backgroundColor = 'rgba(239, 68, 68, 0.15)'}
                onMouseOut={(e) => e.currentTarget.style.backgroundColor = 'rgba(239, 68, 68, 0.1)'}
              >
                <Trash2 size={16} />
                Clear Chat Thread
              </button>
            </div>

            {/* Right Chat Interface Column */}
            <div className="section-card" style={{ display: 'flex', flexDirection: 'column', height: '600px', padding: 0, overflow: 'hidden' }}>
              {/* Chat Header */}
              {(() => {
                const business = businesses.find(s => s.business_id === selectedBusinessId);
                return (
                  <div style={{ padding: '1rem 1.5rem', borderBottom: '1px solid var(--border-card)', display: 'flex', alignItems: 'center', gap: '0.75rem', backgroundColor: 'rgba(255,255,255,0.01)' }}>
                    <div style={{ width: '40px', height: '40px', borderRadius: '50%', backgroundColor: 'rgba(0, 210, 255, 0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', border: '1px solid rgba(0,210,255,0.2)' }}>
                      <Bot size={20} style={{ color: '#00D2FF' }} />
                    </div>
                    <div>
                      <h4 style={{ fontWeight: 600, fontSize: '0.95rem', margin: 0 }}>{business?.agent_name || 'Kim'}</h4>
                      <p style={{ fontSize: '0.75rem', color: '#10B981', margin: 0, display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                        <span style={{ width: '6px', height: '6px', backgroundColor: '#10B981', borderRadius: '50%', display: 'inline-block' }}></span>
                        Virtual Receptionist (Online)
                      </p>
                    </div>
                  </div>
                );
              })()}

              {/* Chat Messages Log */}
              <div style={{ flex: 1, padding: '1.5rem', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '1rem', backgroundColor: 'rgba(0,0,0,0.08)' }}>
                {chatMessages.map((msg, i) => (
                  <div 
                    key={i} 
                    style={{ 
                      alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                      maxWidth: '75%',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '0.25rem'
                    }}
                  >
                    <div 
                      style={{ 
                        padding: '0.85rem 1.1rem', 
                        borderRadius: msg.role === 'user' ? '16px 16px 2px 16px' : '16px 16px 16px 2px',
                        backgroundColor: msg.role === 'user' ? 'var(--primary-glow)' : 'rgba(255, 255, 255, 0.03)', 
                        border: msg.role === 'user' ? '1px solid rgba(0, 210, 255, 0.25)' : '1px solid var(--border-card)',
                        color: 'var(--text-main)',
                        fontSize: '0.9rem',
                        lineHeight: '1.5',
                        whiteSpace: 'pre-wrap'
                      }}
                    >
                      {msg.content}
                    </div>
                    <span style={{ fontSize: '0.7rem', color: 'var(--text-mute)', alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start' }}>
                      {msg.role === 'user' ? 'Visitor' : (businesses.find(s => s.business_id === selectedBusinessId)?.agent_name || 'Kim')}
                    </span>
                  </div>
                ))}
                
                {chatLoading && (
                  <div style={{ alignSelf: 'flex-start', maxWidth: '75%', display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-mute)', fontSize: '0.85rem' }}>
                    <div style={{ padding: '0.75rem 1rem', borderRadius: '16px 16px 16px 2px', backgroundColor: 'rgba(255,255,255,0.02)', border: '1px solid var(--border-card)', display: 'flex', gap: '0.25rem' }}>
                      <span className="dot-blink" style={{ width: '6px', height: '6px', backgroundColor: 'var(--text-mute)', borderRadius: '50%' }}></span>
                      <span className="dot-blink" style={{ width: '6px', height: '6px', backgroundColor: 'var(--text-mute)', borderRadius: '50%', animationDelay: '0.2s' }}></span>
                      <span className="dot-blink" style={{ width: '6px', height: '6px', backgroundColor: 'var(--text-mute)', borderRadius: '50%', animationDelay: '0.4s' }}></span>
                    </div>
                  </div>
                )}
              </div>

              {/* Chat Input Bar */}
              <div style={{ padding: '1.25rem', borderTop: '1px solid var(--border-card)', display: 'flex', gap: '0.75rem', backgroundColor: 'rgba(255,255,255,0.01)' }}>
                <input 
                  type="text" 
                  placeholder={selectedBusinessId ? `Ask ${businesses.find(s => s.business_id === selectedBusinessId)?.agent_name || 'Kim'}...` : "Select a business to start testing"}
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleSendMessage();
                  }}
                  disabled={!selectedBusinessId || chatLoading}
                  style={{ flex: 1 }}
                />
                <button 
                  onClick={() => handleSendMessage()}
                  disabled={!selectedBusinessId || chatLoading || !chatInput.trim()}
                  className="submit-btn" 
                  style={{ width: 'auto', padding: '0 1.5rem', whiteSpace: 'nowrap' }}
                >
                  Send Message
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ================= TAB 4: SUPPORT DIRECTORY ================= */}
        {activeTab === 'directory' && (
          <div className="simulator-grid">
            {/* Left Pane: Business List */}
            <div className="section-card" style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', height: '650px' }}>
              <div>
                <h3 className="section-title" style={{ marginBottom: '0.5rem' }}>Business Registry</h3>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-mute)', lineHeight: '1.4' }}>
                  Search and manage client profiles. Select a business to view metadata overrides, assets, and parsed data.
                </p>
              </div>

              {/* Search Box */}
              <div style={{ position: 'relative' }}>
                <input 
                  type="text" 
                  placeholder="Search by name or ID..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  style={{ width: '100%', paddingLeft: '2.5rem' }}
                />
                <Search size={16} style={{ position: 'absolute', left: '1rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-mute)' }} />
              </div>

              {/* Scrollable List */}
              <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {(() => {
                  const filtered = businesses.filter(b => 
                    b.business_name.toLowerCase().includes(searchQuery.toLowerCase()) || 
                    b.business_id.toLowerCase().includes(searchQuery.toLowerCase())
                  );

                  if (filtered.length === 0) {
                    return <p style={{ fontSize: '0.85rem', color: 'var(--text-mute)', textAlign: 'center', padding: '2rem 0' }}>No matching businesses found.</p>;
                  }

                  return filtered.map(b => {
                    const isSelected = selectedDirectoryBusinessId === b.business_id;
                    return (
                      <div 
                        key={b.business_id}
                        onClick={() => setSelectedDirectoryBusinessId(b.business_id)}
                        style={{
                          padding: '1rem',
                          borderRadius: '8px',
                          border: isSelected ? '1px solid rgba(0, 210, 255, 0.3)' : '1px solid var(--border-card)',
                          backgroundColor: isSelected ? 'var(--primary-glow)' : 'rgba(255,255,255,0.01)',
                          cursor: 'pointer',
                          transition: 'all 0.2s',
                        }}
                      >
                        <h4 style={{ fontSize: '0.95rem', fontWeight: 600, color: '#FFFFFF', marginBottom: '0.25rem' }}>{b.business_name}</h4>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <code style={{ fontSize: '0.75rem', color: isSelected ? '#00D2FF' : 'var(--text-mute)' }}>{b.business_id}</code>
                          <span style={{ fontSize: '0.75rem', color: 'var(--text-mute)' }}>Agent: {b.agent_name}</span>
                        </div>
                      </div>
                    );
                  });
                })()}
              </div>
            </div>

            {/* Right Pane: Details View */}
            <div className="section-card" style={{ display: 'flex', flexDirection: 'column', height: '650px', padding: 0, overflow: 'hidden' }}>
              {(() => {
                const b = businesses.find(x => x.business_id === selectedDirectoryBusinessId);
                if (!b) {
                  return (
                    <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-mute)', padding: '2rem' }}>
                      <p>Select a business from the registry to inspect support details.</p>
                    </div>
                  );
                }

                // Crawl history logs
                const bizJobs = crawlJobs.filter(j => j.business_id === b.business_id);

                return (
                  <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                    {/* Header */}
                    <div style={{ padding: '1.25rem 1.75rem', borderBottom: '1px solid var(--border-card)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', backgroundColor: 'rgba(255,255,255,0.01)' }}>
                      <div>
                        <h3 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 600 }}>{b.business_name}</h3>
                        <code style={{ fontSize: '0.8rem', color: 'var(--primary)' }}>ID Slug: {b.business_id}</code>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
                        {b.website_url && (
                          <a 
                            href={b.website_url} 
                            target="_blank" 
                            rel="noreferrer" 
                            style={{
                              fontSize: '0.85rem',
                              color: 'var(--primary)',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '0.35rem',
                              textDecoration: 'underline'
                            }}
                          >
                            Visit Site
                            <ExternalLink size={14} />
                          </a>
                        )}
                        <button
                          onClick={() => setDeleteConfirmId(b.business_id)}
                          style={{
                            padding: '0.4rem 0.8rem',
                            fontSize: '0.8rem',
                            backgroundColor: 'rgba(239, 68, 68, 0.1)',
                            color: '#EF4444',
                            border: '1px solid rgba(239, 68, 68, 0.2)',
                            borderRadius: '4px',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.35rem',
                            transition: 'all 0.2s'
                          }}
                          onMouseOver={(e) => e.currentTarget.style.backgroundColor = 'rgba(239, 68, 68, 0.2)'}
                          onMouseOut={(e) => e.currentTarget.style.backgroundColor = 'rgba(239, 68, 68, 0.1)'}
                        >
                          <Trash2 size={12} />
                          Delete Business
                        </button>
                      </div>
                    </div>

                    {/* Scrollable details */}
                    <div style={{ flex: 1, padding: '1.75rem', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                      
                      {/* Section 1: Metadata Overrides */}
                      <div>
                        <h4 style={{ fontSize: '0.8rem', fontWeight: 600, textTransform: 'uppercase', color: 'var(--primary)', letterSpacing: '0.05em', marginBottom: '0.75rem' }}>Database Configuration & Overrides</h4>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', backgroundColor: 'rgba(255,255,255,0.01)', border: '1px solid var(--border-card)', padding: '1rem', borderRadius: '8px', fontSize: '0.85rem' }}>
                          <p style={{ color: 'var(--text-mute)' }}>📞 <b>Phone Override:</b> <span style={{ color: '#FFF' }}>{b.business_phone || '--'}</span></p>
                          <p style={{ color: 'var(--text-mute)' }}>📧 <b>Email Override:</b> <span style={{ color: '#FFF' }}>{b.business_email || '--'}</span></p>
                          <p style={{ color: 'var(--text-mute)' }}>🗺️ <b>Address Override:</b> <span style={{ color: '#FFF' }}>{b.business_address || '--'}</span></p>
                          <p style={{ color: 'var(--text-mute)' }}>🌍 <b>Timezone:</b> <code style={{ color: '#00D2FF' }}>{b.business_timezone}</code></p>
                          <p style={{ color: 'var(--text-mute)' }}>🔗 <b>Admin Telegram ID:</b> <span style={{ color: '#FFF' }}>{b.admin_chat_id || 'Not Bound'}</span></p>
                          <p style={{ color: 'var(--text-mute)' }}>📅 <b>Created At:</b> <span style={{ color: '#FFF' }}>{new Date(b.created_at).toLocaleDateString()}</span></p>
                        </div>
                      </div>

                      {/* Section 2: Marketing & Activation Assets */}
                      <div>
                        <h4 style={{ fontSize: '0.8rem', fontWeight: 600, textTransform: 'uppercase', color: 'var(--primary)', letterSpacing: '0.05em', marginBottom: '0.75rem' }}>Marketing & PDF Assets</h4>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                          {b.flyer_url ? (
                            <a 
                              href={b.flyer_url} 
                              target="_blank" 
                              rel="noreferrer"
                              style={{ 
                                display: 'flex', 
                                alignItems: 'center', 
                                gap: '0.5rem', 
                                padding: '0.75rem 1rem', 
                                border: '1px solid rgba(16, 185, 129, 0.2)', 
                                borderRadius: '8px', 
                                backgroundColor: 'rgba(16, 185, 129, 0.05)', 
                                color: '#10B981', 
                                textDecoration: 'none', 
                                fontSize: '0.85rem' 
                              }}
                            >
                              📄 Download Marketing Flyer (PDF)
                            </a>
                          ) : (
                            <div style={{ padding: '0.75rem 1rem', border: '1px solid var(--border-card)', borderRadius: '8px', color: 'var(--text-mute)', fontSize: '0.85rem' }}>
                              📄 Flyer PDF: Compiling...
                            </div>
                          )}

                          {b.owner_qr_url ? (
                            <a 
                              href={b.owner_qr_url} 
                              target="_blank" 
                              rel="noreferrer"
                              style={{ 
                                display: 'flex', 
                                alignItems: 'center', 
                                gap: '0.5rem', 
                                padding: '0.75rem 1rem', 
                                border: '1px solid rgba(0, 210, 255, 0.2)', 
                                borderRadius: '8px', 
                                backgroundColor: 'rgba(0, 210, 255, 0.05)', 
                                color: '#00D2FF', 
                                textDecoration: 'none', 
                                fontSize: '0.85rem' 
                              }}
                            >
                              📷 Get Activation QR (PNG)
                            </a>
                          ) : (
                            <div style={{ padding: '0.75rem 1rem', border: '1px solid var(--border-card)', borderRadius: '8px', color: 'var(--text-mute)', fontSize: '0.85rem' }}>
                              📷 Activation QR: Generating...
                            </div>
                          )}

                          <a 
                            href={`${window.location.protocol}//${window.location.hostname}:8080/?biz=${b.business_id}`}
                            target="_blank" 
                            rel="noreferrer"
                            style={{ 
                              display: 'flex', 
                              alignItems: 'center', 
                              gap: '0.5rem', 
                              padding: '0.75rem 1rem', 
                              border: '1px solid rgba(167, 139, 250, 0.2)', 
                              borderRadius: '8px', 
                              backgroundColor: 'rgba(167, 139, 250, 0.05)', 
                              color: '#a78bfa', 
                              textDecoration: 'none', 
                              fontSize: '0.85rem',
                              gridColumn: 'span 2'
                            }}
                          >
                            💬 Launch Mobile WebApp Chat ({window.location.hostname}:8080/?biz={b.business_id})
                          </a>
                        </div>
                      </div>

                      {/* Section 3: Knowledge Base Inspector (Vector DB chunks) */}
                      <div>
                        <h4 style={{ fontSize: '0.8rem', fontWeight: 600, textTransform: 'uppercase', color: 'var(--primary)', letterSpacing: '0.05em', marginBottom: '0.75rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span>Parsed Vector Search Index ({selectedBusinessChunks.length} chunks)</span>
                          {chunksLoading && <Loader size={12} className="animate-spin" style={{ animation: 'spin 1s linear infinite' }} />}
                        </h4>
                        
                        <div style={{ maxHeight: '200px', overflowY: 'auto', border: '1px solid var(--border-card)', borderRadius: '8px', backgroundColor: 'rgba(0,0,0,0.1)' }}>
                          {selectedBusinessChunks.length > 0 ? (
                            selectedBusinessChunks.map((chunk, i) => (
                              <div 
                                key={chunk.id}
                                style={{
                                  padding: '0.85rem',
                                  fontSize: '0.8rem',
                                  borderBottom: i === selectedBusinessChunks.length - 1 ? 'none' : '1px solid var(--border-card)',
                                  color: 'var(--text-main)',
                                  lineHeight: '1.4',
                                  whiteSpace: 'pre-wrap'
                                }}
                              >
                                <span style={{ display: 'block', fontSize: '0.7rem', color: 'var(--primary)', fontWeight: 600, marginBottom: '0.35rem' }}>CHUNK #{i+1}</span>
                                {chunk.content}
                              </div>
                            ))
                          ) : (
                            <p style={{ fontSize: '0.85rem', color: 'var(--text-mute)', padding: '1.5rem', textAlign: 'center', margin: 0 }}>
                              {chunksLoading ? 'Fetching knowledge chunks...' : 'No indexed knowledge base chunks found. Run a scraper crawl to seed the search database.'}
                            </p>
                          )}
                        </div>
                      </div>

                      {/* Section 4: Scraping Queue logs */}
                      <div>
                        <h4 style={{ fontSize: '0.8rem', fontWeight: 600, textTransform: 'uppercase', color: 'var(--primary)', letterSpacing: '0.05em', marginBottom: '0.75rem' }}>Scraper Queue History</h4>
                        <div style={{ border: '1px solid var(--border-card)', borderRadius: '8px', overflow: 'hidden' }}>
                          <table style={{ width: '100%', fontSize: '0.8rem' }}>
                            <thead>
                              <tr style={{ backgroundColor: 'rgba(255,255,255,0.01)' }}>
                                <th style={{ padding: '0.5rem 0.75rem' }}>Crawl Job ID</th>
                                <th style={{ padding: '0.5rem 0.75rem' }}>Status</th>
                                <th style={{ padding: '0.5rem 0.75rem' }}>Completed At</th>
                              </tr>
                            </thead>
                            <tbody>
                              {bizJobs.length > 0 ? (
                                bizJobs.slice(0, 3).map((job) => (
                                  <tr key={job.id}>
                                    <td style={{ padding: '0.5rem 0.75rem' }}><code style={{ fontSize: '0.75rem' }}>{job.id.substring(0, 8)}...</code></td>
                                    <td style={{ padding: '0.5rem 0.75rem' }}>
                                      <span className={`badge ${job.status}`} style={{ fontSize: '0.65rem', padding: '0.1rem 0.35rem' }}>{job.status}</span>
                                    </td>
                                    <td style={{ padding: '0.5rem 0.75rem', color: 'var(--text-mute)' }}>{new Date(job.created_at).toLocaleString()}</td>
                                  </tr>
                                ))
                              ) : (
                                <tr>
                                  <td colSpan={3} style={{ padding: '1rem', textAlign: 'center', color: 'var(--text-mute)' }}>No scraper records for this business.</td>
                                </tr>
                              )}
                            </tbody>
                          </table>
                        </div>
                      </div>

                    </div>
                  </div>
                );
              })()}
            </div>
          </div>
        )}

      </main>

      {/* Delete Confirmation Modal Overlay */}
      {deleteConfirmId && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(15, 17, 20, 0.85)',
          backdropFilter: 'blur(8px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <div style={{
            backgroundColor: '#1E2229',
            border: '1px solid var(--border-card)',
            borderRadius: '12px',
            padding: '2rem',
            maxWidth: '450px',
            width: '90%',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 10px 10px -5px rgba(0, 0, 0, 0.4)',
            textAlign: 'center'
          }}>
            <div style={{
              width: '56px',
              height: '56px',
              borderRadius: '50%',
              backgroundColor: 'rgba(239, 68, 68, 0.1)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 1.5rem auto',
              border: '1px solid rgba(239, 68, 68, 0.2)'
            }}>
              <ShieldAlert size={28} style={{ color: '#EF4444' }} />
            </div>
            
            <h3 style={{ fontSize: '1.25rem', fontWeight: 600, color: '#FFF', marginBottom: '0.75rem', fontFamily: 'inherit' }}>
              Delete Client Profile?
            </h3>
            
            <p style={{ fontSize: '0.875rem', color: 'var(--text-mute)', lineHeight: '1.5', marginBottom: '2rem' }}>
              Are you sure you want to permanently delete the profile <code style={{ color: '#00D2FF', backgroundColor: 'rgba(0,210,255,0.05)', padding: '0.2rem 0.4rem', borderRadius: '4px' }}>{deleteConfirmId}</code>? This action cascades and will wipe all vector files, crawl metrics, and active chatbot configurations.
            </p>
            
            <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center' }}>
              <button
                onClick={() => setDeleteConfirmId(null)}
                style={{
                  padding: '0.6rem 1.5rem',
                  backgroundColor: 'rgba(255, 255, 255, 0.05)',
                  color: '#FFF',
                  border: '1px solid var(--border-card)',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  fontSize: '0.875rem',
                  transition: 'background 0.2s'
                }}
                onMouseOver={(e) => e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.1)'}
                onMouseOut={(e) => e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.05)'}
              >
                Cancel
              </button>
              
              <button
                onClick={() => {
                  const id = deleteConfirmId;
                  setDeleteConfirmId(null);
                  executeDeleteBusiness(id);
                }}
                style={{
                  padding: '0.6rem 1.5rem',
                  backgroundColor: '#EF4444',
                  color: '#FFF',
                  border: 'none',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  fontSize: '0.875rem',
                  fontWeight: 600,
                  transition: 'background 0.2s'
                }}
                onMouseOver={(e) => e.currentTarget.style.backgroundColor = '#DC2626'}
                onMouseOut={(e) => e.currentTarget.style.backgroundColor = '#EF4444'}
              >
                Yes, Delete Profile
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
