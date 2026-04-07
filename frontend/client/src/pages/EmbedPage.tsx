import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import { Code2, Copy, Check, FileCode, Globe } from "lucide-react";
import { useState } from "react";

interface EmbedCode {
  jsSnippet: string;
  iframeSnippet: string;
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const { toast } = useToast();

  const copy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    toast({ title: "Скопировано в буфер обмена" });
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Button variant="ghost" size="sm" onClick={copy} className="gap-2 text-muted-foreground hover:text-foreground">
      {copied ? <Check className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4" />}
      {copied ? "Скопировано" : "Копировать"}
    </Button>
  );
}

export default function EmbedPage() {
  const { data: embed, isLoading } = useQuery<EmbedCode>({
    queryKey: ["/api/embed-code"],
  });

  return (
    <div className="p-8 max-w-4xl">
      <div className="mb-8">
        <h1 className="text-xl font-semibold text-foreground flex items-center gap-2">
          <Code2 className="w-5 h-5 text-primary" />
          Код встраивания
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Вставьте один из этих фрагментов кода на страницы стороннего сайта
        </p>
      </div>

      {/* Info cards */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        <Card className="bg-card border-border">
          <CardContent className="p-4 flex items-start gap-3">
            <div className="w-9 h-9 rounded-lg bg-primary/20 flex items-center justify-center flex-shrink-0">
              <FileCode className="w-5 h-5 text-primary" />
            </div>
            <div>
              <div className="text-sm font-medium text-foreground">JS-сниппет</div>
              <div className="text-xs text-muted-foreground mt-0.5">
                Вставьте перед &lt;/body&gt;. Виджет всплывает в правом нижнем углу, не нарушает вёрстку.
              </div>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-card border-border">
          <CardContent className="p-4 flex items-start gap-3">
            <div className="w-9 h-9 rounded-lg bg-primary/20 flex items-center justify-center flex-shrink-0">
              <Globe className="w-5 h-5 text-primary" />
            </div>
            <div>
              <div className="text-sm font-medium text-foreground">iFrame</div>
              <div className="text-xs text-muted-foreground mt-0.5">
                Полная изоляция CSS — идеален для сложных сайтов где JS-виджет может конфликтовать.
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {isLoading ? (
        <div className="text-muted-foreground text-sm">Загрузка...</div>
      ) : (
        <div className="space-y-5">
          {/* Instructions */}
          <Card className="bg-card border-border">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Инструкция по установке</CardTitle>
            </CardHeader>
            <CardContent>
              <ol className="space-y-3 text-sm text-muted-foreground">
                {[
                  "Перейдите в раздел «Настройки виджета», введите ваш OpenAI API ключ и настройте парсинг",
                  "Запустите парсинг вашего сайта в разделе «Парсинг сайта» — дождитесь завершения",
                  "Убедитесь, что в разделе «База знаний» отображаются страницы со статусом «Готово»",
                  "Скопируйте JS-сниппет или iFrame-код и вставьте на страницы вашего сайта",
                  "Виджет появится в правом нижнем углу и будет готов отвечать на вопросы посетителей",
                ].map((step, i) => (
                  <li key={i} className="flex gap-3">
                    <span className="w-5 h-5 rounded-full bg-primary/20 text-primary text-xs flex items-center justify-center flex-shrink-0 mt-0.5">
                      {i + 1}
                    </span>
                    <span>{step}</span>
                  </li>
                ))}
              </ol>
            </CardContent>
          </Card>

          {/* JS snippet */}
          <Card className="bg-card border-border">
            <CardHeader className="pb-2 flex-row items-center justify-between">
              <div>
                <CardTitle className="text-sm flex items-center gap-2">
                  <Badge className="bg-primary/20 text-primary border-primary/30 text-xs">JS</Badge>
                  JavaScript-сниппет
                </CardTitle>
                <CardDescription className="mt-1">Вставьте этот код перед закрывающим тегом &lt;/body&gt; на каждой странице</CardDescription>
              </div>
              <CopyButton text={embed?.jsSnippet ?? ""} />
            </CardHeader>
            <CardContent>
              <pre
                data-testid="code-js-snippet"
                className="bg-primary/20 text-primary border-primary/30 border rounded-lg p-4 text-xs font-mono overflow-x-auto whitespace-pre-wrap leading-relaxed"
              >
                {embed?.jsSnippet}
              </pre>
            </CardContent>
          </Card>

          {/* iFrame snippet */}
          <Card className="bg-card border-border">
            <CardHeader className="pb-2 flex-row items-center justify-between">
              <div>
                <CardTitle className="text-sm flex items-center gap-2">
                  <Badge className="bg-[rgba(0,48,182,0.2)] text-[hsl(216.7,85.9%,41.8%)] border-blue-800/50 text-xs">iFrame</Badge>
                  iFrame-встраивание
                </CardTitle>
                <CardDescription className="mt-1">Альтернативный метод через iframe — полная изоляция стилей</CardDescription>
              </div>
              <CopyButton text={embed?.iframeSnippet ?? ""} />
            </CardHeader>
            <CardContent>
              <pre
                data-testid="code-iframe-snippet"
                className="bg-[rgba(0,48,182,0.2)] text-[hsl(216.7,85.9%,41.8%)] border-blue-800/50 border rounded-lg p-4 text-xs font-mono overflow-x-auto whitespace-pre-wrap leading-relaxed"
              >
                {embed?.iframeSnippet}
              </pre>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
