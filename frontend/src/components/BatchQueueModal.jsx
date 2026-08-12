import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { LoadingScreen, ResumeDiffView, KeywordCoverage } from "./ResumeReview";
import { ChatEditor } from "./TailoringModal";

// One batch-level confirmation before filling the approved set, one more
// before submitting the filled set — see CLAUDE.md §0.2. Neither step ever
// fires per-item without a person having explicitly clicked through the
// modal for the whole batch first.
function ConfirmModal({ title, body, confirmLabel, onCancel, onConfirm, busy }) {
  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center p-4 z-[60]">
      <div className="bg-panel border border-amber rounded-lg p-6 max-w-md w-full">
        <h3 className="font-display text-xl text-amber mb-2">{title}</h3>
        <p className="text-sm text-paper mt-2">{body}</p>
        <div className="flex gap-3 mt-6">
          <button
            onClick={onCancel}
            disabled={busy}
            className="flex-1 px-4 py-2 rounded-md border border-hairline text-paper-dim hover:text-paper transition-colors cursor-pointer"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={busy}
            className="flex-1 px-4 py-2 rounded-md bg-amber text-ink font-medium hover:brightness-110 transition disabled:opacity-50 cursor-pointer"
          >
            {busy ? "Working…" : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function BatchQueueModal({ count, onClose, onChanged }) {
  const [phase, setPhase] = useState("preparing");
  // preparing | review | confirmFill | filling | fillResults | confirmSubmit | submitting | done | error
  const [appIds, setAppIds] = useState([]);
  const [index, setIndex] = useState(0);
  const [detailCache, setDetailCache] = useState({}); // id -> tailoring detail
  const [decisions, setDecisions] = useState({}); // id -> "approved" | "rejected"
  const [fillResults, setFillResults] = useState({}); // id -> status
  const [submitResults, setSubmitResults] = useState({}); // id -> status
  const [error, setError] = useState(null);
  const [confirmBusy, setConfirmBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { application_ids } = await api.prepareBatch(count);
        if (cancelled) return;
        if (application_ids.length === 0) {
          setError("No matched postings waiting to be tailored right now.");
          setPhase("error");
          return;
        }
        setAppIds(application_ids);
        setPhase("review");
      } catch (err) {
        if (cancelled) return;
        setError(err.message);
        setPhase("error");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [count]);

  const currentId = appIds[index];

  useEffect(() => {
    if (phase !== "review" || !currentId || detailCache[currentId]) return;
    let cancelled = false;
    (async () => {
      try {
        const detail = await api.getTailoring(currentId);
        if (cancelled) return;
        setDetailCache((c) => ({ ...c, [currentId]: detail }));
      } catch (err) {
        if (cancelled) return;
        setDetailCache((c) => ({ ...c, [currentId]: { error: err.message } }));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [phase, currentId, detailCache]);

  const decide = async (decision) => {
    try {
      await api.decideApplication(currentId, decision);
      setDecisions((d) => ({ ...d, [currentId]: decision === "approve" ? "approved" : "rejected" }));
      if (index < appIds.length - 1) setIndex((i) => i + 1);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleRevised = (result) => {
    setDetailCache((c) => ({
      ...c,
      [currentId]: {
        ...c[currentId],
        resume: result.resume,
        resume_diff: result.resume_diff,
        keyword_coverage: result.keyword_coverage,
      },
    }));
  };

  const approvedIds = appIds.filter((id) => decisions[id] === "approved");
  const decidedCount = Object.keys(decisions).length;

  const runFill = async () => {
    setConfirmBusy(true);
    setPhase("filling");
    try {
      const { results } = await api.fillBatch(approvedIds);
      setFillResults(results);
      setPhase("fillResults");
    } catch (err) {
      setError(err.message);
      setPhase("error");
    } finally {
      setConfirmBusy(false);
    }
  };

  const filledIds = Object.entries(fillResults)
    .filter(([, status]) => status === "filled")
    .map(([id]) => Number(id));

  const runSubmit = async () => {
    setConfirmBusy(true);
    setPhase("submitting");
    try {
      const { results } = await api.submitBatch(filledIds, true);
      setSubmitResults(results);
      setPhase("done");
      onChanged?.();
    } catch (err) {
      setError(err.message);
      setPhase("error");
    } finally {
      setConfirmBusy(false);
    }
  };

  const detail = detailCache[currentId];

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center p-4 z-50">
      <div className="bg-panel border border-hairline rounded-lg w-full max-w-4xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-hairline">
          <div>
            <h2 className="font-display text-lg">Quick apply</h2>
            {phase === "review" && (
              <p className="text-xs text-paper-dim font-mono">
                {index + 1} of {appIds.length} · {decidedCount} reviewed
              </p>
            )}
          </div>
          <div className="flex items-center gap-3">
            {phase === "review" && (
              <>
                <button
                  onClick={() => setIndex((i) => Math.max(0, i - 1))}
                  disabled={index === 0}
                  className="text-xs font-mono text-paper-dim hover:text-paper disabled:opacity-30 cursor-pointer"
                >
                  ← Prev
                </button>
                <button
                  onClick={() => setIndex((i) => Math.min(appIds.length - 1, i + 1))}
                  disabled={index === appIds.length - 1}
                  className="text-xs font-mono text-paper-dim hover:text-paper disabled:opacity-30 cursor-pointer"
                >
                  Next →
                </button>
              </>
            )}
            <button onClick={onClose} className="text-paper-dim hover:text-paper text-sm cursor-pointer">
              ✕
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          {phase === "preparing" && <LoadingScreen title={`Tailoring ${count} applications…`} />}

          {phase === "error" && (
            <div className="text-center py-16">
              <p className="text-rose text-sm font-mono">{error}</p>
            </div>
          )}

          {phase === "review" && !detail && <p className="text-paper-dim font-mono text-sm">Loading…</p>}

          {phase === "review" && detail && detail.error && (
            <p className="text-rose text-sm font-mono">{detail.error}</p>
          )}

          {phase === "review" && detail && !detail.error && (
            <>
              <div className="mb-4">
                <h3 className="font-display text-lg">{detail.posting_title}</h3>
                <p className="text-sm text-paper-dim">{detail.company_name}</p>
                {decisions[currentId] && (
                  <span
                    className={`text-xs font-mono uppercase ${
                      decisions[currentId] === "approved" ? "text-teal" : "text-rose"
                    }`}
                  >
                    {decisions[currentId]}
                  </span>
                )}
              </div>
              <div className="grid md:grid-cols-[1fr_320px] gap-6">
                <ResumeDiffView resumeDiff={detail.resume_diff} />
                <div className="flex flex-col gap-4">
                  <KeywordCoverage coverage={detail.keyword_coverage} />
                  <div className="flex-1 min-h-[200px]">
                    <ChatEditor applicationId={currentId} onRevised={handleRevised} />
                  </div>
                </div>
              </div>
            </>
          )}

          {(phase === "filling" || phase === "submitting") && (
            <LoadingScreen
              title={phase === "filling" ? "Filling the approved batch…" : "Submitting the filled batch…"}
            />
          )}

          {phase === "fillResults" && (
            <div className="py-4">
              <h3 className="font-display text-lg mb-1">Fill results</h3>
              <p className="text-xs text-paper-dim font-mono mb-3">
                Check the receipt screenshots in the Applications tab before submitting.
              </p>
              <ul className="space-y-1 text-sm font-mono">
                {Object.entries(fillResults).map(([id, status]) => (
                  <li key={id} className={status === "filled" ? "text-teal" : "text-rose"}>
                    Application {id}: {status}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {phase === "done" && (
            <div className="py-4">
              <h3 className="font-display text-lg mb-3">Batch complete</h3>
              <ul className="space-y-1 text-sm font-mono">
                {Object.entries(submitResults).map(([id, status]) => (
                  <li key={id} className={status === "submitted" ? "text-teal" : "text-rose"}>
                    Application {id}: {status}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {phase === "review" && (
          <div className="flex items-center justify-between gap-3 px-6 py-4 border-t border-hairline">
            <div className="flex gap-2">
              <button
                onClick={() => decide("reject")}
                className="px-4 py-2 rounded-md border border-hairline text-paper-dim text-sm hover:text-rose hover:border-rose transition cursor-pointer"
              >
                Decline
              </button>
              <button
                onClick={() => decide("approve")}
                className="px-4 py-2 rounded-md bg-teal text-ink text-sm font-medium hover:brightness-110 transition cursor-pointer"
              >
                Approve
              </button>
            </div>
            <button
              onClick={() => setPhase("confirmFill")}
              disabled={approvedIds.length === 0}
              className="px-4 py-2 rounded-md bg-amber text-ink text-sm font-medium hover:brightness-110 disabled:opacity-40 transition cursor-pointer"
            >
              Fill approved batch ({approvedIds.length})
            </button>
          </div>
        )}

        {phase === "fillResults" && (
          <div className="flex justify-end gap-3 px-6 py-4 border-t border-hairline">
            <button
              onClick={onClose}
              className="px-4 py-2 rounded-md border border-hairline text-paper-dim hover:text-paper transition cursor-pointer"
            >
              Stop here
            </button>
            <button
              onClick={() => setPhase("confirmSubmit")}
              disabled={filledIds.length === 0}
              className="px-4 py-2 rounded-md bg-amber text-ink text-sm font-medium hover:brightness-110 disabled:opacity-40 transition cursor-pointer"
            >
              Submit filled batch ({filledIds.length})
            </button>
          </div>
        )}

        {phase === "done" && (
          <div className="flex justify-end px-6 py-4 border-t border-hairline">
            <button
              onClick={onClose}
              className="px-4 py-2 rounded-md bg-teal text-ink text-sm font-medium hover:brightness-110 transition cursor-pointer"
            >
              Close
            </button>
          </div>
        )}
      </div>

      {phase === "confirmFill" && (
        <ConfirmModal
          title="Fill this approved batch?"
          body={`This fills the ATS form for ${approvedIds.length} approved application${approvedIds.length === 1 ? "" : "s"}, headless, with no submission yet. Review each fill result before the next step.`}
          confirmLabel="Fill batch"
          busy={confirmBusy}
          onCancel={() => setPhase("review")}
          onConfirm={runFill}
        />
      )}

      {phase === "confirmSubmit" && (
        <ConfirmModal
          title="Submit this filled batch?"
          body={`This submits ${filledIds.length} filled application${filledIds.length === 1 ? "" : "s"} for real. This is final and cannot be undone — check the fill receipts in the Applications tab first if you haven't already.`}
          confirmLabel="Yes, submit batch"
          busy={confirmBusy}
          onCancel={() => setPhase("fillResults")}
          onConfirm={runSubmit}
        />
      )}
    </div>
  );
}
