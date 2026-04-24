type ErrorStateProps = {
  title: string;
  description: string;
  icon?: string;
};

export function ErrorState({
  title,
  description,
  icon = "⚠️",
}: ErrorStateProps) {
  return (
    <div className="rounded-3xl border border-red-500/30 bg-red-500/10 p-6 text-center">
      <div className="text-4xl">{icon}</div>
      <h2 className="mt-4 text-xl font-semibold text-white">{title}</h2>
      <p className="mt-2 text-sm text-slate-300">{description}</p>
    </div>
  );
}
