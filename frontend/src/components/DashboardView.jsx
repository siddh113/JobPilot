// Literal classes only — Tailwind can't resolve `text-${accent}` at build time.
const ACCENT_TEXT = { teal: "text-teal", amber: "text-amber", paper: "text-paper" };

function StatTile({ label, value, accent = "paper" }) {
  return (
    <div className="border border-hairline rounded-lg p-5 bg-panel">
      <p className="text-xs font-mono uppercase tracking-wide text-paper-dim">{label}</p>
      <p className={`font-display text-3xl mt-1 ${ACCENT_TEXT[accent]}`}>{value}</p>
    </div>
  );
}

export default function DashboardView({ digest }) {
  if (!digest) {
    return <p className="text-paper-dim font-mono text-sm">Loading…</p>;
  }

  return (
    <div>
      <h2 className="font-display text-2xl mb-4">Today</h2>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile label="New postings" value={digest.new} />
        <StatTile label="Matched" value={digest.matched} accent="teal" />
        <StatTile label="Filtered out" value={digest.filtered_out} />
        <StatTile label="Draft applications" value={digest.draft_applications} accent="amber" />
        <StatTile label="Approved" value={digest.approved_applications} accent="amber" />
        <StatTile label="Filled" value={digest.filled_applications} accent="amber" />
        <StatTile label="Submitted" value={digest.submitted_applications} accent="teal" />
      </div>
    </div>
  );
}
