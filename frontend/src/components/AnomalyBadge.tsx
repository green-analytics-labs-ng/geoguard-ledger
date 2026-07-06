interface Props {
  score: number;
  showLabel?: boolean;
  size?: "sm" | "md";
}

export default function AnomalyBadge({ score, showLabel = true, size = "sm" }: Props) {
  const pct = (score * 100).toFixed(1);
  let color: string;
  let label: string;

  if (score < 0.05) {
    color = "bg-green-100 text-green-800 border-green-200";
    label = "Normal";
  } else if (score < 0.2) {
    color = "bg-yellow-100 text-yellow-800 border-yellow-200";
    label = "Suspect";
  } else {
    color = "bg-red-100 text-red-800 border-red-200";
    label = "Anomalous";
  }

  const px = size === "sm" ? "px-2 py-0.5" : "px-3 py-1";

  return (
    <span
      className={`inline-flex items-center gap-1.5 ${px} text-xs font-medium rounded-full border ${color}`}
      title={`Anomaly score: ${pct}% - ${label}`}
    >
      <span
        className={`w-1.5 h-1.5 rounded-full ${
          score < 0.05 ? "bg-green-500" : score < 0.2 ? "bg-yellow-500" : "bg-red-500"
        }`}
      />
      {pct}%
      {showLabel && <span className="opacity-70">{label}</span>}
    </span>
  );
}
