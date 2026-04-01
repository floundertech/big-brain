import { useState, useEffect, useRef } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "../api";
import EntryCard from "../components/EntryCard";

function InlineEdit({ value, onSave, className = "" }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value || "");
  const inputRef = useRef(null);

  useEffect(() => { if (editing) inputRef.current?.focus(); }, [editing]);

  function save() {
    setEditing(false);
    if (draft !== (value || "")) onSave(draft);
  }

  if (!editing) {
    return (
      <span
        onClick={() => { setDraft(value || ""); setEditing(true); }}
        className={`cursor-pointer hover:text-white transition-colors ${className}`}
      >
        {value || <span className="text-neutral-600 italic">Click to edit</span>}
      </span>
    );
  }

  return (
    <input
      ref={inputRef}
      value={draft}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={save}
      onKeyDown={(e) => { if (e.key === "Enter") save(); if (e.key === "Escape") setEditing(false); }}
      className="bg-neutral-800 border border-neutral-600 rounded px-2 py-0.5 text-sm text-neutral-300 focus:outline-none focus:border-neutral-400"
    />
  );
}

function MetaField({ label, value, onSave }) {
  return (
    <div className="flex items-baseline gap-2 py-1">
      <span className="text-xs text-neutral-500 w-28 shrink-0">{label}:</span>
      <InlineEdit value={value} onSave={onSave} className="text-sm text-neutral-300" />
    </div>
  );
}

