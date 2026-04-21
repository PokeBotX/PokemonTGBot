import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type PokemonCardProps = {
  name: string;
  type: string;
  level: number;
  rarity: string;
};

export function PokemonCard({ name, type, level, rarity }: PokemonCardProps) {
  return (
    <Card className="border-slate-800 bg-slate-900 text-white shadow-lg">
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div>
          <p className="text-sm text-slate-400">{type}</p>
          <CardTitle className="mt-1 text-xl">{name}</CardTitle>
        </div>

        <Badge className="bg-yellow-400 text-slate-950 hover:bg-yellow-300">
          Lv. {level}
        </Badge>
      </CardHeader>

      <CardContent>
        <div className="rounded-2xl bg-slate-800 p-4 text-center text-5xl">
          ⚡
        </div>

        <p className="mt-4 text-sm text-slate-300">Редкость: {rarity}</p>
      </CardContent>
    </Card>
  );
}
