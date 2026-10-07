import React, { useEffect, useRef, useState } from "react";

type ChatMessage = {
  id: number;
  role: "user" | "assistant";
  content: string;
};

type ProtocolFacts = {
  limit: string;
  consumed: string;
  remaining: number;
  is_violated: boolean;
};

type TodayConsumption = {
  sugar_g: number;
  sodium_mg: number;
};

const API_BASE_URL = "http://localhost:8000"; // adjust if needed
const DEMO_USER_ID = "P-001";

function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 1,
      role: "assistant",
      content:
        "Hi, I’m your Dietitian Assistant. Tell me what you’ve eaten today, and I’ll help you stay within your sugar limits.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [threadId, setThreadId] = useState<string | null>(null);

  const [protocolFacts, setProtocolFacts] = useState<ProtocolFacts | null>(
    null
  );
  const [todayConsumption, setTodayConsumption] =
    useState<TodayConsumption | null>(null);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  // 🔹 Load today's session (messages + sugar state) on first render
  useEffect(() => {
    async function loadSession() {
      try {
        const res = await fetch(
          `${API_BASE_URL}/api/v1/chat/session-state?user_id=${DEMO_USER_ID}`
        );

        if (!res.ok) {
          console.error("Failed to load session state");
          return;
        }

        const data = await res.json();

        // 1) Messages: only override default greeting if backend has any
        if (data.messages && data.messages.length > 0) {
          const uiMessages: ChatMessage[] = data.messages.map(
            (m: { role: string; content: string }, index: number) => ({
              id: Date.now() + index,
              role: m.role === "user" ? "user" : "assistant",
              content: m.content,
            })
          );
          setMessages(uiMessages);
        }

        // 2) Protocol facts (left panel)
        if (data.protocol_facts) {
          setProtocolFacts(data.protocol_facts as ProtocolFacts);
        }

        // 3) Today's consumption
        if (data.today_consumption) {
          setTodayConsumption(data.today_consumption as TodayConsumption);
        }

        // 4) Thread id
        if (data.thread_id) {
          setThreadId(data.thread_id as string);
        }
      } catch (err) {
        console.error("Error loading session:", err);
      }
    }

    loadSession();
  }, []);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || loading) return;

    // Add user message locally
    const userMsg: ChatMessage = {
      id: Date.now(),
      role: "user",
      content: trimmed,
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/chat/message`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          user_id: DEMO_USER_ID,
          message: trimmed,
          thread_id: threadId,
        }),
      });

      if (!res.ok) {
        throw new Error(`HTTP error ${res.status}`);
      }

      const data = await res.json();

      // Add assistant message from API
      const aiMsg: ChatMessage = {
        id: Date.now() + 1,
        role: "assistant",
        content: data.response ?? "No response from assistant.",
      };

      setMessages((prev) => [...prev, aiMsg]);

      // Store thread id (for continuity)
      if (data.thread_id && !threadId) {
        setThreadId(data.thread_id);
      }

      // Update protocol facts + today consumption from debug fields
      if (data.debug_protocol_facts) {
        setProtocolFacts(data.debug_protocol_facts as ProtocolFacts);
      }
      if (data.debug_today_consumption) {
        setTodayConsumption(data.debug_today_consumption as TodayConsumption);
      }
    } catch (err) {
      console.error(err);
      const errMsg: ChatMessage = {
        id: Date.now() + 2,
        role: "assistant",
        content:
          "Sorry, I ran into a technical issue talking to the dietitian service.",
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setLoading(false);
    }
  };

  // Derived values for left panel
  const sugarLimitLabel =
    protocolFacts?.limit != null ? protocolFacts.limit : "30 g";
  let sugarLimitNumeric = 30;
  const firstToken = sugarLimitLabel.split(" ")[0];
  const parsedLimit = parseFloat(firstToken);
  if (!isNaN(parsedLimit)) {
    sugarLimitNumeric = parsedLimit;
  }

  const consumedToday = todayConsumption?.sugar_g ?? 0;

  // Actual remaining based ONLY on what has been taken
  const remainingActual = sugarLimitNumeric - consumedToday;

  const progressPercent =
    sugarLimitNumeric > 0
      ? Math.min(100, Math.max(0, (consumedToday / sugarLimitNumeric) * 100))
      : 0;

  const isOverLimitActual = remainingActual < 0;

  const statusText =
    consumedToday === 0
      ? "No intake logged yet"
      : isOverLimitActual
      ? `Over limit by ${Math.abs(remainingActual).toFixed(1)} g`
      : `Within limit • ${remainingActual.toFixed(1)} g left`;

  const statusDotClass =
    consumedToday === 0
      ? "bg-slate-300"
      : isOverLimitActual
      ? "bg-red-300"
      : "bg-emerald-300";

  return (
    <div className="min-h-screen bg-slate-100 flex items-center justify-center px-4">
      <div className="w-full max-w-6xl h-[80vh] bg-white rounded-3xl shadow-2xl overflow-hidden flex">
        {/* Left sidebar */}
        <aside className="hidden md:flex flex-col w-1/3 bg-gradient-to-b from-emerald-500 to-teal-600 text-white p-6 gap-6">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">
              Dietitian Companion
            </h1>
            <p className="text-sm text-emerald-100 mt-1">
              Gentle, protocol-aware guidance for your day.
            </p>
          </div>

          {/* Patient card */}
          <div className="bg-white/10 rounded-2xl p-4 flex items-center gap-3">
            <div className="w-12 h-12 rounded-full bg-white/20 flex items-center justify-center text-lg font-semibold">
              P
            </div>
            <div>
              <div className="text-sm font-semibold">
                Patient ID: {DEMO_USER_ID}
              </div>
              <div className="text-xs text-emerald-100">
                Today: Sugar monitoring active
              </div>
            </div>
          </div>

          {/* Protocol summary (driven by API data) */}
          <div className="bg-white/10 rounded-2xl p-4 flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold">Daily sugar limit</span>
              <span className="text-sm font-bold">{sugarLimitLabel}</span>
            </div>

            <div className="flex items-center justify-between text-xs text-emerald-100">
              <span>Consumed today</span>
              <span>{consumedToday.toFixed(1)} g</span>
            </div>

            <div className="w-full h-2 bg-emerald-900/40 rounded-full overflow-hidden">
              <div
                className="h-full bg-emerald-200"
                style={{ width: `${progressPercent}%` }}
              ></div>
            </div>

            <div className="flex items-center justify-between text-xs text-emerald-100 mt-1">
              <span>Remaining</span>
              <span>{`${remainingActual.toFixed(1)} g`}</span>
            </div>

            <div className="mt-3 inline-flex items-center gap-2 text-xs bg-emerald-900/40 px-3 py-1.5 rounded-full">
              <span className={`w-2 h-2 rounded-full ${statusDotClass}`} />
              {statusText}
            </div>
          </div>

          <div className="mt-auto text-xs text-emerald-100">
            This is a demo UI. Values are loaded live from your Python
            microservice.
          </div>
        </aside>

        {/* Right chat panel */}
        <main className="flex-1 flex flex-col bg-slate-50">
          {/* Header */}
          <header className="h-16 border-b border-slate-200 flex items-center justify-between px-4 md:px-6 bg-white">
            <div>
              <div className="text-sm font-semibold text-slate-800">
                Dietitian Chat
              </div>
              <div className="text-xs text-slate-500">
                Ask about what you’ve eaten or plan to eat today.
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-500">Logged in as</span>
              <span className="text-xs font-semibold bg-slate-100 px-2 py-1 rounded-full">
                {DEMO_USER_ID}
              </span>
            </div>
          </header>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-4 md:px-6 py-4 space-y-3">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex ${
                  msg.role === "user" ? "justify-end" : "justify-start"
                }`}
              >
                <div
                  className={`max-w-[80%] rounded-2xl px-3 py-2 text-sm shadow-sm ${
                    msg.role === "user"
                      ? "bg-emerald-500 text-white rounded-br-sm"
                      : "bg-white text-slate-800 rounded-bl-sm"
                  }`}
                >
                  {msg.content}
                </div>
              </div>
            ))}

            {/* AI thinking indicator */}
            {loading && (
              <div className="flex justify-start">
                <div className="inline-flex items-center gap-2 text-xs text-slate-500 bg-white px-3 py-2 rounded-2xl shadow-sm">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                  Dietitian is thinking…
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="border-t border-slate-200 bg-white px-4 md:px-6 py-3">
            <form className="flex items-center gap-2" onSubmit={handleSend}>
              <textarea
                className="flex-1 resize-none rounded-2xl border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-400 focus:border-emerald-400 max-h-24"
                rows={1}
                placeholder="Describe what you’ve eaten or ask if a food fits your protocol..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
              />
              <button
                type="submit"
                disabled={loading || !input.trim()}
                className="inline-flex items-center justify-center rounded-2xl bg-emerald-500 text-white text-sm font-medium px-4 py-2 hover:bg-emerald-600 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {loading ? "Sending..." : "Send"}
              </button>
            </form>
          </div>
        </main>
      </div>
    </div>
  );
}

export default App;
