import { BottomNav } from "@/components/bottom-nav";
import { cn } from "@/lib/utils";

type AppShellProps = {
  children: React.ReactNode;
  className?: string;
  contentClassName?: string;
  navVariant?: "default" | "minimal";
};

export function AppShell({
  children,
  className,
  contentClassName,
  navVariant = "default",
}: AppShellProps) {
  return (
    <main
      className={cn(
        "min-h-screen bg-slate-950 px-4 py-6 pb-28 text-white",
        className
      )}
    >
      <section className={cn("mx-auto flex max-w-md flex-col gap-4", contentClassName)}>
        {children}
      </section>

      <BottomNav variant={navVariant} />
    </main>
  );
}
