import { useState, useEffect, useRef } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { api } from "../api";


function InlineEdit({ value, onSave, multiline = false, className = "" }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value || "");
  const ref = useRef(null);

  useEffect(() => {
    if (editing && ref.current) {
      ref.current.focus();
      if (multiline) {
        ref.current.style.height = "auto";
        ref.current.style.height = ref.current.scrollHeight + "px";
      }
    }
  }, [editing]);

  function save() {
    setEditing(false);
    if (draft !== (value || "")) onSave(draft);
  }

  if (!editing) {
    return (
      <span
        onClick={() => { setDraft(value || ""); setEditing(true); }}
        className={`cursor-pointer hover:ring-1 hover:ring-neutral-600 rounded px-1 -mx-1 transition-all ${className}`}
        title="Click to edit"
      >
        {value || <span className="text-neutral-600 italic">Click to add</span>}
      </span>
    );
  }

  if (multiline) {
    return (
      <textarea
        ref={ref}
        value={draft}
        onChange={(e) => {
          setDraft(e.target.value);
          e.target.style.height = "auto";
          e.target.style.height = e.target.scrollHeight + "px";
        }}
        onBlur={save}
        onKeyDown={(e) => {
          if (e.key === "Escape") { setDraft(value || ""); setEditing(false); }
        }}
        className={`w-full bg-neutral-800 border border-neutral-600 rounded px-2 py-1 text-neutral-300 focus:outline-none focus:border-neutral-400 resize-none ${className}`}
      />
    );
  }

  return (
    <input
      ref={ref}
      value={draft}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={save}
      onKeyDown={(e) => {
        if (e.key === "Enter") save();
        if (e.key === "Escape") { setDraft(value || ""); setEditing(false); }
      }}
      className={`w-full bg-neutral-800 border border-neutral-600 rounded px-2 py-1 text-neutral-300 focus:outline-none focus:border-neutral-400 ${className}`}
    />
  );
}


function TagEditor({ tags, onSave }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(tags.join(", "));
  const ref = useRef(null);

  useEffect(() => { if (editing) ref.current?.focus(); }, [editing]);

  function save() {
    setEditing(false);
    const newTags = draft.split(",").map((t) => t.trim().replace(/^#/, "")).filter(Boolean);
    if (JSON.stringify(newTags) !== JSON.stringify(tags)) onSave(newTags);
  }

  if (!editing) {
    return (
      <span
        onClick={() => { setDraft(tags.join(", ")); setEditing(true); }}
        className="cursor-pointer hover:ring-1 hover:ring-neutral-600 rounded px-1 -mx-1 transition-all inline-flex gap-2 flex-wrap"
        title="Click to edit tags"
      >
        {tags.length > 0 ? tags.map((tag) => (
          <span key={tag} className="text-sm text-neutral-500">#{tag}</span>
        )) : (
          <span className="text-sm text-neutral-600 italic">Click to add tags</span>
        )}
      </span>
    );
  }

  return (
    <input
      ref={ref}
      value={draft}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={save}
      onKeyDown={(e) => {
        if (e.key === "Enter") save();
        if (e.key === "Escape") { setDraft(tags.join(", ")); setEditing(false); }
      }}
      placeholder="tag1, tag2, tag3"
      className="text-sm bg-neutral-800 border border-neutral-600 rounded px-2 py-0.5 text-neutral-300 focus:outline-none focus:border-neutral-400"
    />
  );
}


export default function EntryDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [entry, setEntry] = useState(null);
  const [entities, setEntities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState(false);
  const [saving, setSaving] = useState(false);

  function load() {
    api.entries.get(id).then(setEntry).finally(() => setLoading(false));
    api.entities.list({ entry_id: id }).then(setEntities);
  }

  useEffect(() => { load(); }, [id]);

  async function save(updates) {
    setSaving(true);
    try {
      const updated = await api.entries.update(id, updates);
      setEntry(updated);
    } finally {
      setSaving(false);
    }
  }

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
      <div className="flex items-center justify-between mb-6">
        <Link to="/" className="text-sm text-neutral-500 hover:text-neutral-300 transition-colors">
          ← Back
        </Link>
        {saving && <span className="text-xs text-blue-400">Saving...</span>}
      </div>

      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-white mb-2">
          <InlineEdit
            value={entry.title}
            onSave={(title) => save({ title })}
            className="text-2xl font-semibold"
          />
        </h1>
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
          <TagEditor tags={entry.tags} onSave={(tags) => save({ tags })} />
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

      <div className="mb-6 p-4 bg-neutral-900 border border-neutral-800 rounded-lg">
        <p className="text-xs text-neutral-500 mb-1.5 font-medium uppercase tracking-wide">Summary</p>
        <InlineEdit
          value={entry.summary}
          onSave={(summary) => save({ summary })}
          multiline
          className="text-sm leading-relaxed"
        />
      </div>

      <div className="mb-8">
        <p className="text-xs text-neutral-500 mb-3 font-medium uppercase tracking-wide">Full text</p>
        <InlineEdit
          value={entry.raw_text}
          onSave={(raw_text) => save({ raw_text })}
          multiline
          className="text-sm leading-relaxed whitespace-pre-wrap"
        />
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
