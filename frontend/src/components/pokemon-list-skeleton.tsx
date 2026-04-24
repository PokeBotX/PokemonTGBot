import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

function PokemonCardSkeleton() {
  return (
    <Card className="border-slate-800 bg-slate-900 text-white shadow-lg">
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div className="space-y-2">
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-6 w-28" />
        </div>

        <Skeleton className="h-6 w-14 rounded-full" />
      </CardHeader>

      <CardContent className="space-y-4">
        <Skeleton className="h-24 w-full rounded-2xl" />
        <Skeleton className="h-4 w-24" />
      </CardContent>
    </Card>
  );
}

export function PokemonListSkeleton() {
  return (
    <div className="flex flex-col gap-4">
      <PokemonCardSkeleton />
      <PokemonCardSkeleton />
      <PokemonCardSkeleton />
    </div>
  );
}
