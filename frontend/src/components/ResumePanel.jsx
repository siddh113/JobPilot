import { useState } from "react";
import { api } from "../lib/api";

export default function ResumePanel() {
  const [file, setFile] = useState(null);
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const handleImport = async () => {
    if (!file) return;
    setImporting(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.importResume(file);
      setResult(res);
    } catch (err) {
      setError(err.message);
    } finally {
      setImporting(false);
    }
  };

  return (
    <div className="border border-hairline rounded-lg p-6 bg-panel max-w-xl">
      <h3 className="font-display text-xl mb-2">Resume</h3>
      <p className="text-sm text-paper-dim mb-4">
        Upload your resume (PDF, DOCX, MD, or TXT). It's extracted and
        reformatted into the base resume every tailored application is
        grounded in — nothing invented, only reformatted.
      </p>

      <input
        type="file"
        accept=".pdf,.docx,.md,.txt"
        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        className="block w-full text-sm text-paper-dim file:mr-4 file:py-2 file:px-4
                   file:rounded-md file:border file:border-hairline file:bg-panel-raised
                   file:text-paper file:text-sm file:cursor-pointer hover:file:border-teal"
      />

      <button
        onClick={handleImport}
        disabled={!file || importing}
        className="mt-4 px-4 py-2 rounded-md bg-teal text-ink text-sm font-medium hover:brightness-110 disabled:opacity-40 transition cursor-pointer"
      >
        {importing ? "Importing…" : "Import resume"}
      </button>

      {error && <p className="text-rose text-sm mt-3 font-mono">{error}</p>}

      {result && (
        <div className="mt-4">
          <p className="text-teal text-sm font-mono mb-2">Saved to {result.saved_to}</p>
          <pre className="p-3 rounded-md bg-panel-raised text-xs text-paper-dim whitespace-pre-wrap max-h-64 overflow-y-auto">
            {result.preview}
          </pre>
          <p className="text-xs text-paper-dim mt-2">
            Review the full file before running Match/Tailor.
          </p>
        </div>
      )}
    </div>
  );
}
