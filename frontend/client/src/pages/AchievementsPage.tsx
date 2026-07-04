import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/lib/queryClient";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Trophy, Lock, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { useEffect } from "react";

interface AchievementItem {
  key: string;
  emoji: string;
  title: string;
  description: string;
  category: string;
  unlocked: boolean;
  unlockedAt: string | null;
  isNew: boolean;
}

interface GamificationData {
  achievements: AchievementItem[];
  tasks: any[];
  stats: { total: number; unlocked: number; newCount: number };
}

const CATEGORY_LABELS: Record<string, { label: string; color: string }> = {
  crawler:  { label: "Парсинг",    color: "bg-blue-100 text-blue-700 border-blue-200 dark:bg-blue-900/40 dark:text-blue-400 dark:border-blue-800/50" },
  dialogs:  { label: "Диалоги",   color: "bg-purple-100 text-purple-700 border-purple-200 dark:bg-purple-900/40 dark:text-purple-400 dark:border-purple-800/50" },
  operator: { label: "Оператор",  color: "bg-green-100 text-green-700 border-green-200 dark:bg-green-900/40 dark:text-green-400 dark:border-green-800/50" },
  settings: { label: "Настройки", color: "bg-orange-100 text-orange-700 border-orange-200 dark:bg-orange-900/40 dark:text-orange-400 dark:border-orange-800/50" },
  daily:    { label: "Стрик",     color: "bg-yellow-100 text-yellow-700 border-yellow-200 dark:bg-yellow-900/40 dark:text-yellow-400 dark:border-yellow-800/50" },
};

const CATEGORIES = ["crawler", "dialogs", "operator", "settings", "daily"] as const;

document.title = "Достижения"

export default function AchievementsPage() {
  const qc = useQueryClient();

  const { data, isLoading } = useQuery<GamificationData>({
    queryKey: ["/api/gamification"],
    refetchInterval: 10000,
  });

  const markSeen = useMutation({
    mutationFn: () => apiRequest("POST", "/api/gamification/mark-seen"),
  });


  useEffect(() => {
    return () => {
        if (data?.stats.newCount && data.stats.newCount > 0) {
            markSeen.mutate();
        }
    };
  }, [data?.stats.newCount]);

  const formatDate = (d: string) => {
    try {
      return new Date(d).toLocaleDateString("ru-RU", {
        day: "2-digit", month: "2-digit", year: "2-digit",
      });
    } catch { return d; }
  };

  const unlocked = data?.stats.unlocked ?? 0;
  const total = data?.stats.total ?? 0;
  const pct = total > 0 ? Math.round((unlocked / total) * 100) : 0;

  return (
    <div className="p-8 max-w-5xl">
      {/* Header */}
      <div className="mb-8 flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground flex items-center gap-2">
            <Trophy className="w-5 h-5 text-primary" />
            Достижения
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Разблокируйте все {total} достижений, активно используя систему
          </p>
        </div>
        {data?.stats.newCount ? (
          <Badge className="bg-yellow-100 text-yellow-700 border border-yellow-200 dark:bg-yellow-900/40 dark:text-yellow-400 dark:border-yellow-800/50 gap-1.5 px-3 py-1 text-sm animate-pulse">
            <Sparkles className="w-3.5 h-3.5" />
            {data.stats.newCount} новых!
          </Badge>
        ) : null}
      </div>

      {/* Overall progress */}
      <Card className="mb-8 bg-card border-border">
        <CardContent className="pt-6">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Trophy className="w-5 h-5 text-yellow-500" />
              <span className="font-semibold text-foreground">Общий прогресс</span>
            </div>
            <span className="text-sm font-mono text-muted-foreground">
              {unlocked} / {total}
            </span>
          </div>
          <Progress value={pct} className="h-3 mb-2" />
          <p className="text-xs text-muted-foreground text-right">{pct}% выполнено</p>
        </CardContent>
      </Card>

      {isLoading ? (
        <div className="text-sm text-muted-foreground text-center py-12">Загрузка...</div>
      ) : (
        CATEGORIES.map((cat) => {
          const items = data?.achievements.filter((a) => a.category === cat) ?? [];
          if (!items.length) return null;
          const catMeta = CATEGORY_LABELS[cat];
          const catUnlocked = items.filter((a) => a.unlocked).length;

          return (
            <div key={cat} className="mb-8">
              <div className="flex items-center gap-3 mb-4">
                <h2 className="text-sm font-semibold text-foreground">{catMeta.label}</h2>
                <span className={cn("text-xs border rounded px-2 py-0.5 font-medium", catMeta.color)}>
                  {catUnlocked}/{items.length}
                </span>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                {items.map((ach) => (
                  <div
                    key={ach.key}
                    data-testid={`achievement-${ach.key}`}
                    className={cn(
                      "relative rounded-xl border p-4",
                      ach.unlocked
                        ? "bg-card border-primary/30 shadow-sm"
                        : "bg-muted/30 border-border opacity-60"
                    )}
                  >
                    {/* New badge */}
                    {ach.isNew && (
                      <span className="absolute top-2 right-2 text-xs bg-yellow-400 text-yellow-900 rounded-full px-1.5 py-0.5 font-bold leading-none">
                        NEW
                      </span>
                    )}

                    <div className="flex items-start gap-3">
                      <div
                        className={cn(
                          "w-10 h-10 rounded-xl flex items-center justify-center text-xl flex-shrink-0",
                          ach.unlocked
                            ? "bg-primary/10"
                            : "bg-muted"
                        )}
                      >
                        {ach.unlocked ? ach.emoji : <Lock className="w-4 h-4 text-muted-foreground" />}
                      </div>
                      <div className="min-w-0">
                        <div className={cn(
                          "text-sm font-semibold truncate",
                          ach.unlocked ? "text-foreground" : "text-muted-foreground"
                        )}>
                          {ach.title}
                        </div>
                        <div className="text-xs text-muted-foreground leading-snug mt-0.5">
                          {ach.description}
                        </div>
                        {ach.unlocked && ach.unlockedAt && (
                          <div className="text-xs text-primary/70 mt-1.5 font-medium">
                            ✓ {formatDate(ach.unlockedAt)}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          );
        })
      )}
    </div>
  );
}
