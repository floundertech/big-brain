import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";

export default function Entities() {
  const [entities, setEntities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("");
  const [search, setSearch] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [newEntity, setNewEntity] = useState({ entity_type: "contact", name: "" });
  const [creating, setCreating] = useState(false);

  function load() {
    setLoading(true);
    const params = {};
    if (filter) params.entity_type = filter;
    if (search) params.q = search;
    api.entities.list(params).then(setEntities).finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, [filter, search]);

  async function handleCreate(e) {
    e.preventDefault();
    if (!newEntity.name.trim()) return;
    setCreating(true);
    try {
      await api.entities.create(newEntity);
      setNewEntity({ entity_type: "contact", name: "" });
      setShowCreate(false);
      load();
    } finally {
      setCreating(false);
    }
  }

  const typePill = (type) =>
    type === "contact" ? "border border-violet-800 text-violet-400" :
    type === "account" ? "border border-amber-900 text-amber-500" :
    type === "opportunity" ? "border border-cyan-900 text-cyan-400" :
    "border border-neutral-700 text-neutral-400";

  const typeLabels = {
    contact: "Contact",
    account: "Account",
    organization: "Organization",
    opportunity: "Opportunity",
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold">Entities</h1>
        <div className="flex items-center gap-3">
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="text-sm bg-neutral-900 border border-neutral-700 rounded px-3 py-1.5 text-neutral-300 focus:outline-none focus:border-neutral-500"
          >
            <option value="">All types</option>
            <option value="contact">Contacts</option>
            <option value="account">Accounts</option>
            <option value="organization">Organizations</option>
            <option value="opportunity">Opportunities</option>
          </select>
          <button
            onClick={() => setShowCreate(!showCreate)}
            className="text-sm px-3 py-1.5 bg-neutral-800 hover:bg-neutral-700 text-neutral-300 rounded border border-neutral-700 transition-colors"
          >
            + New
          </button>
        </div>
      </div>

      <div className="mb-4">
        <input
          type="text"
          placeholder="Search entities..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full text-sm bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-neutral-300 placeholder-neutral-600 focus:outline-none focus:border-neutral-500"
        />
      </div>

      {showCreate && (
        <form onSubmit={handleCreate} className="mb-6 p-4 bg-neutral-900 border border-neutral-800 rounded-lg">
          <div className="flex items-end gap-3">
            <div>
              <label className="text-xs text-neutral-500 block mb-1">Type</label>
              <select
                value={newEntity.entity_type}
                onChange={(e) => setNewEntity({ ...newEntity, entity_type: e.target.value })}
                className="text-sm bg-neutral-800 border border-neutral-700 rounded px-3 py-1.5 text-neutral-300"
              >
                <option value="contact">Contact</option>
                <option value="account">Account</option>
                <option value="organization">Organization</option>
                <option value="opportunity">Opportunity</option>
              </select>
            </div>
            <div className="flex-1">
              <label className="text-xs text-neutral-500 block mb-1">Name</label>
              <input
                type="text"
                value={newEntity.name}
                onChange={(e) => setNewEntity({ ...newEntity, name: e.target.value })}
                placeholder="Entity name"
                className="w-full text-sm bg-neutral-800 border border-neutral-700 rounded px-3 py-1.5 text-neutral-300 placeholder-neutral-600 focus:outline-none focus:border-neutral-500"
              />
            </div>
            <button
              type="submit"
              disabled={creating || !newEntity.name.trim()}
              className="text-sm px-4 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded disabled:opacity-50 transition-colors"
            >
              {creating ? "Creating..." : "Create"}
            </button>
          </div>
        </form>
      )}

      {loading ? (
        <div className="text-neutral-500 text-sm">Loading...</div>
      ) : entities.length === 0 ? (
        <div className="text-neutral-500 text-sm">No entities found.</div>
      ) : (
        <div className="space-y-2">
          {entities.map((entity) => (
            <Link
              key={entity.id}
              to={`/entity/${entity.id}`}
              className="block p-4 rounded-lg border border-neutral-800 hover:border-neutral-600 bg-neutral-900 hover:bg-neutral-800 transition-all"
            >
              <div className="flex items-center gap-3">
                <span className="text-sm font-medium text-white">{entity.name}</span>
                <span className={`text-xs px-1.5 py-0.5 rounded ${typePill(entity.entity_type)}`}>
                  {typeLabels[entity.entity_type] || entity.entity_type}
                </span>
              </div>
              {entity.meta?.summary && (
                <p className="mt-1 text-xs text-neutral-400 line-clamp-1">{entity.meta.summary}</p>
              )}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
