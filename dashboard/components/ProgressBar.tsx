/** Horizontal progress bar for a 0..1 value. */

interface ProgressBarProps {
  /** Progress in [0, 1]; values outside the range are clamped. */
  value: number;
  className?: string;
  /** Override the fill color class (default sky). */
  barClassName?: string;
}

export default function ProgressBar({ value, className, barClassName }: ProgressBarProps) {
  const clamped = Math.max(0, Math.min(1, Number.isFinite(value) ? value : 0));
  return (
    <div className={`h-2 w-full overflow-hidden rounded-full bg-slate-800 ${className ?? ""}`}>
      <div
        className={`h-full rounded-full transition-[width] duration-500 ${barClassName ?? "bg-sky-500"}`}
        style={{ width: `${clamped * 100}%` }}
      />
    </div>
  );
}
