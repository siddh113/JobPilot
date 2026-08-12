import { useEffect, useState } from "react";
import { api } from "../lib/api";

export default function FiltersPanel() {
  const [filters, setFilters] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.getFilters().then(setFilters).catch(() => {});
  }, []);

  if (!filters) {
    return <p className="text-paper-dim font-mono text-sm">Loading filters…</p>;
  }

  const save = async () => {
    setSaving(true);
    setSaved(false);
    try {
      await api.setFilters(filters);
      setSaved(true);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="border border-hairline rounded-lg p-6 bg-panel max-w-xl">
      <h3 className="font-display text-xl mb-4">Constraints</h3>

      <label className="block mb-4">
        <span className="text-xs font-mono uppercase tracking-wide text-paper-dim">
          Max days since posted
        </span>
        <input
          type="number"
          value={filters.max_days_since_posted ?? ""}
          onChange={(e) =>
            setFilters({
              ...filters,
              max_days_since_posted: e.target.value === "" ? null : parseInt(e.target.value, 10),
            })
          }
          placeholder="No limit"
          className="mt-1 w-full bg-panel-raised border border-hairline rounded-md px-3 py-2 text-paper font-mono text-sm"
        />
      </label>

      <label className="flex items-center gap-2 mb-4 cursor-pointer">
        <input
          type="checkbox"
          checked={filters.remote_only}
          onChange={(e) => setFilters({ ...filters, remote_only: e.target.checked })}
          className="accent-teal"
        />
        <span className="text-sm">Remote only</span>
      </label>

      <label className="block mb-4">
        <span className="text-xs font-mono uppercase tracking-wide text-paper-dim">
          Exclude keywords (comma-separated)
        </span>
        <input
          type="text"
          value={filters.exclude_keywords.join(", ")}
          onChange={(e) =>
            setFilters({
              ...filters,
              exclude_keywords: e.target.value.split(",").map((s) => s.trim()).filter(Boolean),
            })
          }
          placeholder="Staff, Director, Clearance Required"
          className="mt-1 w-full bg-panel-raised border border-hairline rounded-md px-3 py-2 text-paper font-mono text-sm"
        />
      </label>

      <label className="block mb-6">
        <span className="text-xs font-mono uppercase tracking-wide text-paper-dim">
          Require at least one keyword (comma-separated)
        </span>
        <input
          type="text"
          value={filters.require_keywords.join(", ")}
          onChange={(e) =>
            setFilters({
              ...filters,
              require_keywords: e.target.value.split(",").map((s) => s.trim()).filter(Boolean),
            })
          }
          placeholder="Python, LLM"
          className="mt-1 w-full bg-panel-raised border border-hairline rounded-md px-3 py-2 text-paper font-mono text-sm"
        />
      </label>

      <button
        onClick={save}
        disabled={saving}
        className="px-4 py-2 rounded-md bg-teal text-ink text-sm font-medium hover:brightness-110 disabled:opacity-50 transition cursor-pointer"
      >
        {saving ? "Saving…" : saved ? "Saved ✓" : "Save filters"}
      </button>
      <p className="text-xs text-paper-dim mt-3">
        Location/relocation rules live in config.yaml (locations_ok, locations_excluded).
      </p>
    </div>
  );
}
