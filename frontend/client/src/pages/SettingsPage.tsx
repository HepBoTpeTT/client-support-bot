import { useState, useEffect, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/lib/queryClient";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import { Settings, Eye, EyeOff, Save, Bot, Palette, Key, Globe, Play } from "lucide-react";
import { useChatPanel } from "@/App";

interface SettingsData {
  id: number;
  openaiKey: string;
  botName: string;
  welcomeMessage: string;
  accentColor: string;
  language: string;
  targetUrl: string;
  model: string;
  chatBgColor: string;
  textColor: string;
  crawlerSettings: string;
}

export default function SettingsPage() {
  const { toast } = useToast();
  const qc = useQueryClient();
  const { openChat } = useChatPanel();
  const [showKey, setShowKey] = useState(false);
  const [form, setForm] = useState<Partial<SettingsData>>({});

  const { data: settings, isLoading } = useQuery<SettingsData>({
    queryKey: ["/api/settings"],
  });
  const [tags, setTags] = useState<string[]>([]);
  const [inputValue, setInputValue] = useState("");

  useEffect(() => {
    if (settings) setForm(settings);
    if (settings?.crawlerSettings) {
      setTags(settings.crawlerSettings.split(" ").filter(Boolean));
    }
  }, [settings]);

  const update = useMutation({
    mutationFn: (data: Partial<SettingsData>) => apiRequest("PATCH", "/api/settings", data),
    onSuccess: () => {
      toast({ title: "Настройки сохранены" });
      qc.invalidateQueries({ queryKey: ["/api/settings"] });
      setInputValue("");
    },
    onError: (e: any) => {
      toast({ title: "Ошибка сохранения", description: e.message, variant: "destructive" });
    },
  });

  const set = (key: keyof SettingsData, value: string) => {
    setForm(f => ({ ...f, [key]: value }));
  };


  function getTagClass(tag: string) {
    if (tag.startsWith('.')) return 'bg-primary/20 text-primary border-primary/30';                              //class-item class
    if (tag.startsWith('#')) return 'bg-[rgba(255,232,0,0.2)] border-[rgba(177,156,0,0.3)] text-yellow-700'; //id-item class
    return 'bg-[rgba(0,48,182,0.2)] text-[hsl(216.7,85.9%,41.8%)] border-blue-800/50';                       //tag-item class
  }

  function handleTagDelete(index: number) {
    const newTags = tags.filter((_, i) => i !== index);
    setTags(newTags);
    const value = newTags.join(" ");
    set("crawlerSettings", value);
  }


  if (isLoading) return <div className="p-8 text-muted-foreground">Загрузка...</div>;

  return (
    <div className="p-8 max-w-2xl">
      <div className="mb-8">
        <h1 className="text-xl font-semibold text-foreground flex items-center gap-2">
          <Settings className="w-5 h-5 text-primary" />
          Настройки виджета
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Конфигурация AI-помощника и параметры отображения
        </p>
      </div>

      <div className="space-y-5">
        {/* OpenAI */}
        <Card className="bg-card border-border">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <Key className="w-4 h-4 text-primary" />
              OpenAI API
            </CardTitle>
            <CardDescription>Ключ для доступа к OpenAI API</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div>
              <Label className="text-xs text-muted-foreground mb-1.5 block">API Ключ</Label>
              <div className="relative">
                <Input
                  data-testid="input-api-key"
                  type={showKey ? "text" : "password"}
                  value={form.openaiKey || ""}
                  onChange={e => set("openaiKey", e.target.value)}
                  placeholder="sk-..."
                  className="bg-muted border-border text-foreground pr-10 placeholder:text-muted-foreground"
                />
                <button
                  type="button"
                  onClick={() => setShowKey(!showKey)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>
            <div>
              <Label className="text-xs text-muted-foreground mb-1.5 block">Модель</Label>
              <Select value={form.model || "gpt-4o"} onValueChange={v => set("model", v)}>
                <SelectTrigger data-testid="select-model" className="bg-muted border-border text-foreground">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-card border-border">
                  <SelectItem value="gpt-4o">GPT-4o (рекомендуется)</SelectItem>
                  <SelectItem value="gpt-4o-mini">GPT-4o Mini (быстрее, дешевле)</SelectItem>
                  <SelectItem value="gpt-4-turbo">GPT-4 Turbo</SelectItem>
                  <SelectItem value="gpt-3.5-turbo">GPT-3.5 Turbo</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>

        {/* Bot identity */}
        <Card className="bg-card border-border">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <Bot className="w-4 h-4 text-primary" />
              Личность бота
            </CardTitle>
            <CardDescription>Как бот представляется пользователям</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div>
              <Label className="text-xs text-muted-foreground mb-1.5 block">Имя бота</Label>
              <Input
                data-testid="input-bot-name"
                value={form.botName || ""}
                onChange={e => set("botName", e.target.value)}
                placeholder="Помощник"
                className="bg-muted border-border text-foreground placeholder:text-muted-foreground"
              />
            </div>
            <div>
              <Label className="text-xs text-muted-foreground mb-1.5 block">Приветственное сообщение</Label>
              <Input
                data-testid="input-welcome"
                value={form.welcomeMessage || ""}
                onChange={e => set("welcomeMessage", e.target.value)}
                placeholder="Привет! Чем могу помочь?"
                className="bg-muted border-border text-foreground placeholder:text-muted-foreground"
              />
            </div>
            <div>
              <Label className="text-xs text-muted-foreground mb-1.5 block">Язык ответов</Label>
              <Select value={form.language || "ru"} onValueChange={v => set("language", v)}>
                <SelectTrigger data-testid="select-language" className="bg-muted border-border text-foreground">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-card border-border">
                  <SelectItem value="ru">Русский</SelectItem>
                  <SelectItem value="en">English</SelectItem>
                  <SelectItem value="uk">Українська</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle className="text-base">Настройки парсинга</CardTitle>
            <CardDescription>
              Укажите <code className="bg-[rgba(0,48,182,0.2)] text-[hsl(216.7,85.9%,41.8%)] border-blue-800/50 border rounded-md p-1">теги</code>
              , <code className="bg-primary/20 text-primary border-primary/30 border rounded-md p-1">.классы</code>
              , <code className="bg-[rgba(255,232,0,0.2)] border-[rgba(177,156,0,0.3)] text-yellow-700 border rounded-md p-1">#id</code>
              , которые следует игнорировать
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="min-h-[26px] mb-3">
              {/* Теги */}
              {tags.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {tags.map((tag, i) => (
                  <div key={i} className={`flex border items-center gap-1 p-1 cursor-pointer rounded-md text-xs font-mono
                    ${getTagClass(tag)}`}
                  >
                    <span>{tag}</span>
                    <button type="button" onClick={() => handleTagDelete(i)}
                      className="ml-1 opacity-60 hover:opacity-100">×</button>
                  </div>
                ))}
              </div>
            )}
            </div>
            <Input
              type="text"
              value={inputValue}
              onChange={e => {
                setInputValue(e.target.value);
                const newFromInput = e.target.value.split(" ").filter(Boolean);
                set("crawlerSettings", [...tags, ...newFromInput].join(" "));
              }}
              placeholder="Укажите элементы, которые следует исключить из парсинга"
              className="bg-muted border-border text-foreground placeholder:text-muted-foreground"
            />
          </CardContent>
        </Card>

        {/* Appearance */}
        <Card className="bg-card border-border">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <Palette className="w-4 h-4 text-primary" />
              Внешний вид
            </CardTitle>
            <CardDescription>Цвет виджета на сайте</CardDescription>
          </CardHeader>
          <CardContent>
            <div>
              <Label className="text-xs text-muted-foreground mb-1.5 block">Основной цвет</Label>
              <div className="flex items-center gap-3">
                <input
                  data-testid="input-accent-color"
                  type="color"
                  value={form.accentColor || "#01696f"}
                  onChange={e => set("accentColor", e.target.value)}
                  className="w-10 h-10 rounded cursor-pointer border border-border bg-transparent"
                />
                <Input
                  value={form.accentColor || "#01696f"}
                  onChange={e => set("accentColor", e.target.value)}
                  placeholder="#01696f"
                  className="w-36 bg-muted border-border text-foreground"
                />
                <Button
                  onClick={openChat}
                  className="bg-primary hover:bg-primary/90 gap-2"
                  style={{ background: form.accentColor || "#01696f" }}
                  title="Открыть тестовый чат"
                >
                  <Play className="w-3.5 h-3.5" />
                  Предпросмотр
                </Button>
              </div>
            </div>
            <div className="mt-3">
              <Label className="text-xs text-muted-foreground mb-1.5 block">Фон диалогового окна</Label>
              <div className="flex items-center gap-3">
                <input
                  data-testid="input-chat-bg-color"
                  type="color"
                  value={form.chatBgColor || "#f8f9fb"}
                  onChange={e => set("chatBgColor", e.target.value)}
                  className="w-10 h-10 rounded cursor-pointer border border-border bg-transparent"
                />
                <Input
                  value={form.chatBgColor || "#f8f9fb"}
                  onChange={e => set("chatBgColor", e.target.value)}
                  placeholder="#f8f9fb"
                  className="w-36 bg-muted border-border text-foreground"
                />
                <span className="text-xs text-muted-foreground">Фон зоны сообщений</span>
              </div>
              <div className="mt-3">
                <Label className="text-xs text-muted-foreground mb-1.5 block">Цвет текста сообщений</Label>
                <div className="flex items-center gap-3">
                  <input
                    type="color"
                    value={form.textColor || "#222222"}
                    onChange={e => set("textColor", e.target.value)}
                    className="w-10 h-10 rounded cursor-pointer border border-border bg-transparent"
                  />
                  <Input
                    value={form.textColor || "#222222"}
                    onChange={e => set("textColor", e.target.value)}
                    placeholder="#222222"
                    className="w-36 bg-muted border-border text-foreground"
                  />
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Save button */}
        <Button
          data-testid="button-save-settings"
          onClick={() => update.mutate(form)}
          disabled={update.isPending}
          className="w-full bg-primary hover:bg-primary/90 gap-2"
        >
          <Save className="w-4 h-4" />
          {update.isPending ? "Сохранение..." : "Сохранить настройки"}
        </Button>
      </div>
    </div>
  );
}
