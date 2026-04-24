"use client";

import { ErrorState } from "@/components/error-state";
import { InfoRow } from "@/components/info-row";
import { ProfileCardSkeleton } from "@/components/profile-card-skeleton";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useProfile } from "@/hooks/use-profile";

export function ProfileCard() {
  const { data, isLoading, isError } = useProfile();

  if (isLoading) {
    return <ProfileCardSkeleton />;
  }

  if (isError || !data) {
    return (
      <ErrorState
        icon="👤"
        title="Не удалось загрузить профиль"
        description="Попробуй обновить страницу чуть позже."
      />
    );
  }

  return (
    <Card className="border-slate-800 bg-slate-900 text-white shadow-lg">
      <CardHeader>
        <p className="text-sm text-slate-400">Профиль игрока</p>
        <CardTitle className="text-xl">{data.name}</CardTitle>
      </CardHeader>

      <CardContent className="space-y-3">
        <InfoRow label="Username" value={`@${data.username}`} />
        <InfoRow label="Покемонов" value={data.pokemonCount} />
        <InfoRow label="Монет" value={data.coins} />
      </CardContent>
    </Card>
  );
}
