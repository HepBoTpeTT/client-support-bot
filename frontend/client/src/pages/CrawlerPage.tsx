import { useState, useEffect, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/lib/queryClient";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { useToast } from "@/hooks/use-toast";
import { useConfirm } from "@/hooks/use-confirm";
import { Globe, Play, RefreshCw, CheckCircle, AlertCircle, Clock, FileText, CheckSquare, Square, MessageSquare, ShoppingCart, Trophy, Sparkles, Trash2 } from "lucide-react";
import { Link } from "wouter";
import { cn } from "@/lib/utils";

interface CrawlSession {
    id?: number;
    targetUrl?: string;
    status: string;
    pagesFound?: number;
    pagesDone?: number;
    startedAt?: string;
    finishedAt?: string;
    errorMessage?: string;
}

export default function CrawlerPage() {
    const [url, setUrl] = useState("");
    const { toast } = useToast();
    const confirm = useConfirm();
    const qc = useQueryClient();

    const [justFinished, setJustFinished] = useState(false);
    const prevStatusRef = useRef<string | null>(null);

    const { data: settings } = useQuery<any>({
        queryKey: ["/api/settings"],
    });

    const { data: crawlStatus, refetch: refetchStatus } = useQuery<CrawlSession>({
        queryKey: ["/api/crawl/status"],
        // TanStack Query v5: callback receives { state } object, not data directly
        refetchInterval: (query) => query.state.data?.status === "running" ? 2000 : false,
    });

    const { data: sessions = [] } = useQuery<CrawlSession[]>({
        queryKey: ["/api/crawl/sessions"],
        refetchInterval: crawlStatus?.status === "running" ? 3000 : 10000,
    });

    // Pre-fill URL from settings
    useEffect(() => {
        if (settings?.targetUrl && !url) setUrl(settings.targetUrl);
    }, [settings]);

    // Hide "Done" message in new session
    useEffect(() => {
        if (
            crawlStatus?.status === "done" &&
            prevStatusRef.current !== null &&
            prevStatusRef.current !== "done"
        ) {
            setJustFinished(true);
        }
        prevStatusRef.current = crawlStatus?.status ?? null;
    }, [crawlStatus?.status]);

    const deleteCrawlHistory = useMutation({
        mutationFn: () => apiRequest("DELETE", "/api/crawl/sessions"),
        onSuccess: () => {
            toast({ title: "История очищена" });
            qc.invalidateQueries({ queryKey: ["/api/crawl/sessions"] });
        },
    });

    const handleDeleteCrawlHistory = async () => {
        const ok = await confirm({
            title: "Очистить историю запусков?",
            description: "Будет удалена история предыдущих запусков парсинга.",
            confirmText: "Очистить",
            cancelText: "Отмена",
            variant: "destructive",
        });

        if (!ok) return;
        deleteCrawlHistory.mutate();
    };

    const startCrawl = useMutation({
        mutationFn: (targetUrl: string) =>
            apiRequest("POST", "/api/crawl/start", { url: targetUrl }),
        onSuccess: () => {
            toast({ title: "Парсинг запущен", description: "Обходим страницы сайта..." });
            qc.invalidateQueries({ queryKey: ["/api/crawl/status"] });
            qc.invalidateQueries({ queryKey: ["/api/crawl/sessions"] });
        },
        onError: (e: any) => {
            toast({ title: "Ошибка", description: e.message, variant: "destructive" });
        },
    });

    const handleStart = () => {
        if (!url.trim()) {
            toast({ title: "Введите URL сайта", variant: "destructive" });
            return;
        }
        // Save URL to settings
        apiRequest("PATCH", "/api/settings", { targetUrl: url });
        startCrawl.mutate(url);
    };

    const displayPagesFound =
        crawlStatus?.status === "done"
            ? (crawlStatus?.pagesDone ?? 0)
            : (crawlStatus?.pagesFound ?? 0);

    const progress = displayPagesFound
        ? Math.round(((crawlStatus?.pagesDone ?? 0) / displayPagesFound) * 100)
        : 0;

    const statusIcon = {
        running: <RefreshCw className="w-4 h-4 animate-spin text-blue-400" />,
        done: <CheckCircle className="w-4 h-4 text-green-400" />,
        error: <AlertCircle className="w-4 h-4 text-red-400" />,
        idle: <Clock className="w-4 h-4 text-muted-foreground" />,
    };

    const statusLabel = {
        running: "В процессе",
        done: "Завершён",
        error: "Ошибка",
        idle: "Ожидание",
    };

    // ── Daily tasks ────────────────────────────────────────
    const { data: gamification } = useQuery<any>({
        queryKey: ["/api/gamification"],
        refetchInterval: 30000,
    });

    const completeTask = useMutation({
        mutationFn: (taskKey: string) =>
            apiRequest("POST", "/api/gamification/complete-task", { task_key: taskKey }),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ["/api/gamification"] });
        },
    });

    const taskIconMap: Record<string, React.ReactNode> = {
        MessageSquare: <MessageSquare className="w-4 h-4" />,
        ShoppingCart: <ShoppingCart className="w-4 h-4" />,
    };

    const tasks: any[] = gamification?.tasks ?? [];
    const allDone = tasks.length > 0 && tasks.every((t: any) => t.completed);
    const newCount = gamification?.stats?.newCount ?? 0;

    return (
        <div className="p-8 max-w-4xl">
            <div className="mb-8">
                <h1 className="text-xl font-semibold text-foreground flex items-center gap-2">
                    <Globe className="w-5 h-5 text-primary" />
                    Парсинг сайта
                </h1>
                <p className="text-sm text-muted-foreground mt-1">
                    Введите URL сайта — система автоматически обойдёт все дочерние страницы и создаст базу знаний для AI-помощника
                </p>
            </div>

            {/* Daily tasks widget */}
            <Card className={cn(
                "mb-6 border ",
                allDone
                    ? "bg-green-50 border-green-200 dark:bg-green-900/10 dark:border-green-800/40"
                    : "bg-card border-border"
            )}>
                <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                        <CardTitle className="text-base flex items-center gap-2">
                            {allDone
                                ? <CheckSquare className="w-4 h-4 text-green-500" />
                                : <Square className="w-4 h-4 text-muted-foreground" />}
                            Задачи на сегодня
                        </CardTitle>
                        <div className="flex items-center gap-2">
                            {newCount > 0 && (
                                <Link href="/achievements">
                                    <span className="flex items-center gap-1 text-xs bg-yellow-100 text-yellow-700 border border-yellow-200 dark:bg-yellow-900/40 dark:text-yellow-400 dark:border-yellow-800/50 rounded-full px-2 py-0.5 cursor-pointer hover:opacity-80 transition-opacity">
                                        <Sparkles className="w-3 h-3" />
                                        {newCount} новых достижений!
                                    </span>
                                </Link>
                            )}
                            <Link href="/achievements">
                                <span className="flex items-center gap-1 text-xs text-muted-foreground hover:text-primary cursor-pointer">
                                    <Trophy className="w-3.5 h-3.5" />
                                    {gamification?.stats?.unlocked ?? 0}/{gamification?.stats?.total ?? 0}
                                </span>
                            </Link>
                        </div>
                    </div>
                </CardHeader>
                <CardContent className="pt-0">
                    {tasks.length === 0 ? (
                        <p className="text-sm text-muted-foreground">Загрузка задач...</p>
                    ) : (
                        <div className="space-y-2">
                            {tasks.map((task: any) => (
                                <div
                                    key={task.key}
                                    data-testid={`daily-task-${task.key}`}
                                    className={cn(
                                        "flex items-center gap-3 p-3 rounded-lg border ",
                                        task.completed
                                            ? "bg-green-50 border-green-200 dark:bg-green-900/10 dark:border-green-800/30"
                                            : "bg-muted/40 border-border"
                                    )}
                                >
                                    <div className={cn(
                                        "flex-shrink-0",
                                        task.completed ? "text-green-500" : "text-muted-foreground"
                                    )}>
                                        {task.completed
                                            ? <CheckCircle className="w-4 h-4" />
                                            : (taskIconMap[task.icon] ?? <Square className="w-4 h-4" />)}
                                    </div>
                                    <span className={cn(
                                        "flex-1 text-sm",
                                        task.completed ? "line-through text-muted-foreground" : "text-foreground"
                                    )}>
                                        {task.title}
                                    </span>
                                    {task.no_action ? (
                                        <span className="text-xs text-muted-foreground italic">внешняя CRM</span>
                                    ) : !task.completed ? (
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            data-testid={`btn-complete-${task.key}`}
                                            onClick={() => completeTask.mutate(task.key)}
                                            disabled={completeTask.isPending}
                                            className="h-7 text-xs px-2"
                                        >
                                            Выполнено
                                        </Button>
                                    ) : null}
                                </div>
                            ))}
                        </div>
                    )}
                    {allDone && (
                        <p className="text-xs text-green-600 dark:text-green-400 mt-3 font-medium">
                            🎉 Все задачи выполнены! Отличная работа.
                        </p>
                    )}
                </CardContent>
            </Card>



            {/* URL input */}
            <Card className="mb-6 bg-card border-border">
                <CardHeader>
                    <CardTitle className="text-base">Адрес сайта</CardTitle>
                    <CardDescription>Введите корневой URL. Система обойдёт все страницы того же домена (максимум 200)</CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="flex gap-3">
                        <Input
                            data-testid="input-url"
                            value={url}
                            onChange={e => setUrl(e.target.value)}
                            placeholder="https://example.com"
                            className="flex-1 bg-muted border-border text-foreground placeholder:text-muted-foreground"
                            onKeyDown={e => e.key === "Enter" && handleStart()}
                        />
                        <Button
                            data-testid="button-start-crawl"
                            onClick={handleStart}
                            disabled={startCrawl.isPending || crawlStatus?.status === "running"}
                            className="bg-primary hover:bg-primary/90 gap-2"
                        >
                            {crawlStatus?.status === "running" ? (
                                <><RefreshCw className="w-4 h-4 animate-spin" /> Парсинг...</>
                            ) : (
                                <><Play className="w-4 h-4" /> Запустить</>
                            )}
                        </Button>
                    </div>
                </CardContent>
            </Card>

            {/* Current status */}
            {crawlStatus && crawlStatus.status !== "idle" && (
                <Card className="mb-6 bg-card border-border">
                    <CardHeader>
                        <CardTitle className="text-base flex items-center gap-2">
                            {statusIcon[crawlStatus.status as keyof typeof statusIcon]}
                            Текущий статус: {statusLabel[crawlStatus.status as keyof typeof statusLabel]}
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="grid grid-cols-3 gap-4">
                            <div className="bg-muted rounded-lg p-3 text-center">
                                <div className="text-2xl font-bold text-foreground">{displayPagesFound}</div>
                                <div className="text-xs text-muted-foreground mt-1">Найдено страниц</div>
                            </div>
                            <div className="bg-muted rounded-lg p-3 text-center">
                                <div className="text-2xl font-bold text-primary">{crawlStatus.pagesDone ?? 0}</div>
                                <div className="text-xs text-muted-foreground mt-1">Обработано</div>
                            </div>
                            <div className="bg-muted rounded-lg p-3 text-center">
                                <div className="text-2xl font-bold text-foreground">{progress}%</div>
                                <div className="text-xs text-muted-foreground mt-1">Прогресс</div>
                            </div>
                        </div>

                        {crawlStatus.status === "running" && (
                            <Progress value={progress} className="h-2" />
                        )}

                        {crawlStatus.targetUrl && (
                            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                <Globe className="w-3.5 h-3.5" />
                                <span className="truncate">{crawlStatus.targetUrl}</span>
                            </div>
                        )}

                        {crawlStatus.errorMessage && (
                            <div className="text-sm text-destructive bg-destructive/10 rounded p-3">
                                {crawlStatus.errorMessage}
                            </div>
                        )}

                        {crawlStatus.status === "done" && justFinished && (
                            <div className="flex items-center gap-2 text-sm status-done rounded p-3">
                                <CheckCircle className="w-4 h-4" />
                                База знаний успешно создана. Теперь AI-помощник готов отвечать на вопросы.
                            </div>
                        )}
                    </CardContent>
                </Card>
            )}

            {/* History */}
            {sessions.length > 0 && (
                <Card className="bg-card border-border">
                    <CardHeader>
                        <div className="flex items-center justify-between">
                            <CardTitle className="text-base flex items-center gap-2">
                                <FileText className="w-4 h-4 text-muted-foreground" />
                                История запусков
                            </CardTitle>
                            <Button
                                size="sm"
                                variant="destructive"
                                data-testid="btn-delete-crawl-history"
                                onClick={handleDeleteCrawlHistory}
                                disabled={deleteCrawlHistory.isPending}
                                className="gap-2"
                            >
                                <Trash2 className="w-3.5 h-3.5" />
                                Очистить историю
                            </Button>
                        </div>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-2">
                            {sessions.slice(0, 5).map((s, i) => (
                                <div key={i} className="flex items-center justify-between py-2 border-b border-border last:border-0">
                                    <div className="text-sm text-foreground truncate max-w-xs">{s.targetUrl}</div>
                                    <div className="flex items-center gap-3 ml-4 flex-shrink-0">
                                        <span className="text-xs text-muted-foreground">{s.pagesDone ?? 0} стр.</span>
                                        <Badge
                                            data-testid={`status-session-${i}`}
                                            className={`text-xs ${s.status === "done" ? "status-done" :
                                                    s.status === "error" ? "status-error" :
                                                        s.status === "running" ? "status-running" : "status-pending"
                                                }`}
                                            variant="outline"
                                        >
                                            {statusLabel[s.status as keyof typeof statusLabel] ?? s.status}
                                        </Badge>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
