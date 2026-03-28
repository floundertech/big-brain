import { useState, useRef, useEffect } from "react";
import { api } from "../api";
import Markdown from "../components/Markdown";

export default function Chat() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sources, setSources] = useState([]);
  const bottomRef = useRef();

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function send(e) {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMsg = { role: "user", content: input };
    const next = [...messages, userMsg];
    setMessages(next);
    setInput("");
    setLoading(true);

    try {
      const res = await api.chat(next);
      setMessages([...next, { role: "assistant", content: res.answer }]);
      setSources(res.sources);
    } catch (err) {
      setMessages([...next, { role: "assistant", content: `Error: ${err.message}` }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-9rem)]">
      <h1 className="text-xl font-semibold mb-4">Chat</h1>

      <div className="flex-1 overflow-y-auto space-y-4 pr-1 mb-4">
        {messages.length === 0 && (
          <p className="text-sm text-neutral-500">
            Ask anything about your notes. Claude will search your knowledge base to answer.
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[80%] rounded-lg px-4 py-2.5 text-sm leading-relaxed ${
                m.role === "user"
                  ? "bg-white text-neutral-950"
                  : "bg-neutral-800 text-neutral-200"
              }`}
            >
              {m.role === "assistant" ? <Markdown content={m.content} /> : m.content}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-neutral-800 rounded-lg px-4 py-2.5 text-sm text-neutral-400">
              Thinking...
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {sources.length > 0 && (
        <div className="mb-3 flex flex-wrap gap-2">
          {sources.map((s) => (
            <a
              key={s.id}
              href={`/entry/${s.id}`}
              className="text-xs text-neutral-500 hover:text-neutral-300 border border-neutral-800 rounded px-2 py-0.5 transition-colors"
            >
              {s.title}
            </a>
          ))}
        </div>
      )}

      <form onSubmit={send} className="flex gap-3">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question..."
          disabled={loading}
          className="flex-1 bg-neutral-900 border border-neutral-700 rounded px-4 py-2.5 text-sm text-neutral-200 placeholder-neutral-600 focus:outline-none focus:border-neutral-500 disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="px-5 py-2 bg-white text-neutral-950 rounded text-sm font-medium hover:bg-neutral-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          Send
        </button>
      </form>
    </div>
  );
}
