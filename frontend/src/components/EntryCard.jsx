import { Link } from "react-router-dom";

export default function EntryCard({ entry, score }) {
  const date = new Date(entry.created_at).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });

  return (
    <Link
      to={`/entry/${entry.id}`}
      className="block p-4 rounded-lg border border-neutral-800 hover:border-neutral-600 bg-neutral-900 hover:bg-neutral-800 transition-all"
    >
      <div className="flex items-start justify-between gap-4">
        <h3 className="text-sm font-medium text-white leading-snug">{entry.title}</h3>
        {score != null && (
          <span className="text-xs text-neutral-500 shrink-0">{Math.round(score * 100)}%</span>
        )}
      </div>
      {entry.summary && (
        <p className="mt-1 text-xs text-neutral-400 line-clamp-2">{entry.summary}</p>
      )}
      <div className="mt-3 flex items-center gap-3 flex-wrap">
        <span className="text-xs text-neutral-600">{date}</span>
        <span
          className={`text-xs px-1.5 py-0.5 rounded ${
            entry.source_type === "transcript"
              ? "bg-blue-950 text-blue-400"
              : "bg-neutral-800 text-neutral-400"
          }`}
        >
          {entry.source_type}
        </span>
        {entry.tags.slice(0, 4).map((tag) => (
          <span key={tag} className="text-xs text-neutral-500">
            #{tag}
          </span>
        ))}
      </div>
    </Link>
  );
}
