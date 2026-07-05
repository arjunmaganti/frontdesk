import React, { useState, useEffect, useRef } from 'react';
import { 
  ThreadPrimitive, 
  ComposerPrimitive, 
  useExternalStoreRuntime,
  AssistantRuntimeProvider 
} from "@assistant-ui/react";
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

  const chatEndRef = useRef<HTMLDivElement>(null);

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

  // 7. Bridge message state to assistant-ui ExternalStoreRuntime
  const runtime = useExternalStoreRuntime({
    messages: messages.filter(m => m.sender !== 'system'),
    convertMessage: (m: Message) => ({
      id: String(m.id),
      role: m.sender === 'visitor' ? 'user' : 'assistant',
      content: [{ type: 'text', text: m.message }],
      createdAt: new Date(m.created_at)
    }),
    onNew: async (message) => {
      if (message.content[0]?.type === 'text') {
        const text = message.content[0].text;
        await handleSendText(text);
      }
    }
  });

  const handleSlugSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (slugInput.trim()) {
      window.location.search = `?biz=${slugInput.trim()}`;
    }
  };

  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (inputText.trim()) {
      handleSendText(inputText.trim());
      setInputText('');
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

          <form onSubmit={handleSlugSubmit} className="mt-6 space-y-4">
            <div>
              <input
                type="text"
                required
                value={slugInput}
                onChange={e => setSlugInput(e.target.value)}
                placeholder="e.g. hair-by-gabie-g"
                className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-white placeholder-gray-500 focus:border-[#00D2FF] focus:outline-none focus:ring-1 focus:ring-[#00D2FF]"
              />
            </div>
            <button
              type="submit"
              className="flex w-full items-center justify-center rounded-xl bg-gradient-to-r from-[#00D2FF] to-[#0080FF] py-3 text-sm font-semibold text-white shadow-lg transition-transform hover:scale-[1.02]"
            >
              Start Chat <ArrowRight className="ml-2 h-4 w-4" />
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <div className="flex h-screen flex-col bg-[#06090e] font-sans text-white">
        {/* Header Profile Bar */}
        <header className="flex items-center justify-between border-b border-white/5 bg-[#0a0f18]/80 px-4 py-3 backdrop-blur-md shadow-md z-10">
          <div className="flex items-center space-x-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[#00D2FF]/10 text-[#00D2FF] font-outfit font-bold text-lg">
              {bizConfig.business_name.substring(0, 1)}
            </div>
            <div>
              <h1 className="font-outfit font-semibold text-sm leading-tight">{bizConfig.business_name}</h1>
              <p className="text-xs font-light text-[#00D2FF] flex items-center">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 inline-block mr-1.5 animate-pulse"></span>
                {bizConfig.agent_name || "AI Assistant"}
              </p>
            </div>
          </div>
          
          {/* Quick Contact Buttons */}
          <div className="flex items-center space-x-1">
            {bizConfig.business_phone && (
              <a href={`tel:${bizConfig.business_phone}`} className="p-2 text-gray-400 hover:text-white rounded-lg hover:bg-white/5">
                <Phone className="h-4 w-4" />
              </a>
            )}
            {bizConfig.map_url && (
              <a href={bizConfig.map_url} target="_blank" rel="noreferrer" className="p-2 text-gray-400 hover:text-white rounded-lg hover:bg-white/5">
                <MapPin className="h-4 w-4" />
              </a>
            )}
          </div>
        </header>

        {/* assistant-ui Thread Primitive Container */}
        <ThreadPrimitive.Root className="flex-1 flex flex-col overflow-hidden">
          <main className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
            {messages.length === 0 && (
              <div className="flex h-full flex-col items-center justify-center text-center p-6">
                <div className="h-12 w-12 rounded-full bg-white/5 flex items-center justify-center text-[#00D2FF] mb-3">
                  <MessageSquare className="h-6 w-6" />
                </div>
                <h3 className="font-outfit font-medium text-sm text-gray-300">Welcome to {bizConfig.business_name}</h3>
                <p className="text-xs text-gray-500 max-w-xs mt-1">
                  Ask me about our operating hours, pricing list, location address, or booking details!
                </p>
              </div>
            )}

            {/* Loop through messages */}
            <ThreadPrimitive.Messages
              components={{
                Message: ({ message }: any) => {
                  if (!message) return null;
                  const m = messages.find(x => x && x.id && String(x.id) === message.id);
                  const isMe = message.role === 'user';
                  const senderName = isMe ? 'You' : (m?.sender === 'staff' ? 'Staff Representative' : (bizConfig.agent_name || 'Frontdesk'));
                  
                  return (
                    <div className={`flex flex-col my-3 ${isMe ? 'items-end' : 'items-start'}`}>
                      <span className="text-[10px] text-gray-500 mb-1 px-1">{senderName}</span>
                      <div className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm shadow-md leading-relaxed whitespace-pre-wrap ${
                        isMe
                          ? 'bg-gradient-to-br from-[#00D2FF] to-[#0080FF] text-white rounded-tr-none'
                          : m?.sender === 'staff'
                            ? 'bg-gradient-to-br from-[#FF8000] to-[#FF4000] text-white rounded-tl-none'
                            : 'bg-white/5 border border-white/10 text-gray-200 rounded-tl-none'
                      }`}>
                        {message.content.map((part: any, index: number) => {
                          if (part.type === 'text') {
                            return <span key={index}>{formatText(part.text)}</span>;
                          }
                          return null;
                        })}
                      </div>
                      <span className="text-[9px] text-gray-600 mt-1 px-1">
                        {message.createdAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                  );
                }
              }}
            />

            {/* Render any system/resolution notifications manually outside RAG bubbles */}
            {messages.filter(m => m.sender === 'system').map(sysMsg => (
              <div key={sysMsg.id} className="flex justify-center my-2">
                <div className="rounded-lg bg-amber-500/10 border border-amber-500/20 px-3 py-1.5 text-xs text-amber-300 max-w-xs text-center shadow-sm">
                  {sysMsg.message}
                </div>
              </div>
            ))}

            {isSending && (
              <div className="flex flex-col items-start my-3">
                <span className="text-[10px] text-gray-500 mb-1 px-1">{bizConfig.agent_name || "Frontdesk"}</span>
                <div className="rounded-2xl rounded-tl-none px-4 py-3 bg-white/5 border border-white/10 flex space-x-1.5 items-center">
                  <span className="h-1.5 w-1.5 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: '0ms' }}></span>
                  <span className="h-1.5 w-1.5 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: '150ms' }}></span>
                  <span className="h-1.5 w-1.5 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: '300ms' }}></span>
                </div>
              </div>
            )}

            <div ref={chatEndRef} />
          </main>

          {/* assistant-ui Composer Input Box */}
          <footer className="border-t border-white/5 bg-[#0a0f18]/60 p-3 backdrop-blur-md z-10">
            {isPaused && (
              <div className="mb-2 text-center text-[11px] text-amber-400 flex items-center justify-center">
                <span className="h-1.5 w-1.5 rounded-full bg-amber-400 inline-block mr-1.5 animate-pulse"></span>
                Staff connected. Your messages are relayed directly.
              </div>
            )}
            
            <ComposerPrimitive.Root className="flex items-center space-x-2">
              <form onSubmit={handleFormSubmit} className="flex-1 flex items-center space-x-2">
                <input
                  type="text"
                  required
                  value={inputText}
                  onChange={e => setInputText(e.target.value)}
                  placeholder={isPaused ? "Type message for staff..." : "Ask the front desk..."}
                  className="flex-1 rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white placeholder-gray-500 focus:border-[#00D2FF] focus:outline-none focus:ring-1 focus:ring-[#00D2FF]"
                />
                <button
                  type="submit"
                  disabled={!inputText.trim() || isSending}
                  className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-r from-[#00D2FF] to-[#0080FF] text-white shadow-md transition-transform active:scale-95 disabled:opacity-40 disabled:scale-100"
                >
                  <Send className="h-4 w-4" />
                </button>
              </form>
            </ComposerPrimitive.Root>
          </footer>
        </ThreadPrimitive.Root>
      </div>
    </AssistantRuntimeProvider>
  );
}
