import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "../api";
import EntryCard from "../components/EntryCard";

export default function EntityDetail() {
  const { id } = useParams();
  const [entity, setEntity] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.entities.get(id).then(setEntity).finally(() => setLoading(false));
  }, [id]);

  if (loading) return <div className="text-neutral-500 text-sm">Loading...</div>;
  if (!entity) return <div className="text-neutral-500 text-sm">Not found.</div>;

  const typeLabel = entity.entity_type === "person" ? "Person" : "Organization";
  const typePill =
    entity.entity_type === "person"
      ? "border border-violet-800 text-violet-400"
      : "border border-amber-900 text-amber-500";

  return (
    <div className="max-w-2xl">
      <div className="flex items-center gap-3 mb-6">
        <Link to="/" className="text-sm text-neutral-500 hover:text-neutral-300 transition-colors">
          ← Back
        </Link>
      </div>

      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-white mb-2">{entity.name}</h1>
        <span className={`text-xs px-1.5 py-0.5 rounded ${typePill}`}>{typeLabel}</span>
      </div>

      <div>
        <p className="text-xs text-neutral-500 mb-3 font-medium uppercase tracking-wide">
          Mentioned in {entity.entries.length}{" "}
          {entity.entries.length === 1 ? "entry" : "entries"}
        </p>
        {entity.entries.length === 0 ? (
          <p className="text-sm text-neutral-500">No entries yet.</p>
        ) : (
          <div className="space-y-3">
            {entity.entries.map((entry) => (
              <EntryCard key={entry.id} entry={entry} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
