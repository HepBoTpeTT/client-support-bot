import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/lib/queryClient";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { MessageSquare, User, Bot, Clock, Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { useToast } from "@/hooks/use-toast";

interface SessionSummary {
  sessionId: string;
  lastMessage: string;
  count: number;
  createdAt: string;
}

interface Dialog {
  id: number;
  sessionId: string;
  role: string;
  content: string;
  createdAt: string;
}

export default function DialogsPage() {
  const [selectedSession, setSelectedSession] = useState<string | null>(null);
  const { toast } = useToast();
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

  const formatDate = (d: string) => {
    try {
      return new Date(d).toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
    } catch { return d; }
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
            onClick={() => deleteAll.mutate()}
            disabled={deleteAll.isPending}
            className="gap-2"
          >
            <Trash2 className="w-3.5 h-3.5" />
            Очистить всё
          </Button>
        )}
      </div>

      <div className="grid grid-cols-5 gap-4 h-[calc(100vh-200px)]">
        {/* Sessions list */}
        <Card className="col-span-2 bg-card border-border flex flex-col">
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
                    <div className="flex items-start justify-between gap-2 mb-1">
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
                            deleteOne.mutate(s.sessionId);
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
                      {formatDate(s.createdAt)}
                    </div>
                  </div>
                ))}
              </ScrollArea>
            )}
          </CardContent>
        </Card>

        {/* Messages */}
        <Card className="col-span-3 bg-card border-border flex flex-col">
          <CardHeader className="pb-3 border-b border-border flex-shrink-0">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              {selectedSession ? `Диалог: ${selectedSession.slice(0, 24)}...` : "Выберите сессию"}
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
                <div className="flex flex-col gap-3">
                  {messages.map((msg, idx) => (
                    <div
                      key={msg.id}
                      data-testid={`msg-${idx}`}
                      className={cn("flex gap-3 max-w-[85%]", msg.role === "user" ? "ml-auto flex-row-reverse" : "")}
                    >
                      <div className={cn(
                        "w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0",
                        msg.role === "user" ? "bg-primary/20" : "bg-muted"
                      )}>
                        {msg.role === "user"
                          ? <User className="w-3.5 h-3.5 text-primary" />
                          : <Bot className="w-3.5 h-3.5 text-muted-foreground" />}
                      </div>
                      <div>
                        <div className={cn(
                          "rounded-xl px-3.5 py-2.5 text-sm",
                          msg.role === "user"
                            ? "bg-primary/20 text-primary-foreground"
                            : "bg-muted text-foreground"
                        )}>
                          {msg.content}
                        </div>
                        <div className={cn(
                          "text-xs text-muted-foreground mt-1",
                          msg.role === "user" ? "text-right" : "text-left"
                        )}>
                          {formatDate(msg.createdAt)}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
