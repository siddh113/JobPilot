import { useState } from "react";
import { api } from "../lib/api";

function SubmitConfirmModal({ application, onCancel, onConfirmed }) {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const handleConfirm = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const result = await api.submitApplication(application.id, true);
      onConfirmed(result);
    } catch (err) {
      setError(err.message);
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center p-4 z-50">
      <div className="bg-panel border border-amber rounded-lg p-6 max-w-md w-full">
        <h3 className="font-display text-xl text-amber mb-2">Submit this application?</h3>
        <p className="text-sm text-paper-dim mb-1">
          {application.posting_title} · {application.company_name}
        </p>
        <p className="text-sm text-paper mt-4">
          This is final. The form has been filled — a screenshot of what was
          filled is at <span className="font-mono text-xs">{application.receipt_path}</span>.
          Review it before confirming; this action cannot be undone.
        </p>
        {error && <p className="text-rose text-sm mt-3 font-mono">{error}</p>}
        <div className="flex gap-3 mt-6">
          <button
            onClick={onCancel}
            disabled={submitting}
            className="flex-1 px-4 py-2 rounded-md border border-hairline text-paper-dim hover:text-paper transition-colors cursor-pointer"
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            disabled={submitting}
            className="flex-1 px-4 py-2 rounded-md bg-amber text-ink font-medium hover:brightness-110 transition disabled:opacity-50 cursor-pointer"
          >
            {submitting ? "Submitting…" : "Yes, submit"}
          </button>
        </div>
      </div>
    </div>
  );
}

function ApplicationCard({ application, onChanged }) {
  const [busy, setBusy] = useState(false);
  const [showSubmitModal, setShowSubmitModal] = useState(false);
  const [error, setError] = useState(null);

  const decide = async (decision) => {
    setBusy(true);
    setError(null);
    try {
      await api.decideApplication(application.id, decision);
      if (decision === "approve") {
        // Chained: approving also fills the form right away — filling has
        // no external effect (no submission happens), so there's no
        // safety reason to make this a separate manual step. Submit stays
        // its own explicit, confirmed action — see CLAUDE.md §0.
        await api.fillApplication(application.id);
      }
      onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const fill = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.fillApplication(application.id);
      onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="border border-hairline rounded-lg p-5 bg-panel">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="font-display text-xl">{application.posting_title}</h3>
          <p className="text-sm text-paper-dim">{application.company_name}</p>
        </div>
        <span className="text-xs font-mono uppercase tracking-wide text-amber shrink-0">
          {application.status}
        </span>
      </div>

      {application.tailored_cover_letter_md && (
        <div className="mt-4 p-3 rounded-md bg-panel-raised text-sm text-paper-dim whitespace-pre-wrap max-h-40 overflow-y-auto">
          {application.tailored_cover_letter_md}
        </div>
      )}

      {application.tailored_resume_pdf_path && (
        <p className="mt-2 text-xs font-mono text-paper-dim">
          Resume PDF: {application.tailored_resume_pdf_path}
        </p>
      )}

      {error && <p className="text-rose text-sm mt-3 font-mono">{error}</p>}

      <div className="flex gap-2 mt-4">
        {application.status === "draft" && (
          <>
            <button
              onClick={() => decide("approve")}
              disabled={busy}
              className="px-4 py-2 rounded-md bg-teal text-ink text-sm font-medium hover:brightness-110 disabled:opacity-50 transition cursor-pointer"
            >
              {busy ? "Approving…" : "Approve"}
            </button>
            <button
              onClick={() => decide("reject")}
              disabled={busy}
              className="px-4 py-2 rounded-md border border-hairline text-paper-dim text-sm hover:text-rose hover:border-rose disabled:opacity-50 transition cursor-pointer"
            >
              Decline
            </button>
          </>
        )}

        {application.status === "approved" && (
          <button
            onClick={fill}
            disabled={busy}
            className="px-4 py-2 rounded-md bg-panel-raised border border-teal text-teal text-sm font-medium hover:bg-teal hover:text-ink disabled:opacity-50 transition cursor-pointer"
          >
            {busy ? "Filling…" : "Fill form"}
          </button>
        )}

        {application.status === "filled" && (
          <button
            onClick={() => setShowSubmitModal(true)}
            className="px-4 py-2 rounded-md bg-amber text-ink text-sm font-medium hover:brightness-110 transition cursor-pointer"
          >
            Review & submit
          </button>
        )}

        {application.status === "submitted" && (
          <span className="px-4 py-2 text-sm font-mono text-teal">✓ Submitted</span>
        )}
      </div>

      {showSubmitModal && (
        <SubmitConfirmModal
          application={application}
          onCancel={() => setShowSubmitModal(false)}
          onConfirmed={() => {
            setShowSubmitModal(false);
            onChanged();
          }}
        />
      )}
    </div>
  );
}

export default function ReviewPanel({ applications, onChanged }) {
  if (!applications || applications.length === 0) {
    return (
      <div className="border border-hairline rounded-lg p-8 text-center">
        <p className="text-paper-dim font-mono text-sm">
          No applications yet — run Match, then Tailor, to generate some.
        </p>
      </div>
    );
  }

  return (
    <div className="grid gap-4">
      {applications.map((a) => (
        <ApplicationCard key={a.id} application={a} onChanged={onChanged} />
      ))}
    </div>
  );
}
