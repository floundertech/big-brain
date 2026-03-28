import { useState, useEffect } from "react";
import { api } from "../api";
import EntryCard from "../components/EntryCard";

export default function Browse() {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState({ source_type: "" });

  useEffect(() => {
    setLoading(true);
    api.entries
      .list(filter.source_type ? { source_type: filter.source_type } : {})
      .then(setEntries)
      .finally(() => setLoading(false));
  }, [filter]);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold">Notes</h1>
        <select
          value={filter.source_type}
          onChange={(e) => setFilter({ source_type: e.target.value })}
          className="text-sm bg-neutral-900 border border-neutral-700 rounded px-3 py-1.5 text-neutral-300 focus:outline-none focus:border-neutral-500"
        >
          <option value="">All types</option>
          <option value="transcript">Transcripts</option>
          <option value="note">Notes</option>
          <option value="email">Email</option>
          <option value="research">Research</option>
          <option value="rss">RSS Articles</option>
          <option value="rss_digest">RSS Digests</option>
        </select>
      </div>

      {loading ? (
        <div className="text-neutral-500 text-sm">Loading...</div>
      ) : entries.length === 0 ? (
        <div className="text-neutral-500 text-sm">No entries yet. Add your first note.</div>
      ) : (
        <div className="space-y-3">
          {entries.map((entry) => (
            <EntryCard key={entry.id} entry={entry} />
          ))}
        </div>
      )}
    </div>
  );
}
