/** CSS-grid heatmap for the 12x8 movement-proxy grid (`player_match_stats.heatmap_json`). */

interface HeatmapProps {
  grid: number[][] | null | undefined;
  caption?: string;
}

function normalizeGrid(grid: number[][] | null | undefined): number[][] {
  if (!grid || !Array.isArray(grid) || grid.length === 0) return [];
  const rows = grid.map((row) =>
    Array.isArray(row) ? row.map((v) => (typeof v === "number" && Number.isFinite(v) ? v : 0)) : [],
  );
  const width = Math.max(...rows.map((r) => r.length));
  if (width === 0) return [];
  const padded = rows.map((r) => [...r, ...Array<number>(Math.max(0, width - r.length)).fill(0)]);
  // Render landscape (pitch-shaped) regardless of row/column orientation in the JSON.
  if (padded.length > width) {
    return padded[0].map((_, col) => padded.map((row) => row[col] ?? 0));
  }
  return padded;
}

export default function Heatmap({ grid, caption }: HeatmapProps) {
  const rows = normalizeGrid(grid);
  if (rows.length === 0) {
    return <p className="text-xs text-slate-500">No heat data yet.</p>;
  }
  const cols = rows[0].length;
  const max = Math.max(...rows.flat(), 1e-9);
  return (
    <figure>
      <div
        className="grid w-full gap-px overflow-hidden rounded-md border border-slate-800 bg-slate-900"
        style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}
      >
        {rows.flatMap((row, r) =>
          row.map((value, c) => (
            <div
              key={`${r}-${c}`}
              className="aspect-square w-full"
              title={value.toFixed(3)}
              style={{
                backgroundColor: `rgba(52, 211, 153, ${value > 0 ? 0.08 + 0.9 * (value / max) : 0.02})`,
              }}
            />
          )),
        )}
      </div>
      {caption ? <figcaption className="mt-1 text-xs text-slate-500">{caption}</figcaption> : null}
    </figure>
  );
}
