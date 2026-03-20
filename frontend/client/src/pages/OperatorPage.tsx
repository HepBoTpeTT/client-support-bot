import { useState, useRef, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/lib/queryClient";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  Headphones, Clock, Send, CheckCircle2, XCircle, User, Bot,
  RefreshCw,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useToast } from "@/hooks/use-toast";

interface OperatorSession {
  id: number;
  sessionId: string;
  status: "pending" | "active" | "closed";
  createdAt: string;
  updatedAt: string;
  lastMessage: string;
  lastMessageRole: string;
  userMessageCount: number;
}

interface OperatorMessage {
  id: number;
  sessionId: string;
  role: "user" | "operator";
  content: string;
  createdAt: string;
}

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  pending: { label: "Ожидает", color: "bg-yellow-100 text-yellow-700 border-yellow-200 dark:bg-yellow-900/40 dark:text-yellow-400 dark:border-yellow-800/60" },
  active:  { label: "Активен",  color: "bg-green-100 text-green-700 border-green-200 dark:bg-green-900/40 dark:text-green-400 dark:border-green-800/60" },
  closed:  { label: "Закрыт",  color: "bg-muted text-muted-foreground border-border" },
};

export default function OperatorPage() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const qc = useQueryClient();
  const { toast } = useToast();
  const bottomRef = useRef<HTMLDivElement>(null);

  const { data: sessions = [], isLoading } = useQuery<OperatorSession[]>({
    queryKey: ["/api/operator/sessions"],
    refetchInterval: 5000,
  });

  const { data: messages = [] } = useQuery<OperatorMessage[]>({
    queryKey: ["/api/operator/messages", selectedId],
    queryFn: () =>
      selectedId
        ? apiRequest("GET", `/api/operator/messages/${selectedId}`).then((r) => r.json())
        : Promise.resolve([]),
    enabled: !!selectedId,
    refetchInterval: 3000,
  });

  const sendMutation = useMutation({
    mutationFn: (msg: string) =>
      apiRequest("POST", "/api/operator/send", {
        session_id: selectedId,
        message: msg,
      }),
    onSuccess: () => {
      setDraft("");
      qc.invalidateQueries({ queryKey: ["/api/operator/messages", selectedId] });
      qc.invalidateQueries({ queryKey: ["/api/operator/sessions"] });
    },
    onError: () => toast({ title: "Ошибка", description: "Не удалось отправить сообщение", variant: "destructive" }),
  });

  const closeMutation = useMutation({
    mutationFn: (sid: string) =>
      apiRequest("PATCH", `/api/operator/sessions/${sid}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["/api/operator/sessions"] });
      qc.invalidateQueries({ queryKey: ["/api/operator/messages", selectedId] });
      toast({ title: "Готово", description: "Статус сессии изменён" });
    },
  });

  // Auto-scroll to bottom when messages load
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const formatDate = (d: string) => {
    try {
      return new Date(d).toLocaleString("ru-RU", {
        day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
      });
    } catch { return d; }
  };

  const selectedSession = sessions.find((s) => s.sessionId === selectedId);
  const pendingCount = sessions.filter((s) => s.status === "pending").length;

  const handleSend = () => {
    const text = draft.trim();
    if (!text || !selectedId) return;
    sendMutation.mutate(text);
  };

  return (
    <div className="p-8 max-w-6xl">
      {/* Header */}
      <div className="mb-8 flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground flex items-center gap-2">
            <Headphones className="w-5 h-5 text-primary" />
            Операторы
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Обращения пользователей к живому оператору
          </p>
        </div>
        {pendingCount > 0 && (
          <Badge className="bg-yellow-100 text-yellow-700 border border-yellow-200 dark:bg-yellow-900/40 dark:text-yellow-400 dark:border-yellow-800/60 text-sm px-3 py-1">
            {pendingCount} новых
          </Badge>
        )}
      </div>

      <div className="grid grid-cols-5 gap-4 h-[calc(100vh-210px)]">
        {/* Sessions list */}
        <Card className="col-span-2 bg-card border-border flex flex-col">
          <CardHeader className="pb-3 border-b border-border flex-shrink-0">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center justify-between">
              Обращения
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="text-xs border-border text-muted-foreground">
                  {sessions.length}
                </Badge>
                <button
                  onClick={() => qc.invalidateQueries({ queryKey: ["/api/operator/sessions"] })}
                  className="text-muted-foreground hover:text-foreground transition-colors"
                  data-testid="btn-refresh-sessions"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                </button>
              </div>
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0 flex-1 overflow-hidden">
            {isLoading ? (
              <div className="p-4 text-sm text-muted-foreground text-center">Загрузка...</div>
            ) : sessions.length === 0 ? (
              <div className="p-6 text-center">
                <Headphones className="w-8 h-8 text-muted-foreground mx-auto mb-2" />
                <p className="text-sm text-muted-foreground">Обращений пока нет</p>
                <p className="text-xs text-muted-foreground mt-1">
                  Когда пользователь нажмёт «Связаться с оператором» в виджете — обращение появится здесь
                </p>
              </div>
            ) : (
              <ScrollArea className="h-full">
                {sessions.map((s, i) => {
                  const st = STATUS_LABELS[s.status] ?? STATUS_LABELS.closed;
                  return (
                    <div
                      key={s.sessionId}
                      data-testid={`op-session-${i}`}
                      onClick={() => setSelectedId(s.sessionId)}
                      className={cn(
                        "p-4 border-b border-border cursor-pointer hover:bg-muted/40 transition-colors",
                        selectedId === s.sessionId && "bg-primary/10 border-l-2 border-l-primary"
                      )}
                    >
                      <div className="flex items-center justify-between gap-2 mb-1">
                        <div className="text-xs font-mono text-muted-foreground truncate">
                          {s.sessionId.slice(0, 18)}…
                        </div>
                        <span className={cn("text-xs border rounded px-1.5 py-0.5 font-medium", st.color)}>
                          {st.label}
                        </span>
                      </div>
                      <div className="text-sm text-foreground truncate">{s.lastMessage || "—"}</div>
                      <div className="flex items-center gap-1 mt-1 text-xs text-muted-foreground">
                        <Clock className="w-3 h-3" />
                        {formatDate(s.updatedAt)}
                      </div>
                    </div>
                  );
                })}
              </ScrollArea>
            )}
          </CardContent>
        </Card>

        {/* Chat panel */}
        <Card className="col-span-3 bg-card border-border flex flex-col">
          {/* Chat header */}
          <CardHeader className="pb-3 border-b border-border flex-shrink-0">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {selectedSession
                  ? `Сессия: ${selectedId!.slice(0, 22)}…`
                  : "Выберите обращение"}
              </CardTitle>
              {selectedSession && (
                <Button
                  size="sm"
                  variant="outline"
                  data-testid="btn-toggle-session"
                  onClick={() => closeMutation.mutate(selectedId!)}
                  disabled={closeMutation.isPending}
                  className={cn(
                    "text-xs h-7 px-2 gap-1",
                    selectedSession.status === "closed"
                      ? "border-green-400 text-green-600 hover:bg-green-50 dark:hover:bg-green-900/20"
                      : "border-red-300 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20"
                  )}
                >
                  {selectedSession.status === "closed" ? (
                    <><CheckCircle2 className="w-3.5 h-3.5" /> Открыть</>
                  ) : (
                    <><XCircle className="w-3.5 h-3.5" /> Закрыть</>
                  )}
                </Button>
              )}
            </div>
          </CardHeader>

          {/* Messages */}
          <CardContent className="p-0 flex-1 overflow-hidden flex flex-col">
            {!selectedId ? (
              <div className="flex-1 flex items-center justify-center">
                <div className="text-center">
                  <Headphones className="w-10 h-10 text-muted-foreground mx-auto mb-3" />
                  <p className="text-sm text-muted-foreground">Выберите обращение слева</p>
                </div>
              </div>
            ) : (
              <>
                <ScrollArea className="flex-1 p-4">
                  <div className="flex flex-col gap-3">
                    {messages.map((msg, idx) => (
                      <div
                        key={msg.id}
                        data-testid={`op-msg-${idx}`}
                        className={cn(
                          "flex gap-2.5 max-w-[85%]",
                          msg.role === "operator" ? "ml-auto flex-row-reverse" : ""
                        )}
                      >
                        <div
                          className={cn(
                            "w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0",
                            msg.role === "operator" ? "bg-primary/20" : "bg-muted"
                          )}
                        >
                          {msg.role === "operator"
                            ? <Headphones className="w-3.5 h-3.5 text-primary" />
                            : <User className="w-3.5 h-3.5 text-muted-foreground" />}
                        </div>
                        <div>
                          <div
                            className={cn(
                              "rounded-xl px-3.5 py-2.5 text-sm",
                              msg.role === "operator"
                                ? "bg-primary/15 text-foreground"
                                : "bg-muted text-foreground"
                            )}
                          >
                            {msg.content}
                          </div>
                          <div
                            className={cn(
                              "text-xs text-muted-foreground mt-1",
                              msg.role === "operator" ? "text-right" : "text-left"
                            )}
                          >
                            {msg.role === "operator" ? "Оператор" : "Пользователь"} · {formatDate(msg.createdAt)}
                          </div>
                        </div>
                      </div>
                    ))}
                    <div ref={bottomRef} />
                  </div>
                </ScrollArea>

                {/* Reply input */}
                {selectedSession?.status !== "closed" && (
                  <div className="p-3 border-t border-border flex gap-2 flex-shrink-0">
                    <Textarea
                      data-testid="input-operator-reply"
                      value={draft}
                      onChange={(e) => setDraft(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && !e.shiftKey) {
                          e.preventDefault();
                          handleSend();
                        }
                      }}
                      placeholder="Ответ пользователю... (Enter — отправить)"
                      className="resize-none min-h-[38px] max-h-[100px] text-sm"
                      rows={1}
                    />
                    <Button
                      data-testid="btn-send-operator"
                      onClick={handleSend}
                      disabled={!draft.trim() || sendMutation.isPending}
                      size="sm"
                      className="h-auto px-3 self-end"
                    >
                      <Send className="w-4 h-4" />
                    </Button>
                  </div>
                )}
                {selectedSession?.status === "closed" && (
                  <div className="p-3 border-t border-border text-center text-xs text-muted-foreground">
                    Сессия закрыта. Нажмите «Открыть» для возобновления.
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
