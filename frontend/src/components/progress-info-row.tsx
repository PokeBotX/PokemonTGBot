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
    <div className="grid grid-cols-[72px_minmax(0,1fr)_96px] items-center gap-3 rounded-xl bg-slate-800/70 px-4 py-3 sm:grid-cols-[88px_minmax(0,1fr)_140px]">
      <span className="truncate text-sm text-slate-400">{label}</span>

      <div className="h-2.5 min-w-0 flex-1 overflow-hidden rounded-full bg-slate-700/80">
        <div
          className={`h-full rounded-full transition-[width] duration-300 ${barClassName}`}
          style={{ width: `${normalizedPercentage}%` }}
        />
      </div>

      <span className="truncate text-right font-medium text-white">{value}</span>
    </div>
  );
}
