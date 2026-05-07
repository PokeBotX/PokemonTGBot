type ProgressInfoRowProps = {
  label: string;
  value: string | number;
  percentage: number;
  barClassName: string;
};

export function ProgressInfoRow({
  label,
  value,
  percentage,
  barClassName,
}: ProgressInfoRowProps) {
  const normalizedPercentage = Math.max(0, Math.min(percentage, 100));

  return (
    <div className="flex items-center gap-3 rounded-xl bg-slate-800/70 px-4 py-3">
      <span className="min-w-0 shrink-0 text-sm text-slate-400">{label}</span>

      <div className="h-2.5 min-w-0 flex-1 overflow-hidden rounded-full bg-slate-700/80">
        <div
          className={`h-full rounded-full transition-[width] duration-300 ${barClassName}`}
          style={{ width: `${normalizedPercentage}%` }}
        />
      </div>

      <span className="shrink-0 text-right font-medium text-white">{value}</span>
    </div>
  );
}
