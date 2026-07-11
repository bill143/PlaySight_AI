/** Inline spinner row used while data loads. */
export default function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 py-8 text-sm text-slate-400">
      <span
        aria-hidden
        className="h-4 w-4 animate-spin rounded-full border-2 border-slate-600 border-t-sky-500"
      />
      {label}
    </div>
  );
}
