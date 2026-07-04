import { createContext, useContext, useEffect, useState } from "react";
import { Route, Switch } from "wouter";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "@/lib/queryClient";
import { Toaster } from "@/components/ui/toaster";
import { ConfirmProvider } from "@/hooks/use-confirm";
import Layout from "@/components/Layout";
import TestChatPanel from "@/components/TestChatPanel";
import CrawlerPage from "@/pages/CrawlerPage";
import PagesPage from "@/pages/PagesPage";
import DialogsPage from "@/pages/DialogsPage";
import OperatorPage from "@/pages/OperatorPage";
import AchievementsPage from "@/pages/AchievementsPage";
import SettingsPage from "@/pages/SettingsPage";
import EmbedPage from "@/pages/EmbedPage";
import NotFound from "@/pages/not-found";

export interface ChatPreviewSettings {
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

interface ChatPanelCtx {
  openChat: (settings?: ChatPreviewSettings) => void;
}

export const ChatPanelContext = createContext<ChatPanelCtx>({
  openChat: () => {},
});

export function useChatPanel() {
  return useContext(ChatPanelContext);
}

type Theme = "light" | "dark";

interface ThemeCtx {
  theme: Theme;
  toggle: () => void;
}

export const ThemeContext = createContext<ThemeCtx>({
  theme: "light",
  toggle: () => {},
});

export function useTheme() {
  return useContext(ThemeContext);
}

function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<Theme>(() => {
    return "light";
  });

  useEffect(() => {
    const root = document.documentElement;
    if (theme === "dark") {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }
  }, [theme]);

  const toggle = () => setTheme((t) => (t === "light" ? "dark" : "light"));

  return (
    <ThemeContext.Provider value={{ theme, toggle }}>
      {children}
    </ThemeContext.Provider>
  );
}

export default function App() {
  const [chatOpen, setChatOpen] = useState(false);
  const [previewSettings, setPreviewSettings] = useState<ChatPreviewSettings | null>(null);

  const openChat = (settings?: ChatPreviewSettings) => {
    setPreviewSettings(settings ?? null);
    setChatOpen(true);
  };

  const closeChat = () => {
    setChatOpen(false);
  };

  return (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <ChatPanelContext.Provider value={{ openChat }}>
          <ConfirmProvider>
            <div className="min-h-screen bg-background text-foreground">
              <Layout>
                <Switch>
                  <Route path="/" component={CrawlerPage} />
                  <Route path="/pages" component={PagesPage} />
                  <Route path="/dialogs" component={DialogsPage} />
                  <Route path="/operator" component={OperatorPage} />
                  <Route path="/achievements" component={AchievementsPage} />
                  <Route path="/settings" component={SettingsPage} />
                  <Route path="/embed" component={EmbedPage} />
                  <Route component={NotFound} />
                </Switch>
              </Layout>

              <Toaster />

              <TestChatPanel
                open={chatOpen}
                onClose={closeChat}
                previewSettings={previewSettings}
              />
            </div>
          </ConfirmProvider>
        </ChatPanelContext.Provider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}