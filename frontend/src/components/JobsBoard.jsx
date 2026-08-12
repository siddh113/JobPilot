import { useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import TailoringModal from "./TailoringModal";

// Tailwind can't resolve interpolated class names like `bg-${accent}-dim`
// at build time — every literal class used per accent has to appear
// somewhere in source. This lookup keeps them literal.
const ACCENT_CLASSES = [
  { border: "border-teal", badgeBg: "bg-teal-dim", badgeText: "text-teal" },
  { border: "border-amber", badgeBg: "bg-amber-dim", badgeText: "text-amber" },
  { border: "border-rose", badgeBg: "bg-rose-dim", badgeText: "text-rose" },
];

function accentFor(id) {
  return ACCENT_CLASSES[id % ACCENT_CLASSES.length];
}

function relativeTime(iso) {
  if (!iso) return null;
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return null;
  const diffMs = Date.now() - then;
  const hours = Math.floor(diffMs / 3_600_000);
  if (hours < 1) return "just now";
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.floor(hours / 24);
  if (days === 1) return "a day ago";
  if (days < 30) return `${days} days ago`;
  const months = Math.floor(days / 30);
  return `${months} month${months === 1 ? "" : "s"} ago`;
}

function ringColor(score) {
  if (score === null || score === undefined) return "var(--color-paper-dim)";
  if (score >= 85) return "var(--color-teal)";
  if (score >= 70) return "var(--color-amber)";
  return "var(--color-rose)";
}

function MatchRing({ score }) {
  const size = 44;
  const stroke = 4;
  const r = (size - stroke) / 2;
  const circumference = 2 * Math.PI * r;
  const pct = score === null || score === undefined ? 0 : Math.max(0, Math.min(100, score));
  const offset = circumference * (1 - pct / 100);
  const color = ringColor(score);

  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--color-hairline)" strokeWidth={stroke} />
        {score !== null && score !== undefined && (
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke={color}
            strokeWidth={stroke}
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
          />
        )}
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center leading-none">
        <span className="text-[11px] font-mono font-medium" style={{ color }}>
          {score === null || score === undefined ? "—" : Math.round(score)}
        </span>
      </div>
    </div>
  );
}

function CompanyBadge({ name, accent }) {
  const initial = name?.[0]?.toUpperCase() || "?";
  return (
    <div
      className={`w-7 h-7 rounded-md flex items-center justify-center text-xs font-mono font-medium shrink-0
        ${accent.badgeBg} ${accent.badgeText}`}
    >
      {initial}
    </div>
  );
}

function SkillTags({ tags }) {
  if (!tags || tags.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1.5 mt-3">
      {tags.map((t) => (
        <span
          key={t}
          className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-panel-raised text-paper-dim border border-hairline"
        >
          {t}
        </span>
      ))}
    </div>
  );
}

function JobCard({ posting, accent, onDecided, onApply }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const skip = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.skipPosting(posting.id);
      onDecided(posting.id);
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  };

  const when = relativeTime(posting.posted_at || posting.first_seen_at);

  return (
    <div className={`border-l-2 ${accent.border} border-t border-r border-b border-hairline rounded-lg p-5 bg-panel flex flex-col`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <CompanyBadge name={posting.company_name} accent={accent} />
          <div className="min-w-0">
            <p className="text-sm text-paper truncate">{posting.company_name}</p>
            <p className="text-xs text-paper-dim">
              {posting.location || "—"}
              {posting.remote && posting.location?.toLowerCase() !== "remote" && " · Remote"}
            </p>
          </div>
        </div>
        <MatchRing score={posting.final_score} />
      </div>

      <div className="flex-1 mt-3">
        <h3 className="font-display text-lg leading-snug">{posting.title}</h3>
        {when && <p className="text-xs text-paper-dim font-mono mt-1">{when}</p>}
        <SkillTags tags={posting.skill_tags} />
      </div>

      {error && <p className="text-rose text-xs font-mono mt-3">{error}</p>}

      <div className="flex items-center gap-2 mt-4 pt-4 border-t border-hairline">
        <a
          href={posting.url}
          target="_blank"
          rel="noreferrer"
          className="text-xs font-mono text-paper-dim hover:text-teal underline underline-offset-2 mr-auto"
        >
          Details →
        </a>
        <button
          onClick={skip}
          disabled={busy}
          className="px-3 py-2 rounded-md border border-hairline text-paper-dim text-sm hover:text-rose hover:border-rose disabled:opacity-40 transition cursor-pointer"
        >
          Pass
        </button>
        <button
          onClick={() => onApply(posting)}
          disabled={busy}
          className="px-4 py-2 rounded-md bg-teal text-ink text-sm font-medium hover:brightness-110 disabled:opacity-60 transition cursor-pointer"
        >
          Apply
        </button>
      </div>
    </div>
  );
}

