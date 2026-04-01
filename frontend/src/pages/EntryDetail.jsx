import { useState, useEffect } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { api } from "../api";


export default function EntryDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [entry, setEntry] = useState(null);
  const [entities, setEntities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    api.entries.get(id).then(setEntry).finally(() => setLoading(false));
    api.entities.list({ entry_id: id }).then(setEntities);
  }, [id]);

  async function handleDelete() {
    if (!confirm("Delete this entry?")) return;
    setDeleting(true);
    await api.entries.delete(id);
    navigate("/");
  }

  if (loading) return <div className="text-neutral-500 text-sm">Loading...</div>;
  if (!entry) return <div className="text-neutral-500 text-sm">Not found.</div>;

  const date = new Date(entry.created_at).toLocaleDateString("en-US", {
    weekday: "short",
    month: "long",
    day: "numeric",
    year: "numeric",
  });

  return (
    <div className="max-w-2xl">
      <div className="flex items-center gap-3 mb-6">
        <Link to="/" className="text-sm text-neutral-500 hover:text-neutral-300 transition-colors">
          ← Back
        </Link>
      </div>

      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-white mb-2">{entry.title}</h1>
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-sm text-neutral-500">{date}</span>
          <span
            className={`text-xs px-1.5 py-0.5 rounded ${
              entry.source_type === "transcript"
                ? "bg-blue-950 text-blue-400"
                : "bg-neutral-800 text-neutral-400"
            }`}
          >
            {entry.source_type}
          </span>
          {entry.tags.map((tag) => (
            <span key={tag} className="text-sm text-neutral-500">
              #{tag}
            </span>
          ))}
        </div>
        {entities.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-2">
            {entities.map((e) => (
              <Link
                key={e.id}
                to={`/entity/${e.id}`}
                className={`text-xs px-2 py-0.5 rounded border transition-colors ${
                  e.entity_type === "contact"
                    ? "border-violet-800 text-violet-400 hover:border-violet-600"
                    : "border-amber-900 text-amber-500 hover:border-amber-700"
                }`}
              >
                {e.name}
              </Link>
            ))}
          </div>
        )}
      </div>

      {entry.summary && (
        <div className="mb-6 p-4 bg-neutral-900 border border-neutral-800 rounded-lg">
          <p className="text-xs text-neutral-500 mb-1.5 font-medium uppercase tracking-wide">Summary</p>
          <p className="text-sm text-neutral-300 leading-relaxed">{entry.summary}</p>
        </div>
      )}

      <div className="mb-8">
        <p className="text-xs text-neutral-500 mb-3 font-medium uppercase tracking-wide">Full text</p>
        <div className="text-sm text-neutral-300 leading-relaxed whitespace-pre-wrap">{entry.raw_text}</div>
      </div>

      <button
        onClick={handleDelete}
        disabled={deleting}
        className="text-sm text-red-500 hover:text-red-400 disabled:opacity-50 transition-colors"
      >
        {deleting ? "Deleting..." : "Delete entry"}
      </button>
    </div>
  );
}
