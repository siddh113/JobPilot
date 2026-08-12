import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import { LoadingScreen, ResumeDiffView, KeywordCoverage } from "./ResumeReview";

export function ChatEditor({ applicationId, onRevised }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async () => {
    const instruction = input.trim();
    if (!instruction || busy) return;
    setInput("");
    setError(null);
    setMessages((m) => [...m, { role: "user", text: instruction }]);
    setBusy(true);
    try {
      const result = await api.reviseApplication(applicationId, instruction);
      setMessages((m) => [...m, { role: "assistant", text: result.explanation || "Done." }]);
      onRevised(result);
    } catch (err) {
      setError(err.message);
      setMessages((m) => [...m, { role: "assistant", text: `Couldn't apply that: ${err.message}` }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="border border-hairline rounded-lg flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-3 space-y-2 min-h-[120px] max-h-64">
        {messages.length === 0 && (
          <p className="text-xs text-paper-dim font-mono">
            Ask me to change anything — "make the summary punchier", "lead with the ETL work", etc.
          </p>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={`text-sm px-3 py-2 rounded-md max-w-[90%] ${
              m.role === "user" ? "bg-panel-raised ml-auto text-paper" : "text-paper-dim"
            }`}
          >
            {m.text}
          </div>
        ))}
        {busy && <p className="text-xs text-paper-dim font-mono">Revising…</p>}
        <div ref={bottomRef} />
      </div>
      {error && <p className="text-rose text-xs font-mono px-3">{error}</p>}
      <div className="flex gap-2 p-2 border-t border-hairline">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          disabled={busy}
          placeholder="Ask me to change anything…"
          className="flex-1 bg-panel-raised border border-hairline rounded-md px-3 py-2 text-sm outline-none focus:border-teal disabled:opacity-50"
        />
        <button
          onClick={send}
          disabled={busy || !input.trim()}
          className="px-4 py-2 rounded-md bg-teal text-ink text-sm font-medium hover:brightness-110 disabled:opacity-50 transition cursor-pointer"
        >
          Send
        </button>
      </div>
    </div>
  );
}

export default function TailoringModal({ posting, onClose, onDone }) {
  const [phase, setPhase] = useState("loading"); // loading | review | error
  const [applicationId, setApplicationId] = useState(null);
  const [tailoring, setTailoring] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { application_id } = await api.applyToPosting(posting.id);
        if (cancelled) return;
        setApplicationId(application_id);
        const detail = await api.getTailoring(application_id);
        if (cancelled) return;
        setTailoring(detail);
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
  }, [posting.id]);

  const handleRevised = (result) => {
    setTailoring((prev) => ({
      ...prev,
      resume: result.resume,
      resume_diff: result.resume_diff,
      keyword_coverage: result.keyword_coverage,
    }));
  };

  // The draft Application is created the moment tailoring starts (see the
  // effect above) — so once applicationId is set, it already exists in the
  // Applications tab regardless of how this modal gets dismissed. Closing
  // it here should behave the same as the explicit "send to Applications"
  // button, or the Jobs card would be left stuck pointing at a posting
  // that's already been applied to.
  const handleClose = () => {
    if (applicationId) {
      onDone(posting);
    } else {
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center p-4 z-50">
      <div className="bg-panel border border-hairline rounded-lg w-full max-w-4xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-hairline">
          <div>
            <h2 className="font-display text-lg">{posting.title}</h2>
            <p className="text-xs text-paper-dim">{posting.company_name}</p>
          </div>
          <button
            onClick={handleClose}
            className="text-paper-dim hover:text-paper text-sm cursor-pointer"
          >
            ✕
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          {phase === "loading" && (
            <LoadingScreen title={`Optimizing your resume for ${posting.company_name}`} />
          )}

          {phase === "error" && (
            <div className="text-center py-16">
              <p className="text-rose text-sm font-mono">{error}</p>
            </div>
          )}

          {phase === "review" && tailoring && (
            <div className="grid md:grid-cols-[1fr_320px] gap-6">
              <ResumeDiffView resumeDiff={tailoring.resume_diff} />
              <div className="flex flex-col gap-4">
                <KeywordCoverage coverage={tailoring.keyword_coverage} />
                <div className="flex-1 min-h-[240px]">
                  <ChatEditor applicationId={applicationId} onRevised={handleRevised} />
                </div>
              </div>
            </div>
          )}
        </div>

        {phase === "review" && (
          <div className="flex justify-end gap-3 px-6 py-4 border-t border-hairline">
            <button
              onClick={handleClose}
              className="px-4 py-2 rounded-md bg-teal text-ink text-sm font-medium hover:brightness-110 transition cursor-pointer"
            >
              Looks good — send to Applications
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
