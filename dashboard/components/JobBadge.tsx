/** Colored status chip for jobs, matches, video assets and upload records. */

const STYLES: Record<string, string> = {
  created: "border-slate-600 bg-slate-800 text-slate-300",
  registered: "border-slate-600 bg-slate-800 text-slate-300",
  queued: "border-slate-600 bg-slate-800 text-slate-300",
  pending: "border-slate-600 bg-slate-800 text-slate-300",
  processing: "border-sky-700 bg-sky-950 text-sky-300",
  running: "border-sky-700 bg-sky-950 text-sky-300",
  uploading: "border-sky-700 bg-sky-950 text-sky-300",
  processed: "border-emerald-700 bg-emerald-950 text-emerald-300",
  succeeded: "border-emerald-700 bg-emerald-950 text-emerald-300",
  ready: "border-emerald-700 bg-emerald-950 text-emerald-300",
  failed: "border-rose-700 bg-rose-950 text-rose-300",
  cancelled: "border-amber-700 bg-amber-950 text-amber-300",
};

const ACTIVE_STATUSES = new Set(["processing", "running", "uploading", "queued", "pending"]);

export default function JobBadge({ status }: { status: string }) {
  const cls = STYLES[status] ?? "border-slate-600 bg-slate-800 text-slate-300";
  const active = ACTIVE_STATUSES.has(status);
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium ${cls}`}
    >
      {active ? <span aria-hidden className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" /> : null}
      {status}
    </span>
  );
}
