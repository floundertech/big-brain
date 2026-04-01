import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";

const TABS = [
  { key: "pipeline", label: "Pipeline" },
  { key: "accounts", label: "By Account" },
  { key: "reps", label: "By Rep" },
  { key: "activity", label: "Weekly Activity" },
];

const STAGES = [
  "Prospecting",
  "Discovery",
  "Proposal",
  "Negotiation",
  "Closed-Won",
  "Closed-Lost",
];

const stagePill = (stage) => {
  const s = (stage || "").toLowerCase();
  if (s.includes("won")) return "bg-green-950 text-green-400 border-green-800";
  if (s.includes("lost")) return "bg-red-950 text-red-400 border-red-800";
  if (s.includes("negotiation")) return "bg-yellow-950 text-yellow-400 border-yellow-800";
  if (s.includes("proposal")) return "bg-blue-950 text-blue-400 border-blue-800";
  if (s.includes("discovery")) return "bg-purple-950 text-purple-400 border-purple-800";
  return "bg-neutral-800 text-neutral-400 border-neutral-700";
};

// ---------------------------------------------------------------------------
// Pipeline tab — all opportunities
// ---------------------------------------------------------------------------

function PipelineTab() {
  const [opps, setOpps] = useState([]);
  const [loading, setLoading] = useState(true);
  const [stageFilter, setStageFilter] = useState("");
  const [repFilter, setRepFilter] = useState("");
  const [showClosed, setShowClosed] = useState(false);
  const [reps, setReps] = useState([]);

  useEffect(() => { api.pipeline.reps().then(setReps); }, []);

  useEffect(() => {
    setLoading(true);
    const params = {};
    if (stageFilter) params.stage = stageFilter;
    if (repFilter) params.sales_rep = repFilter;
    if (showClosed) params.include_closed = true;
    api.pipeline.opportunities(params).then(setOpps).finally(() => setLoading(false));
  }, [stageFilter, repFilter, showClosed]);

  return (
    <div>
      <div className="flex items-center gap-3 mb-4">
        <select
          value={stageFilter}
          onChange={(e) => setStageFilter(e.target.value)}
          className="text-sm bg-neutral-900 border border-neutral-700 rounded px-3 py-1.5 text-neutral-300 focus:outline-none focus:border-neutral-500"
        >
          <option value="">All Stages</option>
          {STAGES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select
          value={repFilter}
          onChange={(e) => setRepFilter(e.target.value)}
          className="text-sm bg-neutral-900 border border-neutral-700 rounded px-3 py-1.5 text-neutral-300 focus:outline-none focus:border-neutral-500"
        >
          <option value="">All Reps</option>
          {reps.map((r) => <option key={r} value={r}>{r}</option>)}
        </select>
        <label className="flex items-center gap-1.5 text-sm text-neutral-400 cursor-pointer">
          <input
            type="checkbox"
            checked={showClosed}
            onChange={(e) => setShowClosed(e.target.checked)}
            className="rounded border-neutral-700"
          />
          Show closed
        </label>
      </div>

      {loading ? (
        <p className="text-neutral-500 text-sm">Loading...</p>
      ) : opps.length === 0 ? (
        <p className="text-neutral-500 text-sm">{showClosed ? "No opportunities found." : "No open opportunities. Create one from the Entities page, or check \"Show closed\"."}</p>
      ) : (
        <div className="space-y-2">
          {opps.map((opp) => (
            <Link
              key={opp.id}
              to={`/entity/${opp.id}`}
              className="block p-4 rounded-lg border border-neutral-800 hover:border-neutral-600 bg-neutral-900 hover:bg-neutral-800 transition-all"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="text-sm font-medium text-white">{opp.name}</span>
                  {opp.stage && (
                    <span className={`text-xs px-1.5 py-0.5 rounded border ${stagePill(opp.stage)}`}>
                      {opp.stage}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-4 text-xs text-neutral-500">
                  {opp.value && <span>{opp.value}</span>}
                  {opp.close_date && <span>Close: {opp.close_date}</span>}
                </div>
              </div>
              <div className="mt-1 flex items-center gap-4 text-xs text-neutral-500">
                {opp.account_name && (
                  <span className="text-amber-600">{opp.account_name}</span>
                )}
                {opp.sales_rep && <span>Rep: {opp.sales_rep}</span>}
                {opp.recent_activity_count > 0 && (
                  <span className="text-blue-400">{opp.recent_activity_count} recent</span>
                )}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Accounts tab
// ---------------------------------------------------------------------------

function AccountsTab() {
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [repFilter, setRepFilter] = useState("");
  const [showInactive, setShowInactive] = useState(false);
  const [reps, setReps] = useState([]);

  useEffect(() => { api.pipeline.reps().then(setReps); }, []);

  useEffect(() => {
    setLoading(true);
    const params = {};
    if (repFilter) params.sales_rep = repFilter;
    if (showInactive) params.active_only = false;
    api.pipeline.accounts(params).then(setAccounts).finally(() => setLoading(false));
  }, [repFilter, showInactive]);

  return (
    <div>
      <div className="flex items-center gap-3 mb-4">
        <select
          value={repFilter}
          onChange={(e) => setRepFilter(e.target.value)}
          className="text-sm bg-neutral-900 border border-neutral-700 rounded px-3 py-1.5 text-neutral-300 focus:outline-none focus:border-neutral-500"
        >
          <option value="">All Reps</option>
          {reps.map((r) => <option key={r} value={r}>{r}</option>)}
        </select>
        <label className="flex items-center gap-1.5 text-sm text-neutral-400 cursor-pointer">
          <input
            type="checkbox"
            checked={showInactive}
            onChange={(e) => setShowInactive(e.target.checked)}
            className="rounded border-neutral-700"
          />
          Show inactive
        </label>
      </div>

      {loading ? (
        <p className="text-neutral-500 text-sm">Loading...</p>
      ) : accounts.length === 0 ? (
        <p className="text-neutral-500 text-sm">{showInactive ? "No accounts found." : "No active accounts. Create one from the Entities page, or check \"Show inactive\"."}</p>
      ) : (
        <div className="space-y-2">
          {accounts.map((acct) => (
            <Link
              key={acct.id}
              to={`/entity/${acct.id}`}
              className="block p-4 rounded-lg border border-neutral-800 hover:border-neutral-600 bg-neutral-900 hover:bg-neutral-800 transition-all"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="text-sm font-medium text-white">{acct.name}</span>
                  {acct.engagement_status && (
                    <span className="text-xs px-1.5 py-0.5 rounded border border-neutral-700 text-neutral-400">
                      {acct.engagement_status}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-4 text-xs text-neutral-500">
                  {acct.industry && <span>{acct.industry}</span>}
                  {acct.sales_rep && <span>Rep: {acct.sales_rep}</span>}
                </div>
              </div>
              <div className="mt-1 flex items-center gap-4 text-xs text-neutral-500">
                <span>{acct.opportunity_count} opp{acct.opportunity_count !== 1 ? "s" : ""}</span>
                <span>{acct.contact_count} contact{acct.contact_count !== 1 ? "s" : ""}</span>
                {acct.recent_activity_count > 0 && (
                  <span className="text-blue-400">{acct.recent_activity_count} recent</span>
                )}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// By Rep tab
// ---------------------------------------------------------------------------

function RepsTab() {
  const [reps, setReps] = useState([]);
  const [selectedRep, setSelectedRep] = useState("");
  const [repData, setRepData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => { api.pipeline.reps().then(setReps); }, []);

  useEffect(() => {
    if (!selectedRep) { setRepData(null); return; }
    setLoading(true);
    api.pipeline.byRep(selectedRep).then(setRepData).finally(() => setLoading(false));
  }, [selectedRep]);

  return (
    <div>
      <div className="mb-4">
        <select
          value={selectedRep}
          onChange={(e) => setSelectedRep(e.target.value)}
          className="text-sm bg-neutral-900 border border-neutral-700 rounded px-3 py-1.5 text-neutral-300 focus:outline-none focus:border-neutral-500"
        >
          <option value="">Select a rep...</option>
          {reps.map((r) => <option key={r} value={r}>{r}</option>)}
        </select>
      </div>

      {!selectedRep && (
        <p className="text-neutral-500 text-sm">Select a sales rep to see their accounts and opportunities.</p>
      )}

      {loading && <p className="text-neutral-500 text-sm">Loading...</p>}

      {repData && !loading && (
        <div>
          {/* Accounts */}
          <div className="mb-6">
            <p className="text-xs text-neutral-500 mb-3 font-medium uppercase tracking-wide">
              Accounts ({repData.accounts.length})
            </p>
            {repData.accounts.length === 0 ? (
              <p className="text-sm text-neutral-500">No accounts assigned.</p>
            ) : (
              <div className="space-y-2">
                {repData.accounts.map((acct) => (
                  <Link
                    key={acct.id}
                    to={`/entity/${acct.id}`}
                    className="block p-3 rounded-lg border border-neutral-800 hover:border-neutral-600 bg-neutral-900 hover:bg-neutral-800 transition-all"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium text-white">{acct.name}</span>
                      <div className="flex items-center gap-3 text-xs text-neutral-500">
                        <span>{acct.opportunity_count} opp{acct.opportunity_count !== 1 ? "s" : ""}</span>
                        <span>{acct.contact_count} contact{acct.contact_count !== 1 ? "s" : ""}</span>
                        {acct.recent_activity_count > 0 && (
                          <span className="text-blue-400">{acct.recent_activity_count} recent</span>
                        )}
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>

          {/* Opportunities */}
          <div>
            <p className="text-xs text-neutral-500 mb-3 font-medium uppercase tracking-wide">
              Opportunities ({repData.opportunities.length})
            </p>
            {repData.opportunities.length === 0 ? (
              <p className="text-sm text-neutral-500">No open opportunities.</p>
            ) : (
              <div className="space-y-2">
                {repData.opportunities.map((opp) => (
                  <Link
                    key={opp.id}
                    to={`/entity/${opp.id}`}
                    className="block p-3 rounded-lg border border-neutral-800 hover:border-neutral-600 bg-neutral-900 hover:bg-neutral-800 transition-all"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <span className="text-sm font-medium text-white">{opp.name}</span>
                        {opp.stage && (
                          <span className={`text-xs px-1.5 py-0.5 rounded border ${stagePill(opp.stage)}`}>
                            {opp.stage}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-3 text-xs text-neutral-500">
                        {opp.value && <span>{opp.value}</span>}
                        {opp.close_date && <span>Close: {opp.close_date}</span>}
                      </div>
                    </div>
                    {opp.account_name && (
                      <p className="mt-1 text-xs text-amber-600">{opp.account_name}</p>
                    )}
                  </Link>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Weekly Activity tab
// ---------------------------------------------------------------------------

function ActivityTab() {
  const [activity, setActivity] = useState([]);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState("7");
  const [repFilter, setRepFilter] = useState("");
  const [reps, setReps] = useState([]);

  useEffect(() => { api.pipeline.reps().then(setReps); }, []);

  useEffect(() => {
    setLoading(true);
    const params = { days };
    if (repFilter) params.sales_rep = repFilter;
    api.pipeline.weeklyActivity(params).then(setActivity).finally(() => setLoading(false));
  }, [days, repFilter]);

  const sourceTypePill = (type) => {
    if (type === "transcript") return "bg-blue-950 text-blue-400";
    if (type === "email") return "bg-green-950 text-green-400";
    if (type === "note") return "bg-neutral-800 text-neutral-400";
    return "bg-neutral-800 text-neutral-400";
  };

  return (
    <div>
      <div className="flex items-center gap-3 mb-4">
        <select
          value={days}
          onChange={(e) => setDays(e.target.value)}
          className="text-sm bg-neutral-900 border border-neutral-700 rounded px-3 py-1.5 text-neutral-300 focus:outline-none focus:border-neutral-500"
        >
          <option value="7">Last 7 days</option>
          <option value="14">Last 14 days</option>
          <option value="30">Last 30 days</option>
        </select>
        <select
          value={repFilter}
          onChange={(e) => setRepFilter(e.target.value)}
          className="text-sm bg-neutral-900 border border-neutral-700 rounded px-3 py-1.5 text-neutral-300 focus:outline-none focus:border-neutral-500"
        >
          <option value="">All Reps</option>
          {reps.map((r) => <option key={r} value={r}>{r}</option>)}
        </select>
      </div>

      {loading ? (
        <p className="text-neutral-500 text-sm">Loading...</p>
      ) : activity.length === 0 ? (
        <p className="text-neutral-500 text-sm">No account/opportunity activity in this period.</p>
      ) : (
        <div className="space-y-2">
          {activity.map((item) => (
            <Link
              key={item.entry_id}
              to={`/entry/${item.entry_id}`}
              className="block p-4 rounded-lg border border-neutral-800 hover:border-neutral-600 bg-neutral-900 hover:bg-neutral-800 transition-all"
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-medium text-white">{item.title}</span>
                    <span className={`text-xs px-1.5 py-0.5 rounded ${sourceTypePill(item.source_type)}`}>
                      {item.source_type}
                    </span>
                  </div>
                  {item.summary && (
                    <p className="text-xs text-neutral-400 line-clamp-2">{item.summary}</p>
                  )}
                </div>
                <span className="text-xs text-neutral-600 shrink-0">
                  {new Date(item.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                </span>
              </div>
              {item.linked_entities.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-2">
                  {item.linked_entities.map((e) => (
                    <span
                      key={e.id}
                      className={`text-xs px-1.5 py-0.5 rounded border ${
                        e.entity_type === "account"
                          ? "border-amber-900 text-amber-500"
                          : "border-cyan-900 text-cyan-400"
                      }`}
                    >
                      {e.name}
                    </span>
                  ))}
                </div>
              )}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Pipeline page
// ---------------------------------------------------------------------------

export default function Pipeline() {
  const [tab, setTab] = useState("pipeline");

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold">Pipeline</h1>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 mb-6 p-1 bg-neutral-900 rounded-lg border border-neutral-800 w-fit">
        {TABS.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`text-sm px-3 py-1.5 rounded transition-colors ${
              tab === key
                ? "bg-neutral-700 text-white"
                : "text-neutral-400 hover:text-neutral-200"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "pipeline" && <PipelineTab />}
      {tab === "accounts" && <AccountsTab />}
      {tab === "reps" && <RepsTab />}
      {tab === "activity" && <ActivityTab />}
    </div>
  );
}
