type InfoRowProps = {
  label: string;
  value: string | number;
};

export function InfoRow({ label, value }: InfoRowProps) {
  return (
    <div className="flex items-center justify-between rounded-xl bg-slate-800/70 px-4 py-3">
      <span className="text-sm text-slate-400">{label}</span>
      <span className="font-medium text-white">{value}</span>
    </div>
  );
}
