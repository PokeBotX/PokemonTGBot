type EmptyStateProps = {
  title: string;
  description: string;
  icon?: string;
};

export function EmptyState({
  title,
  description,
  icon = "📭",
}: EmptyStateProps) {
  return (
    <div className="rounded-3xl border border-dashed border-slate-700 bg-slate-900/60 p-6 text-center">
      <div className="text-4xl">{icon}</div>
      <h2 className="mt-4 text-xl font-semibold text-white">{title}</h2>
      <p className="mt-2 text-sm text-slate-400">{description}</p>
    </div>
  );
}
