import { useState, useRef, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "@/lib/queryClient";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { X, Send, Bot, User, Loader2, Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ChatPreviewSettings } from "@/App";

interface Message {
  role: "user" | "bot";
  text: string;
  loading?: boolean;
  isError?: boolean;
}

interface SettingsData {
  botName?: string;
  welcomeMessage?: string;
  accentColor?: string;
  chatBgColor?: string;
  userBubbleBg?: string;
  userTextColor?: string;
  botBubbleBg?: string;
  botTextColor?: string;
  crawlerSettings?: string;
}

interface TestChatPanelProps {
  open: boolean;
  onClose: () => void;
  previewSettings?: ChatPreviewSettings | null;
}

export default function TestChatPanel({
  open,
  onClose,
  previewSettings,
}: TestChatPanelProps) {
  const { data: settings, refetch: refetchSettings } = useQuery<SettingsData>({
    queryKey: ["/api/settings"],
    staleTime: 0,
    refetchOnMount: "always",
  });

  const botName =
    previewSettings?.botName || settings?.botName || "Помощник";
  const accentColor =
    previewSettings?.accentColor || settings?.accentColor || "#01696f";
  const welcomeMessage =
    previewSettings?.welcomeMessage || settings?.welcomeMessage || "Привет! Чем могу помочь?";
  const chatBgColor =
    previewSettings?.chatBgColor || settings?.chatBgColor || "#f8f9fb";
  const userBubbleBg =
    previewSettings?.userBubbleBg || settings?.userBubbleBg || "#01696f";
  const userTextColor =
    previewSettings?.userTextColor || settings?.userTextColor || "#ffffff";
  const botBubbleBg =
    previewSettings?.botBubbleBg || settings?.botBubbleBg || "#ffffff";
  const botTextColor =
    previewSettings?.botTextColor || settings?.botTextColor || "#222222";

  useEffect(() => {
    if (open) {
      refetchSettings();
    }
  }, [open, refetchSettings]);

  const sessionId = useRef(`test-${Date.now()}`);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (open) {
      setMessages([{ role: "bot", text: welcomeMessage }]);
      setInput("");
      setLoading(false);
      sessionId.current = `test-${Date.now()}`;
    }
  }, [open, welcomeMessage]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading) return;

    setInput("");
    setMessages((prev) => [...prev, { role: "user", text }]);
    setLoading(true);
    setMessages((prev) => [...prev, { role: "bot", text: "", loading: true }]);

    try {
      const res = await apiRequest("POST", "/api/chat", {
        message: text,
        session_id: sessionId.current,
      });

      const data = await res.json();

      setMessages((prev) => {
        const copy = [...prev];
        const loadingIdx = copy.findLastIndex((m) => m.loading);

        if (loadingIdx !== -1) {
          if (!res.ok) {
            const errText = data.detail || data.error || `HTTP ${res.status}`;
            copy[loadingIdx] = {
              role: "bot",
              text: `⚠️ ${errText}`,
              isError: true,
            };
          } else {
            copy[loadingIdx] = {
              role: "bot",
              text: data.reply || data.response || "...",
            };
          }
        }

        return copy;
      });
    } catch (e: any) {
      setMessages((prev) => {
        const copy = [...prev];
        const loadingIdx = copy.findLastIndex((m) => m.loading);

        if (loadingIdx !== -1) {
          copy[loadingIdx] = {
            role: "bot",
            text: `⚠️ Ошибка соединения: ${e?.message || e}`,
            isError: true,
          };
        }

        return copy;
      });
    } finally {
      setLoading(false);
    }
  };

  const clearChat = () => {
    sessionId.current = `test-${Date.now()}`;
    setMessages([{ role: "bot", text: welcomeMessage }]);
    setInput("");
  };

  return (
    <>
      <div
        className={cn(
          "fixed inset-0 z-40 bg-black/30 transition-opacity duration-300",
          open ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"
        )}
        onClick={onClose}
      />

      <div
        className={cn(
          "fixed top-0 right-0 z-50 flex h-full w-96 flex-col bg-card shadow-2xl transition-transform duration-300 ease-in-out",
          open ? "translate-x-0" : "translate-x-full"
        )}
      >
        <div
          className="flex items-center justify-between px-4 py-3 text-white"
          style={{ background: accentColor }}
        >
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-white/20">
              <Bot className="h-4 w-4" />
            </div>
            <div>
              <div className="text-sm font-semibold">{botName}</div>
              <div className="text-xs opacity-75">Тестовый режим</div>
            </div>
          </div>

          <div className="flex items-center gap-1">
            <button
              onClick={clearChat}
              className="flex h-8 w-8 items-center justify-center rounded-lg transition-colors hover:bg-white/20"
              title="Очистить чат"
              type="button"
            >
              <Trash2 className="h-4 w-4" />
            </button>

            <button
              onClick={onClose}
              className="flex h-8 w-8 items-center justify-center rounded-lg transition-colors hover:bg-white/20"
              title="Закрыть"
              type="button"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        <div
          className="flex-1 overflow-y-auto p-4 space-y-3"
          style={{ backgroundColor: chatBgColor }}
        >
          {messages.map((msg, i) => {
            const isUser = msg.role === "user";
            const isBot = msg.role === "bot" && !msg.isError;

            return (
              <div
                key={i}
                className={cn(
                  "flex gap-2",
                  isUser ? "justify-end" : "justify-start"
                )}
              >
                {msg.role === "bot" && (
                  <div
                    className="mt-0.5 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full"
                    style={{ background: accentColor }}
                  >
                    <Bot className="h-3.5 w-3.5 text-white" />
                  </div>
                )}

                <div
                  className={cn(
                    "max-w-[78%] rounded-2xl px-3 py-2 text-sm leading-relaxed break-words",
                    isUser && "rounded-tr-sm",
                    isBot && "rounded-tl-sm",
                    msg.isError &&
                      "rounded-tl-sm border border-red-200 bg-red-50 font-mono text-xs text-red-700 dark:border-red-800 dark:bg-red-950/30 dark:text-red-400"
                  )}
                  style={
                    isUser
                      ? {
                          background: userBubbleBg,
                          color: userTextColor,
                        }
                      : isBot
                        ? {
                            background: botBubbleBg,
                            color: botTextColor,
                          }
                        : undefined
                  }
                >
                  {msg.loading ? (
                    <span
                      className="flex items-center gap-1.5"
                      style={{ color: botTextColor }}
                    >
                      <Loader2 className="h-3 w-3 animate-spin" />
                      Печатает...
                    </span>
                  ) : (
                    msg.text
                  )}
                </div>

                {msg.role === "user" && (
                  <div
                    className="mt-0.5 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full border"
                    style={{
                      background: userBubbleBg,
                      borderColor: userBubbleBg,
                    }}
                  >
                    <User
                      className="h-3.5 w-3.5"
                      style={{ color: userTextColor }}
                    />
                  </div>
                )}
              </div>
            );
          })}

          <div ref={bottomRef} />
        </div>

        <div className="border-t border-border p-3">
          <div className="flex gap-2">
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  sendMessage();
                }
              }}
              placeholder="Введите вопрос..."
              disabled={loading}
              className="border-border bg-muted text-sm text-foreground placeholder:text-muted-foreground"
            />

            <Button
              onClick={sendMessage}
              disabled={!input.trim() || loading}
              size="icon"
              className="flex-shrink-0 text-white"
              style={{ background: accentColor }}
            >
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </Button>
          </div>
        </div>
      </div>
    </>
  );
}