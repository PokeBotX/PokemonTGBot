type PageSectionProps = {
  title?: string;
  children: React.ReactNode;
};

export function PageSection({ title, children }: PageSectionProps) {
  return (
    <section className="flex flex-col gap-4">
      {title ? <h2 className="text-lg font-semibold text-white">{title}</h2> : null}
      {children}
    </section>
  );
}
