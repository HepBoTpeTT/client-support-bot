import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/lib/queryClient";
import { formatServerDate } from "@/lib/datetime";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { MessageSquare, User, Bot, Clock, Trash2, Headphones, Info } from "lucide-react";
import { cn } from "@/lib/utils";
import { useToast } from "@/hooks/use-toast";
import { useConfirm } from "@/hooks/use-confirm";

interface SessionSummary {
  sessionId: string;
  lastMessage: string;
  count: number;
  createdAt: string;
}

interface Dialog {
  id: number;
  sessionId: string;
  role: "user" | "assistant" | "operator" | "system";
  eventType: "message" | "handoff_requested" | "handoff_closed" | "handoff_reopened";
  content: string | null;
  createdAt: string;
}

document.title = "История диалогов"

export default function DialogsPage() {
  const [selectedSession, setSelectedSession] = useState<string | null>(null);
  const { toast } = useToast();
  const confirm = useConfirm();
  const qc = useQueryClient();

  const { data: sessions = [], isLoading } = useQuery<SessionSummary[]>({
    queryKey: ["/api/dialogs"],
    refetchInterval: 10000,
  });

  const { data: messages = [] } = useQuery<Dialog[]>({
    queryKey: ["/api/dialogs", selectedSession],
    queryFn: () => apiRequest("GET", `/api/dialogs/${selectedSession}`).then(r => r.json()),
    enabled: !!selectedSession,
  });

  // Delete all sessions
  const deleteAll = useMutation({
    mutationFn: () => apiRequest("DELETE", "/api/dialogs"),
    onSuccess: () => {
      toast({ title: "Все диалоги удалены" });
      setSelectedSession(null);
      qc.invalidateQueries({ queryKey: ["/api/dialogs"] });
    },
  });

  // Delete one session
  const deleteOne = useMutation({
    mutationFn: (sessionId: string) => apiRequest("DELETE", `/api/dialogs/${sessionId}`),
    onSuccess: (_data, sessionId) => {
      toast({ title: "Сессия удалена" });
      if (selectedSession === sessionId) setSelectedSession(null);
      qc.invalidateQueries({ queryKey: ["/api/dialogs"] });
    },
  });

  const handleDeleteAll = async () => {
    const ok = await confirm({
      title: "Удалить все диалоги?",
      description: "Будет удалена вся история разговоров пользователей с AI-помощником.",
      confirmText: "Удалить всё",
      cancelText: "Отмена",
      variant: "destructive",
    });

    if (!ok) return;
    deleteAll.mutate();
  };

  const handleDeleteOne = async (sessionId: string) => {
    const ok = await confirm({
      title: "Удалить диалог?",
      description: `Сессия ${sessionId.slice(0, 20)}... будет удалена без возможности восстановления.`,
      confirmText: "Удалить",
      cancelText: "Отмена",
      variant: "destructive",
    });

    if (!ok) return;
    deleteOne.mutate(sessionId);
  };

  const getSystemEventLabel = (eventType: Dialog["eventType"], role?: Dialog["role"]) => {
    switch (eventType) {
      case "handoff_requested":
        return "Пользователь запросил соединение с оператором";
      case "handoff_closed":
        return "Обращение закрыто";
      case "handoff_reopened":
        return "Обращение повторно открыто";
      case "message":
      default:
        if (role === "system") return "Системное событие";
        return "Сообщение";
    }
  };


  return (
    <div className="p-8 max-w-6xl">
      <div className="mb-8 flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground flex items-center gap-2">
            <MessageSquare className="w-5 h-5 text-primary" />
            История диалогов
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Все разговоры пользователей с AI-помощником
          </p>
        </div>
        {sessions.length > 0 && (
          <Button
            size="sm"
            variant="destructive"
            data-testid="btn-delete-all-dialogs"
            onClick={handleDeleteAll}
            disabled={deleteAll.isPending}
            className="gap-2"
          >
            <Trash2 className="w-3.5 h-3.5" />
            Очистить всё
          </Button>
        )}
      </div>

      <div className="grid grid-cols-5 gap-4 h-[calc(100vh-148px)]">
        {/* Sessions list */}
        <Card className="col-span-2 bg-card border-border flex flex-col overflow-y-auto">
          <CardHeader className="pb-3 border-b border-border flex-shrink-0">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center justify-between">
              Сессии
              <Badge variant="outline" className="text-xs border-border text-muted-foreground">
                {sessions.length}
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0 flex-1 overflow-hidden">
            {isLoading ? (
              <div className="p-4 text-sm text-muted-foreground text-center">Загрузка...</div>
            ) : sessions.length === 0 ? (
              <div className="p-6 text-center">
                <MessageSquare className="w-8 h-8 text-muted-foreground mx-auto mb-2" />
                <p className="text-sm text-muted-foreground">Диалогов пока нет</p>
              </div>
            ) : (
              <ScrollArea className="h-full">
                {sessions.map((s, i) => (
                  <div
                    key={s.sessionId}
                    data-testid={`session-item-${i}`}
                    onClick={() => setSelectedSession(s.sessionId)}
                    className={cn(
                      "p-4 border-b border-border cursor-pointer hover:bg-muted/40 transition-colors group",
                      selectedSession === s.sessionId && "bg-primary/10 border-l-2 border-l-primary"
                    )}
                  >
                    <div className="flex items-center justify-between gap-2 mb-1">
                      <div className="text-xs font-mono text-muted-foreground truncate">
                        {s.sessionId.slice(0, 20)}...
                      </div>
                      <div className="flex items-center gap-1 flex-shrink-0">
                        <Badge variant="outline" className="text-xs border-border text-muted-foreground">
                          {s.count} соо.
                        </Badge>
                        <button
                          data-testid={`btn-delete-session-${i}`}
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteOne(s.sessionId);
                          }}
                          disabled={deleteOne.isPending}
                          title="Удалить сессию"
                          className="w-5 h-5 rounded flex items-center justify-center text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors opacity-0 group-hover:opacity-100"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </div>
                    </div>
                    <div className="text-sm text-foreground truncate">{s.lastMessage}</div>
                    <div className="flex items-center gap-1 mt-1 text-xs text-muted-foreground">
                      <Clock className="w-3 h-3" />
                      {formatServerDate(s.createdAt)}
                    </div>
                  </div>
                ))}
              </ScrollArea>
            )}
          </CardContent>
        </Card>

        {/* Messages */}
        <Card className="col-span-3 bg-card border-border flex flex-col overflow-y-auto">
          <CardHeader className="pb-3 border-b border-border flex-shrink-0">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              {selectedSession ? `Диалог: ${selectedSession}` : "Выберите сессию"}
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0 flex-1 overflow-hidden">
            {!selectedSession ? (
              <div className="h-full flex items-center justify-center">
                <div className="text-center">
                  <MessageSquare className="w-10 h-10 text-muted-foreground mx-auto mb-3" />
                  <p className="text-sm text-muted-foreground">Выберите сессию слева</p>
                </div>
              </div>
            ) : (
              <ScrollArea className="h-full p-4">
                <div className="space-y-3">
                  {messages.map((msg) => {
                    const isSystem = msg.role === "system" || msg.eventType !== "message";
                    const isUser = msg.role === "user" && msg.eventType === "message";
                    const isAssistant = msg.role === "assistant" && msg.eventType === "message";
                    const isOperator = msg.role === "operator" && msg.eventType === "message";

                    if (isSystem) {
                      return (
                        <div key={msg.id} className="flex justify-center">
                          <div className="max-w-[85%] rounded-full border border-border bg-muted/60 px-4 py-2 text-center text-sm text-muted-foreground">
                            <div className="inline-flex items-center gap-2">
                              <Info className="w-4 h-4" />
                              <span>{getSystemEventLabel(msg.eventType)}</span>
                            </div>
                            <div className="mt-1 text-xs text-muted-foreground/80">
                              {formatServerDate(msg.createdAt)}
                            </div>
                          </div>
                        </div>
                      );
                    }

                    return (
                      <div
                        key={msg.id}
                        className={cn(
                          "flex gap-3",
                          isUser ? "justify-end" : "justify-start"
                        )}
                      >
                        {!isUser && (
                          <div
                            className={cn(
                              "w-8 h-8 rounded-full flex items-center justify-center shrink-0 mt-1",
                              isAssistant && "bg-primary/10 text-primary",
                              isOperator && "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
                            )}
                          >
                            {isAssistant ? (
                              <Bot className="w-4 h-4" />
                            ) : (
                              <Headphones className="w-4 h-4" />
                            )}
                          </div>
                        )}

                        <div
                          className={cn(
                            "max-w-[80%] rounded-2xl px-4 py-3 shadow-sm",
                            isUser && "bg-primary text-primary-foreground ml-auto",
                            isAssistant && "bg-muted text-foreground",
                            isOperator && "bg-green-50 text-foreground border border-green-200 dark:bg-green-950/30 dark:border-green-900/40"
                          )}
                        >
                          <div className="flex items-center gap-2 mb-1 text-xs opacity-80">
                            {isUser && <User className="w-3.5 h-3.5" />}
                            {isAssistant && <Bot className="w-3.5 h-3.5" />}
                            {isOperator && <Headphones className="w-3.5 h-3.5" />}
                            <span>
                              {isUser
                                ? "Пользователь"
                                : isAssistant
                                ? "AI-помощник"
                                : "Оператор"}
                            </span>
                          </div>

                          <div className="whitespace-pre-wrap break-words text-sm leading-relaxed">
                            {msg.content ?? ""}
                          </div>

                          <div
                            className={cn(
                              "mt-2 text-[11px]",
                              isUser ? "text-white/80" : "text-muted-foreground"
                            )}
                          >
                            {formatServerDate(msg.createdAt)}
                          </div>
                        </div>

                        {isUser && (
                          <div className="w-8 h-8 rounded-full bg-primary/10 text-primary flex items-center justify-center shrink-0 mt-1">
                            <User className="w-4 h-4" />
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </ScrollArea>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