function FilterPill({ active, children, ...props }) {
  return (
    <select
      {...props}
      className={`appearance-none rounded-full px-3 py-1.5 text-xs font-mono outline-none cursor-pointer border transition-colors
        ${active ? "bg-teal-dim/40 border-teal text-teal" : "bg-panel-raised border-hairline text-paper-dim"}`}
    >
      {children}
    </select>
  );
}

function FilterBar({ postings, filters, setFilters, onRefresh, refreshing }) {
  const companies = useMemo(
    () => [...new Set(postings.map((p) => p.company_name))].sort(),
    [postings]
  );

  const activeCount =
    (filters.search ? 1 : 0) +
    (filters.exclude ? 1 : 0) +
    (filters.workplace !== "all" ? 1 : 0) +
    (filters.company !== "all" ? 1 : 0);

  const clear = () =>
    setFilters((f) => ({ search: "", exclude: "", workplace: "all", company: "all", sort: f.sort }));

  return (
    <div className="border border-hairline rounded-lg p-3 mb-4">
      <div className="flex flex-wrap items-center gap-2">
        <select
          value={filters.searchScope}
          onChange={(e) => setFilters((f) => ({ ...f, searchScope: e.target.value }))}
          className="bg-panel-raised border border-hairline rounded-full px-3 py-2 text-xs font-mono text-paper-dim outline-none focus:border-teal cursor-pointer shrink-0"
        >
          <option value="title">Title</option>
          <option value="title_description">Title + description</option>
        </select>
        <input
          value={filters.search}
          onChange={(e) => setFilters((f) => ({ ...f, search: e.target.value }))}
          placeholder="Search by title or keyword…"
          className="flex-1 min-w-[160px] bg-panel-raised border border-hairline rounded-full px-4 py-2 text-sm text-paper placeholder:text-paper-dim outline-none focus:border-teal"
        />
        <button
          onClick={onRefresh}
          disabled={refreshing}
          className="shrink-0 px-3 py-2 text-xs font-mono rounded-full border border-hairline text-paper-dim
                     hover:border-teal hover:text-teal disabled:opacity-40 transition-colors cursor-pointer"
        >
          {refreshing ? "Refreshing…" : "↻ Refresh jobs"}
        </button>
      </div>

      <div className="flex items-center gap-2 mt-2">
        <span className="text-xs font-mono text-paper-dim shrink-0">Exclude</span>
        <input
          value={filters.exclude}
          onChange={(e) => setFilters((f) => ({ ...f, exclude: e.target.value }))}
          placeholder="Hide jobs mentioning…"
          className="flex-1 bg-transparent border-b border-hairline px-1 py-1 text-sm text-paper placeholder:text-paper-dim outline-none focus:border-teal"
        />
      </div>

      <div className="flex flex-wrap items-center gap-2 mt-3">
        <FilterPill
          active={filters.workplace !== "all"}
          value={filters.workplace}
          onChange={(e) => setFilters((f) => ({ ...f, workplace: e.target.value }))}
        >
          <option value="all">Workplace</option>
          <option value="remote">Remote</option>
          <option value="onsite">On-site</option>
        </FilterPill>

        <FilterPill
          active={filters.company !== "all"}
          value={filters.company}
          onChange={(e) => setFilters((f) => ({ ...f, company: e.target.value }))}
        >
          <option value="all">Companies</option>
          {companies.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </FilterPill>

        <FilterPill value={filters.sort} onChange={(e) => setFilters((f) => ({ ...f, sort: e.target.value }))}>
          <option value="match">Sort: best match</option>
          <option value="recent">Sort: most recent</option>
        </FilterPill>

        {activeCount > 0 && (
          <button
            onClick={clear}
            className="text-xs font-mono text-paper-dim hover:text-rose transition cursor-pointer px-2"
          >
            Clear ({activeCount})
          </button>
        )}
      </div>
    </div>
  );
}

export default function JobsBoard({ onAppliedTo }) {
  const [postings, setPostings] = useState(null);
  const [error, setError] = useState(null);
  const [toast, setToast] = useState(null);
  const [filters, setFilters] = useState({
    search: "",
    exclude: "",
    searchScope: "title",
    workplace: "all",
    company: "all",
    sort: "match",
  });
  const [applyingTo, setApplyingTo] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loadingMore, setLoadingMore] = useState(false);

  const PAGE_SIZE = 60;

  // actionable=true does the "not filtered out, not skipped, not already
  // applied to" filtering server-side now — with thousands of historical
  // postings sitting in the DB, fetching everything and filtering it in
  // the browser meant paying for (and rendering) rows nobody would ever
  // see. A page here is a page of genuinely actionable postings.
  const load = async (reset) => {
    try {
      const startOffset = reset ? 0 : offset;
      const page = await api.getPostings({ actionable: true, limit: PAGE_SIZE, offset: startOffset });
      setTotal(page.total);
      setPostings((prev) => (reset ? page.items : [...(prev || []), ...page.items]));
      setOffset(startOffset + page.items.length);
      setError(null);
    } catch (err) {
      setError(err.message);
    }
  };

  useEffect(() => {
    load(true);
  }, []);

  const loadMore = async () => {
    setLoadingMore(true);
    await load(false);
    setLoadingMore(false);
  };

  const runRefresh = async () => {
    setRefreshing(true);
    try {
      await api.runDiscoverSearch();
      await api.runFilterPostings();
      await api.runMatch();
      await load(true);
      onAppliedTo?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setRefreshing(false);
    }
  };

  const handleDecided = (postingId) => {
    setPostings((prev) => prev.filter((p) => p.id !== postingId));
  };

  const handleApplyDone = (posting) => {
    setApplyingTo(null);
    setPostings((prev) => prev.filter((p) => p.id !== posting.id));
    setToast(`Sent to Applications: ${posting.title}`);
    onAppliedTo?.();
    setTimeout(() => setToast(null), 4000);
  };

  const filtered = useMemo(() => {
    if (!postings) return [];
    let list = postings;
    if (filters.search.trim()) {
      const q = filters.search.trim().toLowerCase();
      list = list.filter((p) => {
        if (p.title.toLowerCase().includes(q) || p.company_name.toLowerCase().includes(q)) return true;
        if (filters.searchScope === "title_description") {
          return p.description_snippet?.toLowerCase().includes(q);
        }
        return false;
      });
    }
    if (filters.exclude.trim()) {
      const terms = filters.exclude
        .split(",")
        .map((t) => t.trim().toLowerCase())
        .filter(Boolean);
      list = list.filter((p) => {
        const haystack = `${p.title} ${p.description_snippet || ""}`.toLowerCase();
        return !terms.some((t) => haystack.includes(t));
      });
    }
    if (filters.workplace === "remote") list = list.filter((p) => p.remote);
    if (filters.workplace === "onsite") list = list.filter((p) => !p.remote);
    if (filters.company !== "all") list = list.filter((p) => p.company_name === filters.company);

    list = [...list].sort((a, b) => {
      if (filters.sort === "recent") {
        return new Date(b.posted_at || b.first_seen_at) - new Date(a.posted_at || a.first_seen_at);
      }
      return (b.final_score ?? -1) - (a.final_score ?? -1);
    });
    return list;
  }, [postings, filters]);

  if (error) {
    return <p className="text-rose text-sm font-mono">{error}</p>;
  }

  if (postings === null) {
    return <p className="text-paper-dim font-mono text-sm">Loading jobs…</p>;
  }

  return (
    <div>
      {toast && (
        <div className="mb-4 px-4 py-3 rounded-md border border-teal bg-teal-dim/20 text-teal text-sm font-mono">
          {toast}
        </div>
      )}

      <FilterBar
        postings={postings}
        filters={filters}
        setFilters={setFilters}
        onRefresh={runRefresh}
        refreshing={refreshing}
      />

      {postings.length === 0 ? (
        <div className="border border-hairline rounded-lg p-8 text-center">
          <p className="text-paper-dim font-mono text-sm">
            No jobs waiting on a decision yet.{" "}
            <button onClick={runRefresh} disabled={refreshing} className="text-teal underline underline-offset-2 cursor-pointer disabled:opacity-40">
              {refreshing ? "Refreshing…" : "Refresh jobs"}
            </button>{" "}
            to pull more in.
          </p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="border border-hairline rounded-lg p-8 text-center">
          <p className="text-paper-dim font-mono text-sm">No jobs match these filters.</p>
        </div>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {filtered.map((p, i) => (
              <JobCard
                key={p.id}
                posting={p}
                accent={accentFor(i)}
                onDecided={handleDecided}
                onApply={setApplyingTo}
              />
            ))}
          </div>

          {postings.length < total && (
            <div className="flex flex-col items-center gap-2 mt-6">
              <p className="text-xs text-paper-dim font-mono">
                Showing {postings.length} of {total}
              </p>
              <button
                onClick={loadMore}
                disabled={loadingMore}
                className="px-4 py-2 rounded-md border border-hairline text-paper-dim text-sm
                           hover:border-teal hover:text-teal disabled:opacity-40 transition cursor-pointer"
              >
                {loadingMore ? "Loading…" : "Load more"}
              </button>
            </div>
          )}
        </>
      )}

      {applyingTo && (
        <TailoringModal
          posting={applyingTo}
          onClose={() => setApplyingTo(null)}
          onDone={handleApplyDone}
        />
      )}
    </div>
  );
}
