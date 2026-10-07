import React, { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import FoodVisionPage from "./FoodVisionPage";

// ==========================================
// 1. UPDATED TYPE DEFINITIONS
// ==========================================

type ChatMessage = {
  id: number;
  role: "user" | "assistant";
  content: string;
};

// This matches the "NutrientStatus" Pydantic model from your Python Backend
type NutrientStatus = {
  name: string;          // e.g. "Sodium"
  limit: number;         // e.g. 1500.0
  unit: string;          // e.g. "mg"
  consumed_today: number;
  remaining: number;
  is_violated: boolean;
};

type ChatResponse = {
  thread_id?: string;
  response?: string;
  debug_classification?: string;
  action_type?: string; // <--- NEW FIELD
    // The backend now returns a generic list of statuses
  protocol_statuses?: NutrientStatus[]; 
};

type SessionStateResponse = {
  thread_id: string;
  messages: { role: string; content: string }[];
  // We assume the session endpoint also returns the current status list
  protocol_statuses?: NutrientStatus[];
};

const API_BASE_URL = "http://localhost:8000";

// ==========================================
// 2. HELPER COMPONENTS
// ==========================================

const NutrientCard = ({ status }: { status: NutrientStatus }) => {
  // Calculate percentage for the bar (cap at 100%)
  const percent = status.limit > 0 
    ? Math.min(100, (status.consumed_today / status.limit) * 100) 
    : 0;

  // Dynamic Coloring
  const isDanger = status.is_violated;
  const barColor = isDanger ? "bg-red-400" : "bg-emerald-400";
  const textColor = isDanger ? "text-red-100" : "text-emerald-100";
  const labelColor = isDanger ? "text-red-50" : "text-white";

  return (
    <div className="bg-white/10 rounded-2xl p-4 flex flex-col gap-2 mb-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <span className={`text-sm font-semibold ${labelColor}`}>{status.name}</span>
        <span className="text-xs font-mono opacity-80 text-white">
          Limit: {status.limit} {status.unit}
        </span>
      </div>

      {/* Progress Bar */}
      <div className="w-full h-2 bg-black/20 rounded-full overflow-hidden">
        <div 
          className={`h-full transition-all duration-500 ease-out ${barColor}`} 
          style={{ width: `${percent}%` }} 
        />
      </div>

      {/* Stats Footer */}
      <div className="flex items-center justify-between text-xs">
        <span className="text-emerald-100/70">
          Used: {status.consumed_today.toFixed(1)}
        </span>
        <span className={`font-semibold ${textColor}`}>
           {isDanger 
             ? `Over by ${Math.abs(status.remaining).toFixed(0)}` 
             : `${status.remaining.toFixed(0)} left`}
        </span>
      </div>
    </div>
  );
};

// ==========================================
// 3. MAIN APP COMPONENT
// ==========================================

function App() {
  const [page, setPage] = useState<"chat" | "vision">("chat");
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [userId, setUserId] = useState<string | null>(null);
  
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 1,
      role: "assistant",
      content: "Hi! Tell me what you've eaten, or ask if a food is OK. I'll track your daily nutrient limits.",
    },
  ]);

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [pendingImage, setPendingImage] = useState<File | null>(null);
  const [pendingPreview, setPendingPreview] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // NEW: Dynamic List of Statuses (Replaces fixed sugar/sodium variables)
  const [statuses, setStatuses] = useState<NutrientStatus[]>([]);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  // --- LOGOUT ---
  const handleLogout = () => {
    setIsLoggedIn(false);
    setUserId(null);
    setThreadId(null);
    setMessages([]); // Clear chat
    setStatuses([]); // Clear stats
  };

  // --- SCROLL TO BOTTOM ---
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // --- LOAD SESSION ON MOUNT ---
  useEffect(() => {
    async function loadSession() {
      if (!userId) return;
      try {
        const res = await fetch(`${API_BASE_URL}/api/v1/chat/session-state?user_id=${encodeURIComponent(userId)}`);
        if (!res.ok) return;

        const data = (await res.json()) as SessionStateResponse;
        setThreadId(data.thread_id);

        // Load History
        if (data.messages && data.messages.length > 0) {
          const uiMessages: ChatMessage[] = data.messages.map((m, idx) => ({
            id: Date.now() + idx,
            role: m.role === "human" ? "user" : "assistant",
            content: m.content,
          }));
          setMessages(uiMessages);
        }

        // Load Statuses if available
        if (data.protocol_statuses) {
            setStatuses(data.protocol_statuses);
        }

      } catch (err) {
        console.error("Session load error", err);
      }
    }
    if (isLoggedIn && userId) loadSession();
  }, [isLoggedIn, userId]);

  const clearPendingImage = () => {
    setPendingImage(null);
    if (pendingPreview) URL.revokeObjectURL(pendingPreview);
    setPendingPreview(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const onPickImage = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0] ?? null;
    if (pendingPreview) URL.revokeObjectURL(pendingPreview);
    setPendingImage(selected);
    setPendingPreview(selected ? URL.createObjectURL(selected) : null);
  };

  // --- SEND MESSAGE ---
  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (loading || !userId) return;

    // Image without text → ask for a prompt (client-side; server also enforces)
    if (pendingImage && !trimmed) {
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now(),
          role: "assistant",
          content:
            'I see a meal photo. Please tell me what you want to do — for example "I ate this" or "Can I have this?" — then send again.',
        },
      ]);
      return;
    }

    if (!trimmed && !pendingImage) return;

    const displayContent = pendingImage
      ? `📷 ${pendingImage.name}\n${trimmed}`
      : trimmed;

    const userMsg: ChatMessage = { id: Date.now(), role: "user", content: displayContent };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    const imageToSend = pendingImage;
    clearPendingImage();

    try {
      let res: Response;
      if (imageToSend) {
        const body = new FormData();
        body.append("user_id", userId);
        body.append("message", trimmed);
        if (threadId) body.append("thread_id", threadId);
        body.append("file", imageToSend);
        res = await fetch(`${API_BASE_URL}/api/v1/chat/message-with-image`, {
          method: "POST",
          body,
        });
      } else {
        res = await fetch(`${API_BASE_URL}/api/v1/chat/message`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            user_id: userId,
            message: trimmed,
            thread_id: threadId ?? undefined,
          }),
        });
      }

      if (!res.ok) {
        let detail = `HTTP Error: ${res.status}`;
        try {
          const errBody = await res.json();
          if (errBody?.detail) {
            detail = typeof errBody.detail === "string" ? errBody.detail : JSON.stringify(errBody.detail);
          }
        } catch {
          /* ignore */
        }
        throw new Error(detail);
      }

      const data = (await res.json()) as ChatResponse;
      setThreadId(data.thread_id ?? threadId);

      const aiMsg: ChatMessage = {
        id: Date.now() + 1,
        role: "assistant",
        content: data.response ?? "...",
      };
      setMessages((prev) => [...prev, aiMsg]);
      console.log(data);
      if (data.protocol_statuses && data.protocol_statuses.length > 0) {
        if (data.action_type === "ACTUAL") {
          setStatuses(data.protocol_statuses);
        }
      }
    } catch (err) {
      console.error(err);
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now(),
          role: "assistant",
          content:
            err instanceof Error
              ? `Sorry — ${err.message}`
              : "Error connecting to server.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  // --- Food Vision POC page (no login required) ---
  if (page === "vision") {
    return <FoodVisionPage onBack={() => setPage("chat")} />;
  }

  // --- RENDER LOGIN ---
  if (!isLoggedIn) {
    return (
      <LoginScreen
        setUserId={setUserId}
        setIsLoggedIn={setIsLoggedIn}
        onOpenVision={() => setPage("vision")}
      />
    );
  }

  // --- RENDER MAIN UI ---
  return (
    <div className="min-h-screen bg-slate-100 flex items-center justify-center px-4 font-sans">
      <div className="w-full max-w-6xl h-[85vh] bg-white rounded-3xl shadow-2xl overflow-hidden flex">
        
        {/* === LEFT SIDEBAR (LIVE DASHBOARD) === */}
        <aside className="hidden md:flex flex-col w-80 bg-slate-900 text-white p-6 overflow-y-auto">
          <div className="mb-8">
            <h1 className="text-xl font-bold bg-gradient-to-r from-emerald-400 to-teal-300 bg-clip-text text-transparent">
              Agentic Dietician
            </h1>
            <p className="text-xs text-slate-400 mt-1">Multi-Agent Nutrition Assistant</p>
          </div>

          {/* User Info */}
          <div className="flex items-center gap-3 mb-6 p-3 bg-white/5 rounded-xl border border-white/10 min-w-0">
            <div className="w-10 h-10 shrink-0 rounded-full bg-emerald-500 flex items-center justify-center font-bold text-white text-sm leading-none">
              {(userId?.match(/\d+/)?.[0] ?? userId ?? "?").slice(-2)}
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-sm font-semibold text-white truncate">User {userId}</div>
              <div className="text-[10px] text-emerald-400 uppercase tracking-wider">Active Session</div>
            </div>
          </div>

          {/* DYNAMIC PROGRESS BARS */}
          <div className="flex-1">
             <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">
                Daily Limits
             </h3>
             
             {statuses.length === 0 ? (
                <div className="text-sm text-slate-500 italic text-center mt-10">
                   Log a meal to see your tracking data.
                </div>
             ) : (
                statuses.map((status) => (
                    <NutrientCard key={status.name} status={status} />
                ))
             )}
          </div>
          
          <div className="mt-6 text-[10px] text-slate-600 text-center">
            AI estimates provided for guidance only.
          </div>
        </aside>

        {/* === RIGHT CHAT PANEL === */}
        <main className="flex-1 flex flex-col bg-slate-50 relative">
          
          {/* Header */}
          <header className="h-16 bg-white border-b border-slate-200 flex items-center justify-between px-6 shadow-sm z-10">
             <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                <span className="text-sm font-semibold text-slate-700">Live Assistant</span>
             </div>
             <div className="flex items-center gap-4">
             <button
                onClick={() => setPage("vision")}
                className="text-xs font-medium text-emerald-600 hover:text-emerald-700 transition-colors"
             >
                Food Vision
             </button>
             <button 
                onClick={handleLogout}
                className="text-xs font-medium text-slate-500 hover:text-red-500 transition-colors"
             >
                Log Out
             </button>
             </div>
          </header>

          {/* Chat Area */}
          <div className="flex-1 overflow-y-auto p-6 space-y-4">
            {messages.map((msg) => (
              <div key={msg.id} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[85%] rounded-2xl px-5 py-3 text-sm leading-relaxed shadow-sm ${
                    msg.role === "user" 
                    ? "bg-emerald-600 text-white rounded-br-none" 
                    : "bg-white text-slate-700 border border-slate-100 rounded-bl-none"
                }`}>
                  {msg.role === "assistant" ? (
                    <div className="chat-md space-y-2 [&_h2]:text-base [&_h2]:font-bold [&_h2]:text-slate-800 [&_h3]:text-sm [&_h3]:font-semibold [&_h3]:text-amber-700 [&_strong]:font-semibold [&_strong]:text-slate-900 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5 [&_li]:my-0.5 [&_hr]:my-3 [&_hr]:border-slate-200 [&_p]:my-1.5 whitespace-pre-wrap">
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>
                  ) : (
                    <div className="whitespace-pre-wrap">{msg.content}</div>
                  )}
                </div>
              </div>
            ))}
            {loading && (
               <div className="flex justify-start">
                  <div className="bg-white px-4 py-3 rounded-2xl rounded-bl-none border border-slate-100 shadow-sm">
                     <div className="flex gap-1">
                        <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce"></span>
                        <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce delay-75"></span>
                        <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce delay-150"></span>
                     </div>
                  </div>
               </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Area */}
          <div className="p-4 bg-white border-t border-slate-200 space-y-3">
            {pendingPreview && (
              <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 p-2">
                <img
                  src={pendingPreview}
                  alt="Meal preview"
                  className="h-14 w-14 rounded-lg object-cover"
                />
                <div className="min-w-0 flex-1">
                  <div className="text-xs font-medium text-slate-700 truncate">
                    {pendingImage?.name}
                  </div>
                  <div className="text-[11px] text-slate-500">
                    Add a message like “I ate this” then send
                  </div>
                </div>
                <button
                  type="button"
                  onClick={clearPendingImage}
                  className="text-xs text-slate-500 hover:text-red-500 px-2"
                >
                  Remove
                </button>
              </div>
            )}
            <form onSubmit={handleSend} className="relative flex items-center gap-2">
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={onPickImage}
              />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={loading}
                className="shrink-0 bg-slate-100 hover:bg-slate-200 disabled:opacity-50 text-slate-700 rounded-xl px-3 py-3 text-sm font-medium"
                title="Attach meal photo"
              >
                📷
              </button>
              <input
                className="flex-1 bg-slate-100 text-slate-900 placeholder-slate-400 text-sm rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:bg-white transition-all"
                placeholder={
                  pendingImage
                    ? 'e.g. "I ate this" or "Can I have this?"'
                    : "Type 'I ate a banana' or attach a meal photo..."
                }
                value={input}
                onChange={(e) => setInput(e.target.value)}
              />
              <button
                type="submit"
                disabled={loading || (!input.trim() && !pendingImage)}
                className="bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl px-6 py-3 text-sm font-semibold transition-transform active:scale-95 shadow-lg shadow-emerald-200"
              >
                Send
              </button>
            </form>
          </div>

        </main>
      </div>
    </div>
  );
}

// ==========================================
// 4. LOGIN SCREEN (Unchanged)
// ==========================================
const LoginScreen = ({
  setUserId,
  setIsLoggedIn,
  onOpenVision,
}: {
  setUserId: (id: string) => void;
  setIsLoggedIn: (status: boolean) => void;
  onOpenVision?: () => void;
}) => {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');

    const handleLogin = (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        const raw = username.trim().toUpperCase();
        // Accept 1, 2, P-001, P-002 (backend maps to numeric user ids)
        if (/^\d+$/.test(raw) || /^P-\d+$/.test(raw)) {
            setUserId(raw);
            setIsLoggedIn(true);
        } else {
            setError("Use 1, 2, or P-001 / P-002");
        }
    };

    return (
        <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
            <div className="w-full max-w-sm bg-white p-8 rounded-2xl shadow-xl border border-slate-100">
                <div className="text-center mb-8">
                    <h2 className="text-2xl font-bold text-slate-800">Welcome Back</h2>
                    <p className="text-slate-500 text-sm mt-2">Sign in to your dietitian dashboard</p>
                </div>
                <form onSubmit={handleLogin} className="space-y-4">
                    <div>
                        <label className="block text-xs font-semibold text-slate-600 uppercase mb-1">Patient ID</label>
                        <input value={username} onChange={e => setUsername(e.target.value)} className="w-full border border-slate-300 rounded-lg px-4 py-2 focus:ring-2 focus:ring-emerald-500 outline-none" placeholder="e.g. 1 or P-002" />
                    </div>
                    <div>
                        <label className="block text-xs font-semibold text-slate-600 uppercase mb-1">Password</label>
                        <input type="password" value={password} onChange={e => setPassword(e.target.value)} className="w-full border border-slate-300 rounded-lg px-4 py-2 focus:ring-2 focus:ring-emerald-500 outline-none" placeholder="••••••" />
                    </div>
                    {error && <div className="text-red-500 text-sm text-center">{error}</div>}
                    <button type="submit" className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-semibold py-3 rounded-lg transition-colors">Sign In</button>
                </form>
                {onOpenVision && (
                  <button
                    type="button"
                    onClick={onOpenVision}
                    className="mt-4 w-full text-sm text-emerald-700 hover:text-emerald-800 font-medium"
                  >
                    Or try Food Vision (Gemini image POC) →
                  </button>
                )}
            </div>
        </div>
    );
};

export default App;