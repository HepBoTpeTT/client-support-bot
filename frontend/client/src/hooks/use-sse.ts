import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";

const EVENT_TO_QUERY: Record<string, string[]> = {
    operator_sessions_updated: ["/api/operator/sessions"],
    dialogs_updated:           ["/api/dialogs"],
    crawl_progress:            ["/api/crawl/status", "/api/crawl/sessions"],
    achievement_unlocked:      ["/api/gamification"],
    pages_updated:             ["/api/pages"],
    settings_updated:          ["/api/settings"],
};

export function useSSE(url: string = "/api/admin/stream") {
    const qc = useQueryClient();

    useEffect(() => {
        const es = new EventSource(url);

        es.addEventListener("connected", () => {
            console.debug("[SSE] connected");
        });

        Object.entries(EVENT_TO_QUERY).forEach(([event, keys]) => {
            es.addEventListener(event, () => {
                keys.forEach((key) =>
                    qc.invalidateQueries({ queryKey: [key] })
                );
            });
        });

        es.onerror = () => console.debug("[SSE] error, browser will retry");

        return () => es.close();
    }, [url, qc]);
}