import { useState } from "react";
import { api } from "../api";
import EntryCard from "../components/EntryCard";

export default function Search() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);

  async function search(e) {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    try {
      const data = await api.search(query);
      setResults(data);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h1 className="text-xl font-semibold mb-6">Search</h1>

      <form onSubmit={search} className="flex gap-3 mb-8">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="What are you looking for?"
          className="flex-1 bg-neutral-900 border border-neutral-700 rounded px-4 py-2 text-sm text-neutral-200 placeholder-neutral-600 focus:outline-none focus:border-neutral-500"
        />
        <button
          type="submit"
          disabled={loading}
          className="px-5 py-2 bg-white text-neutral-950 rounded text-sm font-medium hover:bg-neutral-200 disabled:opacity-50 transition-colors"
        >
          {loading ? "..." : "Search"}
        </button>
      </form>

      {results !== null && (
        results.length === 0 ? (
          <p className="text-sm text-neutral-500">No results found.</p>
        ) : (
          <div className="space-y-3">
            {results.map((r) => (
              <EntryCard key={r.id} entry={r} score={r.score} />
            ))}
          </div>
        )
      )}
    </div>
  );
}
