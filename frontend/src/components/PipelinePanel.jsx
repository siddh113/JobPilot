import { useState } from "react";
import { api } from "../lib/api";

// Manual pipeline controls — discovery/filter/match run automatically in
// production via cron (see CLAUDE.md §3), so day-to-day use of Browse Jobs
// shouldn't need these. Kept here, tucked into Settings, for on-demand
// runs and debugging rather than as the primary way to pull in jobs.
export default function PipelinePanel({ onRefresh }) {
  const [running, setRunning] = useState(null);
  const [lastResult, setLastResult] = useState(null);

  const run = async (label, fn) => {
    setRunning(label);
    setLastResult(null);
    try {
      const result = await fn();
      setLastResult({ label, ok: true, detail: JSON.stringify(result) });
      onRefresh();
    } catch (err) {
      setLastResult({ label, ok: false, detail: err.message });
    } finally {
      setRunning(null);
    }
  };

  const actions = [
    { label: "Discover (search)", fn: api.runDiscoverSearch },
    { label: "Discover (companies)", fn: api.runDiscoverCompanies },
    { label: "Filter postings", fn: api.runFilterPostings },
    { label: "Match", fn: api.runMatch },
    { label: "Tailor matched", fn: api.runTailor },
  ];

  return (
    <div className="border border-hairline rounded-lg p-6 bg-panel max-w-xl">
      <h3 className="font-display text-xl mb-1">Pipeline (advanced)</h3>
      <p className="text-xs text-paper-dim font-mono mb-4">
        Manual/debug runs. Browse Jobs' Refresh button already runs discover → filter → match.
      </p>
      <div className="flex flex-wrap gap-2">
        {actions.map((a) => (
          <button
            key={a.label}
            onClick={() => run(a.label, a.fn)}
            disabled={running !== null}
            className="px-3 py-2 text-sm font-mono rounded-md border border-hairline
                       bg-panel-raised text-paper hover:border-teal hover:text-teal
                       disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer"
          >
            {running === a.label ? "Running…" : a.label}
          </button>
        ))}
      </div>
      {lastResult && (
        <p className={`mt-3 text-xs font-mono ${lastResult.ok ? "text-teal" : "text-rose"}`}>
          {lastResult.label}: {lastResult.detail}
        </p>
      )}
    </div>
  );
}
