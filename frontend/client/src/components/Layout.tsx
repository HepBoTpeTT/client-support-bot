import { Link } from "wouter";
import { useHashLocation } from "wouter/use-hash-location";
import {
  Globe, Table2, MessageSquare, Settings, Code2, Bot, ChevronRight,
  Headphones, Sun, Moon, Trophy, MessageCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useTheme, useChatPanel } from "@/App";
import { useQuery } from "@tanstack/react-query";

const navItems = [
  { href: "/", icon: Globe, label: "Парсинг сайта" },
  { href: "/pages", icon: Table2, label: "База знаний" },
  { href: "/dialogs", icon: MessageSquare, label: "История диалогов" },
  { href: "/operator", icon: Headphones, label: "Обращения", operatorBadge: true },
  { href: "/achievements", icon: Trophy, label: "Достижения", badge: true },
  { href: "/settings", icon: Settings, label: "Настройки виджета" },
  { href: "/embed", icon: Code2, label: "Код встраивания" },
];

export default function Layout({ children }: { children: React.ReactNode }) {
  const [location] = useHashLocation();
  const { theme, toggle } = useTheme();
  const { openChat } = useChatPanel();

  // Poll for new achievements badge
  const { data: gamification } = useQuery<any>({
    queryKey: ["/api/gamification"],
    refetchInterval: 15000,
  });
  const newAchievements = gamification?.stats?.newCount ?? 0;
  const pendingOperators = gamification?.stats?.pendingOperators ?? 0;

  return (
    <div className="flex min-h-screen bg-background">
      {/* Sidebar */}
      <aside className="w-64 flex-shrink-0 bg-sidebar-background border-r border-sidebar-border flex flex-col">
        {/* Logo + theme toggle */}
        <div className="p-5 border-b border-sidebar-border flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-primary flex items-center justify-center">
              <Bot className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="text-sm font-semibold text-foreground">Сапортус</div>
              <div className="text-xs text-muted-foreground">AI-помощник</div>
            </div>
          </div>
          {/* Theme toggle button */}
          <button
            data-testid="btn-theme-toggle"
            onClick={toggle}
            aria-label={theme === "dark" ? "Включить светлую тему" : "Включить тёмную тему"}
            className="w-8 h-8 rounded-lg flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-sidebar-accent transition-colors"
          >
            {theme === "dark" ? (
              <Sun className="w-4 h-4" />
            ) : (
              <Moon className="w-4 h-4" />
            )}
          </button>
        </div>

        {/* Test chat button */}
        <div className="px-3 pt-3">
          <button
            data-testid="btn-test-chat"
            onClick={openChat}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm bg-primary/10 text-primary hover:bg-primary/20 transition-colors font-medium"
          >
            <MessageCircle className="w-4 h-4 flex-shrink-0" />
            Тест чата
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-3 space-y-1">
          {navItems.map((item) => {
            const { href, icon: Icon, label } = item;
            const active = location === href;
            return (
              <Link key={href} href={href}>
                <div
                  data-testid={`nav-${href.replace("/", "") || "home"}`}
                  className={cn(
                    "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm cursor-pointer transition-colors",
                    active
                      ? "bg-primary/15 text-primary font-medium"
                      : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
                  )}
                >
                  <Icon className="w-4 h-4 flex-shrink-0" />
                  <span className="flex-1">{label}</span>
                  {(item as any).badge && newAchievements > 0 && !active && (
                    <span className="w-5 h-5 rounded-full bg-yellow-400 text-yellow-900 text-xs font-bold flex items-center justify-center flex-shrink-0">
                      {newAchievements}
                    </span>
                  )}
                  {(item as any).operatorBadge && pendingOperators > 0 && !active && (
                    <span className="w-5 h-5 rounded-full bg-red-500 text-white text-xs font-bold flex items-center justify-center flex-shrink-0">
                      {pendingOperators}
                    </span>
                  )}
                  {active && <ChevronRight className="w-3 h-3 ml-auto opacity-60 flex-shrink-0" />}
                </div>
              </Link>
            );
          })}
        </nav>


      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        {children}
      </main>
    </div>
  );
}
