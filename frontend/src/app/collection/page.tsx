import { AppShell } from "@/components/app-shell";
import { CollectionScreen } from "@/components/collection-screen";

export default function CollectionPage() {
  return (
    <AppShell
      className="bg-slate-950 px-3 py-4 pb-28 text-slate-100"
      navVariant="minimal"
      showScrollToTop
    >
      <CollectionScreen />
    </AppShell>
  );
}
