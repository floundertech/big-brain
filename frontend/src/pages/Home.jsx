import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import Markdown from "../components/Markdown";

function timeAgo(dateStr) {
  const now = new Date();
  const then = new Date(dateStr);
  const diff = Math.floor((now - then) / 1000);
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

const SOURCE_ICONS = {
  email: "\u{1F4E7}",
  rss: "\u{1F4F0}",
  rss_digest: "\u{1F4F0}",
  note: "\u{1F4DD}",
  transcript: "\u{1F399}\uFE0F",
  research: "\u{1F50D}",
};

export default function Home() {
  const navigate = useNavigate();
  const [digest, setDigest] = useState(null);
  const [digestNote, setDigestNote] = useState(null);
  const [activity, setActivity] = useState([]);
  const [suggestions, setSuggestions] = useState([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.home.digest().catch(() => ({ digest: null, note: "Could not load digest." })),
      api.home.activity().catch(() => ({ items: [] })),
      api.home.suggestions().catch(() => ({ suggestions: [] })),
    ]).then(([d, a, s]) => {
      setDigest(d.digest);
      setDigestNote(d.note || null);
      setActivity(a.items || []);
      setSuggestions(s.suggestions || []);
      setLoading(false);
    });
  }, []);

  const handleAsk = (q) => {
    if (!q.trim()) return;
    navigate(`/chat?q=${encodeURIComponent(q.trim())}`);
  };

  if (loading) {
    return <div className="text-neutral-500 text-sm">Loading...</div>;
  }

  return (
    <div className="space-y-8">
      {/* Section 1: Today's Digest */}
      <section>
        {digest ? (
          <div className="border border-neutral-800 rounded-lg p-6">
            <div className="flex items-start justify-between mb-1">
              <h2 className="text-lg font-semibold text-white">{digest.title}</h2>
            </div>
            {digest.summary && (
              <p className="text-sm text-neutral-400 mb-4">{digest.summary}</p>
            )}
            <div className="text-sm text-neutral-300 leading-relaxed">
              <Markdown content={digest.raw_text} />
            </div>
            <div className="mt-4 pt-3 border-t border-neutral-800">
              <button
                onClick={() => navigate(`/entry/${digest.id}`)}
                className="text-sm text-neutral-400 hover:text-white transition-colors"
              >
                View full digest &rarr;
              </button>
            </div>
          </div>
        ) : (
          <div className="border border-neutral-800 rounded-lg p-6 text-neutral-500 text-sm">
            {digestNote || "No digest available yet."}
          </div>
        )}
      </section>

      {/* Section 2: Recent Activity */}
      <section>
        <h2 className="text-sm font-semibold text-neutral-400 uppercase tracking-wider mb-3">
          Recent Activity
        </h2>
        {activity.length === 0 ? (
          <p className="text-neutral-500 text-sm">No recent activity.</p>
        ) : (
          <div className="space-y-2">
            {activity.map((item) => (
              <button
                key={item.id}
                onClick={() => navigate(`/entry/${item.id}`)}
                className="w-full flex items-center gap-3 px-3 py-2 rounded hover:bg-neutral-800/50 transition-colors text-left"
              >
                <span className="text-xs text-neutral-500 w-16 shrink-0 text-right">
                  {timeAgo(item.created_at)}
                </span>
                <span className="text-sm">{SOURCE_ICONS[item.source_type] || "\u{1F4C4}"}</span>
                <span className="text-sm text-neutral-300 truncate">
                  {item.title}
                </span>
              </button>
            ))}
          </div>
        )}
        <button
          onClick={() => navigate("/entries")}
          className="mt-2 text-sm text-neutral-500 hover:text-neutral-300 transition-colors"
        >
          View all &rarr;
        </button>
      </section>

      {/* Section 3: Quick Ask */}
      <section className="border border-neutral-800 rounded-lg p-6">
        <h2 className="text-sm font-semibold text-neutral-400 uppercase tracking-wider mb-3">
          Ask Big Brain
        </h2>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleAsk(query);
          }}
          className="flex gap-2"
        >
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="What's new in Dynatrace this week?"
            className="flex-1 bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm text-neutral-200 placeholder:text-neutral-600 focus:outline-none focus:border-neutral-500"
          />
          <button
            type="submit"
            className="px-4 py-2 bg-neutral-700 hover:bg-neutral-600 rounded text-sm font-medium transition-colors"
          >
            Ask
          </button>
        </form>
        {suggestions.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {suggestions.map((s, i) => (
              <button
                key={i}
                onClick={() => handleAsk(s)}
                className="text-xs text-neutral-500 hover:text-neutral-300 bg-neutral-800/50 hover:bg-neutral-800 rounded-full px-3 py-1 transition-colors"
              >
                {s}
              </button>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
