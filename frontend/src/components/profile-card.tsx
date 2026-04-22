"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useProfile } from "@/hooks/use-profile";

export function ProfileCard() {
  const { data, isLoading, isError } = useProfile();

  if (isLoading) {
    return (
      <Card className="border-slate-800 bg-slate-900 text-white shadow-lg">
        <CardHeader>
          <p className="text-sm text-slate-400">Профиль игрока</p>
          <CardTitle className="text-xl">Загрузка...</CardTitle>
        </CardHeader>
      </Card>
    );
  }

  if (isError || !data) {
    return (
      <Card className="border-red-500/30 bg-slate-900 text-white shadow-lg">
        <CardHeader>
          <p className="text-sm text-red-300">Профиль игрока</p>
          <CardTitle className="text-xl">Ошибка загрузки</CardTitle>
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card className="border-slate-800 bg-slate-900 text-white shadow-lg">
      <CardHeader>
        <p className="text-sm text-slate-400">Профиль игрока</p>
        <CardTitle className="text-xl">{data.name}</CardTitle>
      </CardHeader>

      <CardContent className="space-y-2 text-slate-300">
        <p>Username: @{data.username}</p>
        <p>Покемонов: {data.pokemonCount}</p>
        <p>Монет: {data.coins}</p>
      </CardContent>
    </Card>
  );
}
