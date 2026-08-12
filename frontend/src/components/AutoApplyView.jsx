import { useState } from "react";
import BatchQueueModal from "./BatchQueueModal";

export default function AutoApplyView({ digest, onChanged }) {
  const [count, setCount] = useState(6);
  const [open, setOpen] = useState(false);
  const matched = digest?.matched ?? 0;

  return (
    <div className="max-w-xl">
      <h2 className="font-display text-2xl mb-2">Auto apply</h2>
      <p className="text-sm text-paper-dim mb-6">
        Tailors your top matches, then you approve or decline each one before anything is
        filled — and one more explicit confirmation before anything is actually submitted.
        Nothing here ever fires off unreviewed. See CLAUDE.md §0.
      </p>

      <div className="border border-hairline rounded-lg p-6 bg-panel">
        <p className="text-sm text-paper mb-1">
          <span className="text-teal font-medium">{matched}</span> matched posting{matched === 1 ? "" : "s"}{" "}
          currently waiting to be tailored.
        </p>
        <div className="flex items-center gap-3 mt-4">
          <label className="text-sm text-paper-dim font-mono">Apply to top</label>
          <input
            type="number"
            min={1}
            max={20}
            value={count}
            onChange={(e) => setCount(Math.max(1, Number(e.target.value) || 1))}
            className="w-16 bg-panel-raised border border-hairline rounded-md px-2 py-1.5 text-sm text-paper outline-none focus:border-teal"
          />
          <span className="text-sm text-paper-dim font-mono">matches</span>
        </div>
        <button
          onClick={() => setOpen(true)}
          disabled={matched === 0}
          className="mt-5 w-full px-4 py-3 rounded-md bg-teal text-ink text-sm font-medium hover:brightness-110 disabled:opacity-40 transition cursor-pointer"
        >
          Start
        </button>
        {matched === 0 && (
          <p className="text-xs text-paper-dim font-mono mt-2">
            Run Discover + Match in Settings first, or check Browse Jobs.
          </p>
        )}
      </div>

      {open && (
        <BatchQueueModal
          count={count}
          onClose={() => {
            setOpen(false);
            onChanged();
          }}
          onChanged={onChanged}
        />
      )}
    </div>
  );
}
