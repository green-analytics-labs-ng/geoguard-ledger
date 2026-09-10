interface Props {
  warnings: string[];
}

/**
 * Renders the geochemical plausibility findings returned alongside the
 * statistical anomaly score, e.g.
 * `[ERROR] pH: 1 value(s) outside the plausible range 0 to 14 (rows 4)`.
 *
 * Findings are computed from deterministic range checks rather than the ML
 * model, so they surface errors the Isolation Forest cannot see. The backend
 * prefixes each entry with `[ERROR]` or `[WARNING]`; that prefix drives the
 * styling here.
 */
export default function AnomalyWarnings({ warnings }: Props) {
  if (warnings.length === 0) return null;

  const errorCount = warnings.filter((w) => w.startsWith("[ERROR]")).length;

  return (
    <div
      className={`rounded-lg border p-3 text-sm ${
        errorCount > 0
          ? "bg-red-50 border-red-200 text-red-800"
          : "bg-yellow-50 border-yellow-200 text-yellow-800"
      }`}
    >
      <p className="font-semibold mb-2">
        {errorCount > 0
          ? `${errorCount} impossible value${errorCount === 1 ? "" : "s"} detected`
          : "Plausibility warnings"}
      </p>
      <ul className="space-y-1">
        {warnings.map((warning) => (
          <li key={warning} className="font-mono text-xs break-words">
            {warning}
          </li>
        ))}
      </ul>
    </div>
  );
}
