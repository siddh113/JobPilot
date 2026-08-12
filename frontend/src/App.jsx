import { useEffect, useState, useCallback } from "react";
import { api } from "./lib/api";
import JobsBoard from "./components/JobsBoard";
import ReviewPanel from "./components/ReviewPanel";
import FiltersPanel from "./components/FiltersPanel";
import ResumePanel from "./components/ResumePanel";
import PipelinePanel from "./components/PipelinePanel";
import DashboardView from "./components/DashboardView";
import AutoApplyView from "./components/AutoApplyView";

function NavItem({ active, onClick, children, count }) {
  return (
    <button
      onClick={onClick}
      className={`relative px-3.5 py-1.5 text-sm rounded-full transition-colors cursor-pointer flex items-center gap-1.5
        ${active ? "bg-panel-raised text-teal" : "text-paper-dim hover:text-paper"}`}
    >
      {children}
      {count > 0 && (
        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-amber-dim text-amber">
          {count}
        </span>
      )}
    </button>
  );
}

function App() {
  const [tab, setTab] = useState("jobs"); // "dashboard" | "jobs" | "applications" | "autoApply" | "settings"
  const [digest, setDigest] = useState(null);
  const [applications, setApplications] = useState([]);
  const [loadError, setLoadError] = useState(null);
  const [refreshTick, setRefreshTick] = useState(0);

  const bumpRefresh = () => setRefreshTick((t) => t + 1);

  const refreshDigest = useCallback(async () => {
    try {
      const d = await api.getDigest();
      setDigest(d);
      setLoadError(null);
    } catch (err) {
      setLoadError(err.message);
    }
  }, []);

  useEffect(() => {
    refreshDigest();
  }, [refreshDigest, refreshTick]);

  useEffect(() => {
    if (tab !== "applications") return;
    (async () => {
      try {
        const apps = await api.getApplications();
        setApplications(apps.filter((a) => a.status !== "rejected"));
        setLoadError(null);
      } catch (err) {
        setLoadError(err.message);
      }
    })();
  }, [tab, refreshTick]);

  const pendingApplicationsCount = digest
    ? digest.draft_applications + digest.approved_applications + digest.filled_applications
    : 0;

  return (
    <div className="min-h-screen">
      <header className="border-b border-hairline px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-6">
          <h1 className="font-display text-2xl tracking-tight">JobPilot</h1>
          <nav className="flex items-center gap-1">
            <NavItem active={tab === "dashboard"} onClick={() => setTab("dashboard")}>
              Dashboard
            </NavItem>
            <NavItem active={tab === "jobs"} onClick={() => setTab("jobs")} count={digest?.matched + digest?.new}>
              Browse jobs
            </NavItem>
            <NavItem
              active={tab === "applications"}
              onClick={() => setTab("applications")}
              count={pendingApplicationsCount}
            >
              Applications
            </NavItem>
            <NavItem active={tab === "autoApply"} onClick={() => setTab("autoApply")}>
              Auto apply
            </NavItem>
          </nav>
        </div>
        <NavItem active={tab === "settings"} onClick={() => setTab("settings")}>
          Settings
        </NavItem>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-8">
        {loadError && <p className="mb-4 text-rose text-sm font-mono">{loadError}</p>}

        {tab === "dashboard" && <DashboardView digest={digest} />}

        {tab === "jobs" && <JobsBoard onAppliedTo={bumpRefresh} />}

        {tab === "applications" && (
          <ReviewPanel applications={applications} onChanged={bumpRefresh} />
        )}

        {tab === "autoApply" && <AutoApplyView digest={digest} onChanged={bumpRefresh} />}

        {tab === "settings" && (
          <div className="grid gap-6">
            <div className="grid gap-6 md:grid-cols-2">
              <ResumePanel />
              <FiltersPanel />
            </div>
            <PipelinePanel onRefresh={bumpRefresh} />
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
