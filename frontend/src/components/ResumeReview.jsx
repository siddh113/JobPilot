import { useEffect, useState } from "react";

const LOADING_CAPTIONS = [
  "Reading the job description…",
  "Matching your experience…",
  "Rewriting bullets to fit…",
  "Finalizing formatting…",
];

export function LoadingScreen({ title }) {
  const [captionIdx, setCaptionIdx] = useState(0);

  useEffect(() => {
    const id = setInterval(() => {
      setCaptionIdx((i) => (i + 1) % LOADING_CAPTIONS.length);
    }, 1400);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="flex flex-col items-center justify-center py-24 gap-4">
      <div className="w-10 h-10 rounded-full border-2 border-hairline border-t-teal animate-spin" />
      <p className="font-display text-xl">{title}</p>
      <p className="text-sm text-paper-dim font-mono">{LOADING_CAPTIONS[captionIdx]}</p>
    </div>
  );
}

export function Segments({ segments }) {
  if (!segments) return null;
  return segments.map((seg, i) =>
    seg.added ? (
      <mark key={i} className="bg-teal-dim/50 text-teal rounded-[3px] px-0.5">
        {seg.text}
      </mark>
    ) : (
      <span key={i}>{seg.text}</span>
    )
  );
}

export function ResumeDiffView({ resumeDiff }) {
  if (!resumeDiff) return null;
  return (
    <div className="text-sm leading-relaxed space-y-4">
      <div>
        <h2 className="font-display text-xl">{resumeDiff.name}</h2>
        {resumeDiff.title_line && <p className="text-paper-dim">{resumeDiff.title_line}</p>}
        {resumeDiff.contact_line && <p className="text-xs text-paper-dim font-mono">{resumeDiff.contact_line}</p>}
      </div>

      {resumeDiff.summary_segments && (
        <div>
          <h3 className="font-mono text-xs uppercase tracking-wide text-paper-dim mb-1">Professional Summary</h3>
          <p>
            <Segments segments={resumeDiff.summary_segments} />
          </p>
        </div>
      )}

      {resumeDiff.education?.length > 0 && (
        <div>
          <h3 className="font-mono text-xs uppercase tracking-wide text-paper-dim mb-1">Education</h3>
          {resumeDiff.education.map((edu, i) => (
            <div key={i} className="mb-1">
              <p className="font-medium">
                {edu.school}, {edu.detail} — {edu.dates}
              </p>
              {edu.notes?.map((n, j) => (
                <p key={j} className="text-paper-dim">• {n}</p>
              ))}
            </div>
          ))}
        </div>
      )}

      {resumeDiff.skills?.length > 0 && (
        <div>
          <h3 className="font-mono text-xs uppercase tracking-wide text-paper-dim mb-1">Skills</h3>
          {resumeDiff.skills.map((group, i) => (
            <p key={i}>
              <span className="font-medium">{group.category}:</span> <Segments segments={group.items_segments} />
            </p>
          ))}
        </div>
      )}

      {resumeDiff.experience?.length > 0 && (
        <div>
          <h3 className="font-mono text-xs uppercase tracking-wide text-paper-dim mb-1">Experience</h3>
          {resumeDiff.experience.map((job, i) => (
            <div key={i} className="mb-3">
              <p className="font-medium">
                {job.role}, {job.org} — {job.location}
              </p>
              {job.dates && <p className="text-paper-dim text-xs">{job.dates}</p>}
              {job.bullet_segments.map((segs, j) => (
                <p key={j}>
                  • <Segments segments={segs} />
                </p>
              ))}
            </div>
          ))}
        </div>
      )}

      {resumeDiff.projects?.length > 0 && (
        <div>
          <h3 className="font-mono text-xs uppercase tracking-wide text-paper-dim mb-1">Projects</h3>
          {resumeDiff.projects.map((proj, i) => (
            <div key={i} className="mb-3">
              <p className="font-medium">{proj.name}</p>
              {proj.bullet_segments.map((segs, j) => (
                <p key={j}>
                  • <Segments segments={segs} />
                </p>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function KeywordCoverage({ coverage }) {
  if (!coverage || coverage.total_count === 0) return null;
  return (
    <div className="border border-hairline rounded-lg p-4">
      <p className="text-sm text-paper mb-2">
        <span className="text-teal font-medium">{coverage.covered_count}</span> of{" "}
        {coverage.total_count} keywords covered
      </p>
      <div className="flex flex-wrap gap-1.5">
        {coverage.keywords.map((k) => {
          const isCovered = coverage.covered.includes(k);
          return (
            <span
              key={k}
              className={`text-[11px] font-mono px-2 py-0.5 rounded-full border ${
                isCovered
                  ? "border-teal text-teal bg-teal-dim/20"
                  : "border-hairline text-paper-dim"
              }`}
            >
              {isCovered ? "✓ " : ""}
              {k}
            </span>
          );
        })}
      </div>
    </div>
  );
}
