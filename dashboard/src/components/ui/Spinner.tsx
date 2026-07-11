import * as React from "react";

function cn(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

export function Spinner({
  className
}: {
  className?: string;
}) {
  return (
    <div
      className={cn(
        "h-6 w-6 animate-spin rounded-full border-2 border-slate-700 border-t-primary-500",
        className
      )}
      role="status"
      aria-label="Loading"
    />
  );
}