export default function EntityDetail() {
  const { id } = useParams();
  const [entity, setEntity] = useState(null);
  const [loading, setLoading] = useState(true);

  function load() {
    api.entities.get(id).then(setEntity).finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, [id]);

  async function updateMeta(field, value) {
    await api.entities.update(id, { meta: { [field]: value } });
    load();
  }

  async function updateName(name) {
    await api.entities.update(id, { name });
    load();
  }

  async function removeRelationship(relId) {
    await api.entities.deleteRelationship(relId);
    load();
  }

  if (loading) return <div className="text-neutral-500 text-sm">Loading...</div>;
  if (!entity) return <div className="text-neutral-500 text-sm">Not found.</div>;

  const meta = entity.meta || {};
  const isOrg = entity.entity_type === "organization";
  const isContact = entity.entity_type === "contact";
  const isAccount = entity.entity_type === "account";
  const isOpportunity = entity.entity_type === "opportunity";

  const typePill =
    isContact ? "border border-violet-800 text-violet-400" :
    isAccount ? "border border-amber-900 text-amber-500" :
    isOpportunity ? "border border-cyan-900 text-cyan-400" :
    "border border-neutral-700 text-neutral-400";

  const typeLabel =
    isContact ? "Contact" :
    isAccount ? "Account" :
    isOpportunity ? "Opportunity" :
    "Organization";

  // Split relationships by direction
  const outgoing = entity.relationships.filter((r) => r.source_entity_id === entity.id);
  const incoming = entity.relationships.filter((r) => r.target_entity_id === entity.id);

  // For contacts: find the org/account they work at
  const worksAt = outgoing.find((r) => r.relationship_type === "works_at");

  // For orgs/accounts: find associated contacts
  const contacts = incoming.filter((r) => r.relationship_type === "works_at");

  // For opportunities: find linked account
  const opportunityFor = outgoing.find((r) => r.relationship_type === "opportunity_for");

  // For accounts: find linked opportunities
  const opportunities = incoming.filter((r) => r.relationship_type === "opportunity_for");

  // Separate entries by source type for the detail view sections
  const interactions = entity.entries.filter((e) =>
    ["email", "transcript", "note"].includes(e.source_type)
  );
  const research = entity.entries.filter((e) =>
    ["research", "rss", "rss_digest"].includes(e.source_type)
  );

  return (
    <div className="max-w-2xl">
      <div className="flex items-center gap-3 mb-6">
        <Link to="/entities" className="text-sm text-neutral-500 hover:text-neutral-300 transition-colors">
          ← Entities
        </Link>
      </div>

      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-2">
          <h1 className="text-2xl font-semibold text-white">
            <InlineEdit value={entity.name} onSave={updateName} className="text-2xl font-semibold text-white" />
          </h1>
          <span className={`text-xs px-1.5 py-0.5 rounded ${typePill}`}>
            {typeLabel}
          </span>
        </div>

        {/* Meta fields */}
        <div className="mt-4 p-4 bg-neutral-900 border border-neutral-800 rounded-lg">
          {isOrg && (
            <>
              <MetaField label="Industry" value={meta.industry} onSave={(v) => updateMeta("industry", v)} />
              <MetaField label="Status" value={meta.engagement_status} onSave={(v) => updateMeta("engagement_status", v)} />
              <MetaField label="Products" value={meta.dynatrace_products?.join(", ")} onSave={(v) => updateMeta("dynatrace_products", v.split(",").map((s) => s.trim()).filter(Boolean))} />
              <MetaField label="Website" value={meta.website} onSave={(v) => updateMeta("website", v)} />
            </>
          )}
          {isAccount && (
            <>
              <MetaField label="Industry" value={meta.industry} onSave={(v) => updateMeta("industry", v)} />
              <MetaField label="Sales Rep" value={meta.sales_rep} onSave={(v) => updateMeta("sales_rep", v)} />
              <MetaField label="Status" value={meta.engagement_status} onSave={(v) => updateMeta("engagement_status", v)} />
              <MetaField label="ARR" value={meta.arr} onSave={(v) => updateMeta("arr", v)} />
              <MetaField label="Products" value={meta.dynatrace_products?.join(", ")} onSave={(v) => updateMeta("dynatrace_products", v.split(",").map((s) => s.trim()).filter(Boolean))} />
              <MetaField label="Website" value={meta.website} onSave={(v) => updateMeta("website", v)} />
            </>
          )}
          {isOpportunity && (
            <>
              <MetaField label="Stage" value={meta.stage} onSave={(v) => updateMeta("stage", v)} />
              <MetaField label="Value" value={meta.value} onSave={(v) => updateMeta("value", v)} />
              <MetaField label="Close Date" value={meta.close_date} onSave={(v) => updateMeta("close_date", v)} />
              <MetaField label="Sales Rep" value={meta.sales_rep} onSave={(v) => updateMeta("sales_rep", v)} />
              {opportunityFor && (
                <div className="flex items-baseline gap-2 py-1">
                  <span className="text-xs text-neutral-500 w-28 shrink-0">Account:</span>
                  <Link to={`/entity/${opportunityFor.target_entity_id}`} className="text-sm text-amber-500 hover:text-amber-400">
                    {opportunityFor.target_entity_name}
                  </Link>
                </div>
              )}
              <MetaField label="Next Steps" value={meta.next_steps} onSave={(v) => updateMeta("next_steps", v)} />
              <MetaField label="Champion" value={meta.champion} onSave={(v) => updateMeta("champion", v)} />
              <MetaField label="Competition" value={meta.competition} onSave={(v) => updateMeta("competition", v)} />
            </>
          )}
          {isContact && (
            <>
              <MetaField label="Title" value={meta.title} onSave={(v) => updateMeta("title", v)} />
              {worksAt && (
                <div className="flex items-baseline gap-2 py-1">
                  <span className="text-xs text-neutral-500 w-28 shrink-0">Account:</span>
                  <Link to={`/entity/${worksAt.target_entity_id}`} className="text-sm text-amber-500 hover:text-amber-400">
                    {worksAt.target_entity_name}
                  </Link>
                </div>
              )}
              <MetaField label="Email" value={meta.email} onSave={(v) => updateMeta("email", v)} />
              <MetaField label="Phone" value={meta.phone} onSave={(v) => updateMeta("phone", v)} />
              <MetaField label="Comm. Style" value={meta.communication_style} onSave={(v) => updateMeta("communication_style", v)} />
            </>
          )}
          <MetaField label="Notes" value={meta.notes} onSave={(v) => updateMeta("notes", v)} />
          {meta.summary && (
            <div className="mt-2 pt-2 border-t border-neutral-800">
              <p className="text-xs text-neutral-400">{meta.summary}</p>
            </div>
          )}
        </div>
      </div>

      {/* Contacts (for orgs) */}
      {isOrg && contacts.length > 0 && (
        <div className="mb-6">
          <p className="text-xs text-neutral-500 mb-3 font-medium uppercase tracking-wide">
            Contacts ({contacts.length})
          </p>
          <div className="space-y-2">
            {contacts.map((rel) => (
              <div key={rel.id} className="flex items-center justify-between p-3 bg-neutral-900 border border-neutral-800 rounded-lg">
                <Link to={`/entity/${rel.source_entity_id}`} className="text-sm text-violet-400 hover:text-violet-300">
                  {rel.source_entity_name}
                </Link>
                <button onClick={() => removeRelationship(rel.id)} className="text-xs text-neutral-600 hover:text-red-400 transition-colors">
                  Remove
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Opportunities (for accounts) */}
      {isAccount && opportunities.length > 0 && (
        <div className="mb-6">
          <p className="text-xs text-neutral-500 mb-3 font-medium uppercase tracking-wide">
            Opportunities ({opportunities.length})
          </p>
          <div className="space-y-2">
            {opportunities.map((rel) => {
              const oppEntity = entity.relationships.find((r) => r.id === rel.id);
              return (
                <div key={rel.id} className="flex items-center justify-between p-3 bg-neutral-900 border border-neutral-800 rounded-lg">
                  <Link to={`/entity/${rel.source_entity_id}`} className="text-sm text-cyan-400 hover:text-cyan-300">
                    {rel.source_entity_name}
                  </Link>
                  <button onClick={() => removeRelationship(rel.id)} className="text-xs text-neutral-600 hover:text-red-400 transition-colors">
                    Remove
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Other relationships */}
      {entity.relationships.filter((r) => r.relationship_type !== "works_at").length > 0 && (
        <div className="mb-6">
          <p className="text-xs text-neutral-500 mb-3 font-medium uppercase tracking-wide">
            Relationships
          </p>
          <div className="flex flex-wrap gap-2">
            {entity.relationships
              .filter((r) => r.relationship_type !== "works_at")
              .map((rel) => {
                const isSource = rel.source_entity_id === entity.id;
                const linkedId = isSource ? rel.target_entity_id : rel.source_entity_id;
                const linkedName = isSource ? rel.target_entity_name : rel.source_entity_name;
                return (
                  <div key={rel.id} className="flex items-center gap-2 px-2 py-1 bg-neutral-900 border border-neutral-800 rounded">
                    <Link to={`/entity/${linkedId}`} className="text-xs text-blue-400 hover:text-blue-300">
                      {linkedName}
                    </Link>
                    <span className="text-xs text-neutral-600">{rel.relationship_type}</span>
                    <button onClick={() => removeRelationship(rel.id)} className="text-xs text-neutral-600 hover:text-red-400">
                      ×
                    </button>
                  </div>
                );
              })}
          </div>
        </div>
      )}

      {/* Interactions */}
      {interactions.length > 0 && (
        <div className="mb-6">
          <p className="text-xs text-neutral-500 mb-3 font-medium uppercase tracking-wide">
            Interactions ({interactions.length})
          </p>
          <div className="space-y-3">
            {interactions.map((entry) => (
              <EntryCard key={entry.id} entry={entry} />
            ))}
          </div>
        </div>
      )}

      {/* Research & Notes */}
      {research.length > 0 && (
        <div className="mb-6">
          <p className="text-xs text-neutral-500 mb-3 font-medium uppercase tracking-wide">
            Related Research & Notes ({research.length})
          </p>
          <div className="space-y-3">
            {research.map((entry) => (
              <EntryCard key={entry.id} entry={entry} />
            ))}
          </div>
        </div>
      )}

      {/* All entries fallback if none in either category */}
      {interactions.length === 0 && research.length === 0 && entity.entries.length > 0 && (
        <div className="mb-6">
          <p className="text-xs text-neutral-500 mb-3 font-medium uppercase tracking-wide">
            Linked Entries ({entity.entries.length})
          </p>
          <div className="space-y-3">
            {entity.entries.map((entry) => (
              <EntryCard key={entry.id} entry={entry} />
            ))}
          </div>
        </div>
      )}

      {entity.entries.length === 0 && (
        <p className="text-sm text-neutral-500">No entries linked to this entity.</p>
      )}
    </div>
  );
}
