import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/lib/queryClient";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useToast } from "@/hooks/use-toast";
import { useConfirm } from "@/hooks/use-confirm";
import { Table2, Search, Trash2, Eye, ExternalLink, Database } from "lucide-react";

interface Page {
    id: number;
    url: string;
    title: string;
    content: string;
    status: string;
    crawledAt: string | null;
    contentLen?: number | null;
}

export default function PagesPage() {
    const [search, setSearch] = useState("");
    const [selectedPage, setSelectedPage] = useState<Page | null>(null);
    const [pageContent, setPageContent] = useState<string | null>(null);

    const openPagePreview = async (page: Page) => {
        setSelectedPage(page);
        setPageContent(null);
        try {
            const res = await fetch(`/api/pages/${page.id}/content`);
            const data = await res.json();
            setPageContent(data.content || "Контент отсутствует");
        } catch {
            setPageContent("Ошибка загрузки контента");
        }
    };

    const { toast } = useToast();
    const confirm = useConfirm();
    const qc = useQueryClient();

    const { data: crawlStatus } = useQuery<{status : string}>({
        queryKey: ["/api/crawl/status"],
        refetchInterval: (query) =>
            query.state.data?.status === "running" ? 2000 : false,
    });

    // 2. Страницы поллим только пока краулер работает
    const { data: pages = [], isLoading } = useQuery<Page[]>({
        queryKey: ["/api/pages"],
        refetchInterval: crawlStatus?.status === "running" || crawlStatus?.status === "done"
                        ? 2000 : false,
    });

    const deletePage = useMutation({
        mutationFn: (id: number) => apiRequest("DELETE", `/api/pages/${id}`),
        onSuccess: () => {
            toast({ title: "Страница удалена" });
        },
    });

    const clearAll = useMutation({
        mutationFn: () => apiRequest("DELETE", "/api/pages"),
        onSuccess: () => {
            toast({ title: "База знаний очищена" });
        },
    });

    const handleDeletePage = async (id: number, title?: string) => {
        const ok = await confirm({
            title: "Удалить страницу?",
            description: title
                ? `Страница "${title}" будет удалена из базы знаний.`
                : "Страница будет удалена из базы знаний.",
            confirmText: "Удалить",
            cancelText: "Отмена",
            variant: "destructive",
        });

        if (!ok) return;
        deletePage.mutate(id);
    };

    const handleClearAll = async () => {
        const ok = await confirm({
            title: "Удалить все страницы?",
            description: "Вся база знаний из спарсированных страниц будет очищена.",
            confirmText: "Очистить всё",
            cancelText: "Отмена",
            variant: "destructive",
        });

        if (!ok) return;
        clearAll.mutate();
    };

    const filtered = pages.filter(p =>
        p.url.toLowerCase().includes(search.toLowerCase()) ||
        p.title.toLowerCase().includes(search.toLowerCase())
    );

    const stats = {
        total: pages.length,
        done: pages.filter(p => p.status === "done").length,
        error: pages.filter(p => p.status === "error").length,
        pending: pages.filter(p => p.status === "pending").length,
    };

    return (
        <div className="p-8 max-w-6xl">
            <div className="mb-8">
                <h1 className="text-xl font-semibold text-foreground flex items-center gap-2">
                    <Table2 className="w-5 h-5 text-primary" />
                    База знаний
                </h1>
                <p className="text-sm text-muted-foreground mt-1">
                    Все спарсированные страницы сайта. AI-помощник использует этот контент для ответов.
                </p>
            </div>

            {/* Controls */}
            <Card className="mb-4 bg-card border-border">
                <CardContent className="p-4 flex gap-3 items-center">
                    <div className="relative flex-1">
                        <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                        <Input
                            data-testid="input-search-pages"
                            value={search}
                            onChange={e => setSearch(e.target.value)}
                            placeholder="Поиск по URL или заголовку..."
                            className="pl-9 bg-muted border-border text-foreground placeholder:text-muted-foreground"
                        />
                    </div>
                    <Button
                        data-testid="button-clear-all"
                        variant="destructive"
                        size="sm"
                        onClick={handleClearAll}
                        disabled={pages.length === 0}
                        className="gap-2"
                    >
                        <Trash2 className="w-4 h-4" />
                        Очистить всё
                    </Button>
                </CardContent>
            </Card>

            {/* Table */}
            <Card className="bg-card border-border">
                <CardContent className="p-0">
                    {isLoading ? (
                        <div className="p-8 text-center text-muted-foreground">Загрузка...</div>
                    ) : filtered.length === 0 ? (
                        <div className="p-8 text-center">
                            <Database className="w-10 h-10 text-muted-foreground mx-auto mb-3" />
                            <p className="text-muted-foreground">
                                {pages.length === 0 ? "База знаний пуста. Запустите парсинг сайта." : "Ничего не найдено по вашему запросу."}
                            </p>
                        </div>
                    ) : (
                        <ScrollArea className="h-[calc(100vh-250px)]">
                            <table className="w-full">
                                <thead className="border-b border-border sticky top-0 bg-card">
                                    <tr>
                                        <th className="text-left text-xs font-medium text-muted-foreground px-4 py-3 w-12">#</th>
                                        <th className="text-left text-xs font-medium text-muted-foreground px-4 py-3">Заголовок / URL</th>
                                        <th className="text-left text-xs font-medium text-muted-foreground px-4 py-3 w-32">Размер</th>
                                        <th className="text-left text-xs font-medium text-muted-foreground px-4 py-3 w-28">Статус</th>
                                        <th className="text-right text-xs font-medium text-muted-foreground px-4 py-3 w-24">Действия</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {filtered.map((page, idx) => (
                                        <tr key={page.id} className="border-b border-border last:border-0 hover:bg-muted/30 transition-colors">
                                            <td className="px-4 py-3 text-sm text-muted-foreground">{idx + 1}</td>
                                            <td className="px-4 py-3">
                                                <div className="text-sm font-medium text-foreground truncate max-w-xs"
                                                    data-testid={`text-page-title-${page.id}`}>
                                                    {page.title || "Без заголовка"}
                                                </div>
                                                <a
                                                    href={page.url}
                                                    target="_blank"
                                                    rel="noopener noreferrer"
                                                    className="text-xs text-muted-foreground hover:text-primary flex items-center gap-1 mt-0.5 truncate max-w-xs"
                                                >
                                                    {page.url}
                                                    <ExternalLink className="w-3 h-3 flex-shrink-0" />
                                                </a>
                                            </td>
                                            <td className="px-4 py-3 text-sm text-muted-foreground">
                                                {page.contentLen ? `${Math.round(page.contentLen / 1000)}K знак.` : "—"}
                                            </td>
                                            <td className="px-4 py-3">
                                                <Badge
                                                    data-testid={`status-page-${page.id}`}
                                                    variant="outline"
                                                    className={`text-xs ${page.status === "done" ? "status-done" :
                                                        page.status === "error" ? "status-error" :
                                                            page.status === "running" ? "status-running" : "status-pending"
                                                        }`}
                                                >
                                                    {page.status === "done" ? "Готово" : page.status === "error" ? "Ошибка" : "Ожидание"}
                                                </Badge>
                                            </td>
                                            <td className="px-4 py-3 text-right">
                                                <div className="flex items-center justify-end gap-1">
                                                    <Button
                                                        data-testid={`button-view-page-${page.id}`}
                                                        variant="ghost" size="icon"
                                                        className="w-7 h-7 hover:bg-muted"
                                                        onClick={() => openPagePreview(page)}
                                                    >
                                                        <Eye className="w-3.5 h-3.5" />
                                                    </Button>
                                                    <Button
                                                        data-testid={`button-delete-page-${page.id}`}
                                                        variant="ghost" size="icon"
                                                        className="w-7 h-7 hover:bg-destructive/20 hover:text-destructive"
                                                        onClick={() => handleDeletePage(page.id, page.title)}
                                                    >
                                                        <Trash2 className="w-3.5 h-3.5" />
                                                    </Button>
                                                </div>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </ScrollArea>
                    )}
                </CardContent>
            </Card>

            {/* Page preview dialog */}
            <Dialog open={!!selectedPage} onOpenChange={() => { setSelectedPage(null); setPageContent(null); }}>
                <DialogContent className="bg-card border-border max-w-2xl max-h-[80vh]">
                    <DialogHeader>
                        <DialogTitle className="text-foreground">{selectedPage?.title || "Без заголовка"}</DialogTitle>
                        <a
                            href={selectedPage?.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-xs text-primary hover:underline break-all"
                        >
                            {selectedPage?.url}
                        </a>
                    </DialogHeader>
                    <ScrollArea className="h-96 rounded border border-border p-4 bg-muted">
                        <pre className="text-sm text-foreground whitespace-pre-wrap font-sans">
                            {pageContent === null ? "Загрузка..." : pageContent}
                        </pre>
                    </ScrollArea>
                </DialogContent>
            </Dialog>
        </div>
    );
}
