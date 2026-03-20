import { useState, useRef, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "@/lib/queryClient";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { X, Send, Bot, User, MessageSquare, Loader2, Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface Message {
  role: "user" | "bot";
  text: string;
  loading?: boolean;
  isError?: boolean;
}

interface SettingsData {
  botName: string;
  welcomeMessage: string;
  accentColor: string;
}

interface TestChatPanelProps {
  open: boolean;
  onClose: () => void;
}

export default function TestChatPanel({ open, onClose }: TestChatPanelProps) {
  const { data: settings, refetch: refetchSettings } = useQuery<SettingsData>({
    queryKey: ["/api/settings"],
    staleTime: 0,
    refetchOnMount: "always",
  });
  const botName = settings?.botName || "Помощник";
  const accentColor = settings?.accentColor || "#01696f";
  const welcomeMessage = settings?.welcomeMessage || "Привет! Чем могу помочь?";

  // Re-fetch settings every time panel opens
  useEffect(() => {
    if (open) refetchSettings();
  }, [open]);

  const sessionId = useRef<string>(`test-${Date.now()}`);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Add welcome message when panel opens
  useEffect(() => {
    if (open && messages.length === 0) {
      setMessages([{ role: "bot", text: welcomeMessage }]);
    }
  }, [open]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");

    setMessages(prev => [...prev, { role: "user", text }]);
    setLoading(true);
    setMessages(prev => [...prev, { role: "bot", text: "", loading: true }]);

    try {
      const res = await apiRequest("POST", "/api/chat", {
        message: text,
        session_id: sessionId.current,
      });
      const data = await res.json();
      setMessages(prev => {
        const copy = [...prev];
        const loadingIdx = copy.findLastIndex(m => m.loading);
        if (loadingIdx !== -1) {
          if (!res.ok) {
            // Show full error detail in admin test chat
            const errText = data.detail || data.error || `HTTP ${res.status}`;
            copy[loadingIdx] = { role: "bot", text: `⚠️ ${errText}`, isError: true };
          } else {
            copy[loadingIdx] = { role: "bot", text: data.reply || data.response || "..." };
          }
        }
        return copy;
      });
    } catch (e: any) {
      setMessages(prev => {
        const copy = [...prev];
        const loadingIdx = copy.findLastIndex(m => m.loading);
        if (loadingIdx !== -1) copy[loadingIdx] = { role: "bot", text: `⚠️ Ошибка соединения: ${e?.message || e}`, isError: true };
        return copy;
      });
    } finally {
      setLoading(false);
    }
  };

  const clearChat = () => {
    sessionId.current = `test-${Date.now()}`;
    setMessages([{ role: "bot", text: welcomeMessage }]);
  };

  return (
    <>
      {/* Backdrop */}
      <div
        className={cn(
          "fixed inset-0 z-40 bg-black/30 transition-opacity duration-300",
          open ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"
        )}
        onClick={onClose}
      />

      {/* Slide-in panel */}
      <div
        className={cn(
          "fixed top-0 right-0 h-full w-96 z-50 flex flex-col shadow-2xl transition-transform duration-300 ease-in-out",
          "bg-card border-l border-border",
          open ? "translate-x-0" : "translate-x-full"
        )}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-4 py-3 text-white flex-shrink-0"
          style={{ background: accentColor }}
        >
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-white/20 flex items-center justify-center">
              <Bot className="w-4 h-4" />
            </div>
            <div>
              <div className="text-sm font-semibold">{botName}</div>
              <div className="text-xs opacity-75">Тестовый режим</div>
            </div>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={clearChat}
              className="w-8 h-8 rounded-lg flex items-center justify-center hover:bg-white/20 transition-colors"
              title="Очистить диалог"
            >
              <Trash2 className="w-4 h-4" />
            </button>
            <button
              onClick={onClose}
              className="w-8 h-8 rounded-lg flex items-center justify-center hover:bg-white/20 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Notice */}
        <div className="px-4 py-2 bg-yellow-50 dark:bg-yellow-900/20 border-b border-yellow-200 dark:border-yellow-800 flex-shrink-0">
          <p className="text-xs text-yellow-700 dark:text-yellow-400">
            Тестовый чат — отвечает на основе реальной базы знаний
          </p>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {messages.map((msg, i) => (
            <div
              key={i}
              className={cn("flex gap-2", msg.role === "user" ? "justify-end" : "justify-start")}
            >
              {msg.role === "bot" && (
                <div
                  className="w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5"
                  style={{ background: accentColor }}
                >
                  <Bot className="w-3.5 h-3.5 text-white" />
                </div>
              )}
              <div
                className={cn(
                  "max-w-[78%] rounded-2xl px-3 py-2 text-sm leading-relaxed",
                  msg.role === "user"
                    ? "text-white rounded-tr-sm"
                    : msg.isError
                      ? "bg-red-50 dark:bg-red-950/30 text-red-700 dark:text-red-400 border border-red-200 dark:border-red-800 rounded-tl-sm font-mono text-xs"
                      : "bg-muted text-foreground rounded-tl-sm"
                )}
                style={msg.role === "user" ? { background: accentColor } : undefined}
              >
                {msg.loading ? (
                  <span className="flex items-center gap-1.5 text-muted-foreground">
                    <Loader2 className="w-3 h-3 animate-spin" />
                    Печатает...
                  </span>
                ) : (
                  msg.text
                )}
              </div>
              {msg.role === "user" && (
                <div className="w-7 h-7 rounded-full bg-muted flex items-center justify-center flex-shrink-0 mt-0.5">
                  <User className="w-3.5 h-3.5 text-muted-foreground" />
                </div>
              )}
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="p-3 border-t border-border flex-shrink-0">
          <div className="flex gap-2">
            <Input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === "Enter" && !e.shiftKey && sendMessage()}
              placeholder="Введите вопрос..."
              disabled={loading}
              className="bg-muted border-border text-foreground placeholder:text-muted-foreground text-sm"
            />
            <Button
              onClick={sendMessage}
              disabled={!input.trim() || loading}
              size="icon"
              className="flex-shrink-0 text-white"
              style={{ background: accentColor }}
            >
              {loading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </Button>
          </div>
        </div>
      </div>
    </>
  );
}
