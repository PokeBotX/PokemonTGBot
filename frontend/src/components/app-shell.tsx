import { BottomNav } from "@/components/bottom-nav";

type AppShellProps = {
  children: React.ReactNode;
};

export function AppShell({ children }: AppShellProps) {
  return (
    <main className="min-h-screen bg-slate-950 px-4 py-6 pb-28 text-white">
      <section className="mx-auto flex max-w-md flex-col gap-6">
        {children}
      </section>

      <BottomNav />
    </main>
  );
}
