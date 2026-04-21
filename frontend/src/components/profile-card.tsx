import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function ProfileCard() {
  return (
    <Card className="border-slate-800 bg-slate-900 text-white shadow-lg">
      <CardHeader>
        <p className="text-sm text-slate-400">Профиль игрока</p>
        <CardTitle className="text-xl">Тренер Pokémon</CardTitle>
      </CardHeader>

      <CardContent>
        <p className="text-slate-300">
          Здесь скоро появится твоя коллекция, статистика и редкие находки.
        </p>
      </CardContent>
    </Card>
  );
}
