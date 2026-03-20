import { createContext, useContext, useEffect, useState } from "react";
import { Router, Route, Switch } from "wouter";
import { useHashLocation } from "wouter/use-hash-location";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "@/lib/queryClient";
import { Toaster } from "@/components/ui/toaster";
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

// ── Chat panel context ───────────────────────────────────────
interface ChatPanelCtx {
  openChat: () => void;
}
export const ChatPanelContext = createContext<ChatPanelCtx>({ openChat: () => {} });
export function useChatPanel() { return useContext(ChatPanelContext); }

// ── Theme context ────────────────────────────────────────────
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
    // Default: light. Can be overridden by user preference stored in URL hash
    // (we avoid localStorage per the webapp rules, using in-memory state instead)
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

// ── App ──────────────────────────────────────────────────────
export default function App() {
  const [chatOpen, setChatOpen] = useState(false);

  return (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <ChatPanelContext.Provider value={{ openChat: () => setChatOpen(true) }}>
          <Router hook={useHashLocation}>
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
              <TestChatPanel open={chatOpen} onClose={() => setChatOpen(false)} />
            </div>
          </Router>
        </ChatPanelContext.Provider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
