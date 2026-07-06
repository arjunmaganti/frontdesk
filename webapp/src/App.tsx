import React, { useState, useEffect, useRef } from 'react';
import { Send, ArrowRight, MessageSquare, Phone, MapPin, Compass } from 'lucide-react';

interface Message {
  id: number;
  session_id: string;
  sender: 'visitor' | 'assistant' | 'staff' | 'system';
  message: string;
  created_at: string;
}

interface BusinessConfig {
  business_id: string;
  business_name: string;
  agent_name: string;
  website_url?: string;
  business_phone?: string;
  business_address?: string;
  business_email?: string;
  map_url?: string;
}

export default function App() {
  const [businessId, setBusinessId] = useState<string>('');
  const [bizConfig, setBizConfig] = useState<BusinessConfig | null>(null);
  const [sessionId, setSessionId] = useState<string>('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputText, setInputText] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isSending, setIsSending] = useState<boolean>(false);
  const [isPaused, setIsPaused] = useState<boolean>(false);
  const [slugInput, setSlugInput] = useState<string>('');
  const [viewportHeight, setViewportHeight] = useState<string>('100vh');
  const [isKeyboardOpen, setIsKeyboardOpen] = useState<boolean>(false);

  const chatEndRef = useRef<HTMLDivElement>(null);

  // Dynamic visual viewport height listener for mobile keyboards
  useEffect(() => {
    const visualViewport = window.visualViewport;
    if (!visualViewport) return;

    const handleResize = () => {
      const height = visualViewport.height;
      setViewportHeight(`${height}px`);
      setIsKeyboardOpen(height < window.innerHeight * 0.85);
    };

    visualViewport.addEventListener('resize', handleResize);
    visualViewport.addEventListener('scroll', handleResize);
    
    // Initial sync
    handleResize();

    return () => {
      visualViewport.removeEventListener('resize', handleResize);
      visualViewport.removeEventListener('scroll', handleResize);
    };
  }, []);

  // 1. Resolve business ID from URL parameter e.g. ?biz=hair-by-gabie-g
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const bizParam = params.get('biz');
    if (bizParam) {
      setBusinessId(bizParam);
      loadBusinessConfig(bizParam);
    }
  }, []);

  // 2. Load business profile parameters
  const loadBusinessConfig = async (id: string) => {
    setIsLoading(true);
    try {
      const response = await fetch(`/api/webapp/business/${id}`);
      if (response.ok) {
        const data: BusinessConfig = await response.json();
        setBizConfig(data);
        initializeSession(id);
      } else {
        console.error("Business not found in records");
      }
    } catch (e) {
      console.error("Failed to load business profile config", e);
    } finally {
      setIsLoading(false);
    }
  };

  // 3. Initialize or retrieve session
  const initializeSession = async (bizId: string) => {
    const cacheKey = `frontdesk_session_${bizId}`;
    const cached = localStorage.getItem(cacheKey);

    if (cached) {
      setSessionId(cached);
      loadMessages(cached);
      return;
    }

    try {
      const response = await fetch('/api/webapp/session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ business_id: bizId })
      });
      if (response.ok) {
        const data = await response.json();
        localStorage.setItem(cacheKey, data.session_id);
        setSessionId(data.session_id);
        loadMessages(data.session_id);
      }
    } catch (e) {
      console.error("Failed to create session", e);
    }
  };

  // 4. Fetch message logs
  const loadMessages = async (sessId: string) => {
    try {
      const response = await fetch(`/api/webapp/messages?session_id=${sessId}`);
      if (response.ok) {
        const list: Message[] = await response.json();
        setMessages(list);

        // Find latest system message index
        let latestIsPaused = false;
        for (let i = list.length - 1; i >= 0; i--) {
          if (list[i].sender === 'system') {
            if (list[i].message.includes("reviewing") || list[i].message.includes("escalated")) {
              latestIsPaused = true;
            } else if (list[i].message.includes("resolved") || list[i].message.includes("online")) {
              latestIsPaused = false;
            }
            break;
          }
        }
        setIsPaused(latestIsPaused);
      }
    } catch (e) {
      console.error("Error loading message logs", e);
    }
  };

  // 5. Polling loop for staff replies
  useEffect(() => {
    if (!sessionId) return;

    const interval = setInterval(() => {
      loadMessages(sessionId);
    }, 2000);

    return () => clearInterval(interval);
  }, [sessionId]);

  // Autoscroll logic
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // 6. Backend API query
  const handleSendText = async (text: string) => {
    if (isSending || !sessionId) return;
    setIsSending(true);

    // Optimistically add message
    const tempMsg: Message = {
      id: Date.now(),
      session_id: sessionId,
      sender: 'visitor',
      message: text,
      created_at: new Date().toISOString()
    };
    setMessages(prev => [...prev, tempMsg]);

    try {
      const response = await fetch('/api/webapp/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          message: text
        })
      });

      if (response.ok) {
        const data = await response.json();
        if (data.is_paused) {
          setIsPaused(true);
        }
        loadMessages(sessionId);
      }
    } catch (e) {
      console.error("Error sending message", e);
    } finally {
      setIsSending(false);
    }
  };

  // Formats text to render links and bold headers beautifully
  const formatText = (text: string) => {
    return text.split('\n').map((line, i) => {
      let content: React.ReactNode = line;
      if (line.startsWith('**') && line.endsWith('**')) {
        content = <strong>{line.replace(/\*\*/g, '')}</strong>;
      }
      return <div key={i} className="min-h-[1.2rem]">{content}</div>;
    });
  };

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-[#06090e] text-white">
        <div className="text-center">
          <div className="h-10 w-10 animate-spin rounded-full border-4 border-[#00D2FF] border-t-transparent mx-auto"></div>
          <p className="mt-4 text-gray-400 font-light">Connecting to virtual receptionist...</p>
        </div>
      </div>
    );
  }

  // Welcome selection screen if no biz param is set
  if (!businessId || !bizConfig) {
    return (
      <div className="flex h-screen items-center justify-center bg-[#06090e] px-4 font-sans text-white">
        <div className="w-full max-w-md rounded-2xl border border-white/10 bg-white/5 p-6 backdrop-blur-xl shadow-2xl">
          <div className="text-center">
            <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-[#00D2FF]/10 text-[#00D2FF] mb-4">
              <Compass className="h-8 w-8 animate-pulse" />
            </div>
            <h2 className="text-2xl font-bold tracking-tight text-white font-outfit">Find AI Receptionist</h2>
            <p className="mt-2 text-sm text-gray-400">
              Please enter the unique business ID code to chat with the AI virtual front desk:
            </p>
          </div>

          <div className="mt-6 space-y-4">
            <div>
              <input
                type="text"
                required
                value={slugInput}
                onChange={e => setSlugInput(e.target.value)}
                placeholder="e.g. hair-by-gabie-g"
                className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-white placeholder-gray-500 focus:border-[#00D2FF] focus:outline-none focus:ring-1 focus:ring-[#00D2FF]"
                onKeyDown={e => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    if (slugInput.trim()) {
                      window.location.href = `${window.location.origin}/?biz=${encodeURIComponent(slugInput.trim())}`;
                    }
                  }
                }}
              />
            </div>
            <button
              type="button"
              onClick={() => {
                if (slugInput.trim()) {
                  window.location.href = `${window.location.origin}/?biz=${encodeURIComponent(slugInput.trim())}`;
                }
              }}
              className="flex w-full items-center justify-center rounded-xl bg-gradient-to-r from-[#00D2FF] to-[#0080FF] py-3 text-sm font-semibold text-white shadow-lg transition-transform hover:scale-[1.02]"
            >
              Start Chat <ArrowRight className="ml-2 h-4 w-4" />
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div 
      className="flex flex-col bg-[#191919] font-sans text-white overflow-hidden" 
      style={{ height: viewportHeight }}
    >
        {/* Header Profile Bar */}
        <header className="flex items-center justify-between border-b border-white/5 bg-[#1e1e1c]/90 px-6 py-3.5 backdrop-blur-md shadow-sm z-10">
          <div className="flex items-center space-x-3.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#C5A880]/15 text-[#C5A880] font-serif font-bold text-base border border-[#C5A880]/30 shadow-inner">
              {bizConfig.business_name.substring(0, 1)}
            </div>
            <div>
              <h1 className="font-serif font-semibold text-sm leading-tight tracking-wide text-gray-200">{bizConfig.business_name}</h1>
              <p className="text-xs font-light text-gray-400 flex items-center mt-0.5">
                <span className="h-1.5 w-1.5 rounded-full bg-[#C5A880] inline-block mr-1.5 animate-pulse"></span>
                {bizConfig.agent_name || "AI Assistant"}
              </p>
            </div>
          </div>

          {/* Quick Contact Buttons */}
          <div className="flex items-center space-x-1.5">
            {bizConfig.business_phone && (
              <a href={`tel:${bizConfig.business_phone}`} className="p-2 text-gray-400 hover:text-white rounded-lg hover:bg-white/5 transition-colors">
                <Phone className="h-4 w-4" />
              </a>
            )}
            {bizConfig.map_url && (
              <a href={bizConfig.map_url} target="_blank" rel="noreferrer" className="p-2 text-gray-400 hover:text-white rounded-lg hover:bg-white/5 transition-colors">
                <MapPin className="h-4 w-4" />
              </a>
            )}
          </div>
        </header>

        {/* Chat Thread Viewport Container */}
        <div className="flex-1 flex flex-col overflow-hidden">
          <main className="flex-1 overflow-y-auto py-6">
            <div className="max-w-2xl mx-auto w-full px-4 space-y-6">
              {messages.length === 0 && (
                <div className="flex flex-col items-center justify-center text-center py-20 px-6">
                  <div className="h-14 w-14 rounded-full bg-[#C5A880]/10 flex items-center justify-center text-[#C5A880] border border-[#C5A880]/20 mb-4 shadow-sm">
                    <MessageSquare className="h-6 w-6" />
                  </div>
                  <h3 className="font-serif font-medium text-lg text-gray-200 tracking-wide">Welcome to {bizConfig.business_name}</h3>
                  <p className="text-sm text-gray-400 max-w-sm mt-2 leading-relaxed">
                    Hello! I'm {bizConfig.agent_name || "Sarah"}, your virtual front desk host. Ask me about pricing, schedules, address location, or salon offerings!
                  </p>
                </div>
              )}

              {/* Loop through messages */}
              {messages.filter(m => m.sender !== 'system').map((m, idx) => {
                const isMe = m.sender === 'visitor';
                const senderName = isMe ? 'You' : (m.sender === 'staff' ? 'Staff' : (bizConfig.agent_name || 'Assistant'));
                
                return (
                  <div key={m.id || idx} className={`flex items-start gap-3 my-4 ${isMe ? 'flex-row-reverse' : ''}`}>
                    {/* Avatar */}
                    {!isMe ? (
                      <div className={`flex h-8 w-8 shrink-0 select-none items-center justify-center rounded-full text-xs font-bold font-serif ${
                        m.sender === 'staff'
                          ? 'bg-amber-600/20 text-amber-500 border border-amber-500/30'
                          : 'bg-[#C5A880]/20 text-[#C5A880] border border-[#C5A880]/30'
                      }`}>
                        {m.sender === 'staff' ? 'S' : (bizConfig.business_name || 'Salon').substring(0, 1)}
                      </div>
                    ) : (
                      <div className="flex h-8 w-8 shrink-0 select-none items-center justify-center rounded-full bg-zinc-800 text-zinc-400 text-xs font-semibold border border-zinc-700/50">
                        U
                      </div>
                    )}

                    <div className={`flex flex-col max-w-[80%] ${isMe ? 'items-end' : 'items-start'}`}>
                      {/* Name header */}
                      <div className="flex items-center gap-1.5 mb-1 px-1">
                        <span className="text-[11px] font-medium text-zinc-400">{senderName}</span>
                        <span className="text-[9px] text-zinc-500">
                          {m.created_at
                            ? new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                            : new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>

                      {/* Chat Bubble container (Claude-style) */}
                      <div className={`rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${
                        isMe
                          ? 'bg-[#2B2A27] border border-zinc-800 text-zinc-100 rounded-tr-none'
                          : m.sender === 'staff'
                            ? 'bg-amber-950/20 border border-amber-900/30 text-amber-100 rounded-tl-none shadow-sm'
                            : 'bg-[#222222]/60 border border-zinc-800/80 text-zinc-200 rounded-tl-none'
                      }`}>
                        {formatText(m.message)}
                      </div>
                    </div>
                  </div>
                );
              })}

              {/* Render any system/resolution notifications manually outside RAG bubbles */}
              {messages.filter(m => m.sender === 'system').map(sysMsg => (
                <div key={sysMsg.id} className="flex justify-center my-4">
                  <div className="rounded-lg bg-amber-500/10 border border-amber-500/20 px-3 py-1.5 text-xs text-amber-300 max-w-xs text-center shadow-sm">
                    {sysMsg.message}
                  </div>
                </div>
              ))}

              {isSending && (
                <div className="flex items-start gap-3 my-4">
                  <div className="flex h-8 w-8 shrink-0 select-none items-center justify-center rounded-full bg-[#C5A880]/20 text-[#C5A880] text-xs font-bold font-serif border border-[#C5A880]/30">
                    {bizConfig.business_name.substring(0, 1)}
                  </div>
                  <div className="flex flex-col items-start">
                    <div className="flex items-center gap-1.5 mb-1 px-1">
                      <span className="text-[11px] font-medium text-zinc-400">{bizConfig.agent_name || 'Assistant'}</span>
                    </div>
                    <div className="rounded-2xl rounded-tl-none px-4 py-3 bg-[#222222]/60 border border-zinc-800/80 flex space-x-1.5 items-center">
                      <span className="h-1.5 w-1.5 rounded-full bg-zinc-500 animate-bounce" style={{ animationDelay: '0ms' }}></span>
                      <span className="h-1.5 w-1.5 rounded-full bg-zinc-500 animate-bounce" style={{ animationDelay: '150ms' }}></span>
                      <span className="h-1.5 w-1.5 rounded-full bg-zinc-500 animate-bounce" style={{ animationDelay: '300ms' }}></span>
                    </div>
                  </div>
                </div>
              )}
            </div>
            <div ref={chatEndRef} />
          </main>

          {/* Composer Input Box (Claude-style centered floating footer) */}
          <footer className={`w-full bg-[#191919] px-4 pt-2 transition-all ${isKeyboardOpen ? 'pb-2' : 'pb-5'}`}>
            <div className="max-w-2xl mx-auto w-full">
              {isPaused && (
                <div className="mb-2.5 text-center text-xs text-amber-400 flex items-center justify-center">
                  <span className="h-1.5 w-1.5 rounded-full bg-amber-400 inline-block mr-1.5 animate-pulse"></span>
                  Staff connected. Your messages are relayed directly.
                </div>
              )}

              <div className="relative flex items-center bg-[#1e1e1c] border border-zinc-800 rounded-2xl px-4 py-2.5 shadow-sm focus-within:border-zinc-700 transition-all">
                <input
                  type="text"
                  required
                  value={inputText}
                  onChange={e => setInputText(e.target.value)}
                  onFocus={() => {
                    setTimeout(() => {
                      chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
                    }, 200);
                  }}
                  onKeyDown={e => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      if (inputText.trim() && !isSending) {
                        handleSendText(inputText.trim());
                        setInputText('');
                      }
                    }
                  }}
                  placeholder={isPaused ? "Reply to staff representative..." : `Ask ${bizConfig.agent_name || 'the front desk'}...`}
                  className="flex-1 bg-transparent text-sm text-zinc-200 placeholder-zinc-500 focus:outline-none focus:ring-0 pr-12"
                />
                <button
                  type="button"
                  onClick={() => {
                    if (inputText.trim() && !isSending) {
                      handleSendText(inputText.trim());
                      setInputText('');
                    }
                  }}
                  disabled={!inputText.trim() || isSending}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 flex h-8 w-8 items-center justify-center rounded-xl bg-[#2B2A27] text-zinc-400 border border-zinc-800 shadow-sm transition-all hover:text-white hover:bg-zinc-800 active:scale-95 disabled:opacity-30 disabled:scale-100 disabled:hover:bg-[#2B2A27] disabled:hover:text-zinc-400"
                >
                  <Send className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          </footer>
        </div>
      </div>
  );
}
