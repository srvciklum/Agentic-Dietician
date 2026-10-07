import React from "react";

type ChatMessage = {
  id: number;
  role: "user" | "assistant";
  content: string;
};

const mockMessages: ChatMessage[] = [
  {
    id: 1,
    role: "assistant",
    content:
      "Hi, I’m your Dietitian Assistant. Tell me what you’ve eaten today, and I’ll help you stay within your sugar limits.",
  },
  {
    id: 2,
    role: "user",
    content: "I had a muffin with 12 grams of sugar this morning.",
  },
  {
    id: 3,
    role: "assistant",
    content:
      "Got it. You’ve logged 12 grams so far. You still have room left within your daily limit.",
  },
];

function App() {
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
              <div className="text-sm font-semibold">Patient ID: P-001</div>
              <div className="text-xs text-emerald-100">
                Today: Sugar monitoring active
              </div>
            </div>
          </div>

          {/* Protocol summary */}
          <div className="bg-white/10 rounded-2xl p-4 flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold">Daily sugar limit</span>
              <span className="text-sm font-bold">30 g</span>
            </div>

            <div className="flex items-center justify-between text-xs text-emerald-100">
              <span>Consumed</span>
              <span>12 g</span>
            </div>
            <div className="w-full h-2 bg-emerald-900/40 rounded-full overflow-hidden">
              <div
                className="h-full bg-emerald-200"
                style={{ width: "40%" }} // 12/30 ≈ 40%
              ></div>
            </div>

            <div className="flex items-center justify-between text-xs text-emerald-100 mt-1">
              <span>Remaining</span>
              <span>18 g</span>
            </div>

            <div className="mt-3 inline-flex items-center gap-2 text-xs bg-emerald-900/40 px-3 py-1.5 rounded-full">
              <span className="w-2 h-2 rounded-full bg-emerald-300" />
              Within limit and on track
            </div>
          </div>

          <div className="mt-auto text-xs text-emerald-100">
            This is a demo UI. Values will later be driven by the API response.
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
                P-001
              </span>
            </div>
          </header>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-4 md:px-6 py-4 space-y-3">
            {mockMessages.map((msg) => (
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
          </div>

          {/* Input */}
          <div className="border-t border-slate-200 bg-white px-4 md:px-6 py-3">
            <form className="flex items-center gap-2">
              <textarea
                className="flex-1 resize-none rounded-2xl border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-400 focus:border-emerald-400 max-h-24"
                rows={1}
                placeholder="Describe what you’ve eaten or ask if a food fits your protocol..."
              />
              <button
                type="button"
                className="inline-flex items-center justify-center rounded-2xl bg-emerald-500 text-white text-sm font-medium px-4 py-2 hover:bg-emerald-600 transition-colors"
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

export default App;
