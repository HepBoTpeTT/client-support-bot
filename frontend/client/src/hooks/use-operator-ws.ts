import { useEffect, useRef, useCallback } from "react";

export interface WsMessage {
    type: "operator_message" | "user_message";
    content: string;
    createdAt: string;
}

interface UseOperatorWSOptions {
    sessionId: string | null;
    onMessage: (msg: WsMessage) => void;
}

export function useOperatorWS({ sessionId, onMessage }: UseOperatorWSOptions) {
    const wsRef = useRef<WebSocket | null>(null);
    const onMessageRef = useRef(onMessage);
    onMessageRef.current = onMessage;

    useEffect(() => {
        if (!sessionId) return;

        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const url = `${protocol}//${window.location.host}/ws/chat/${sessionId}`;
        const ws = new WebSocket(url);
        wsRef.current = ws;

        ws.onmessage = (e) => {
            try {
                const msg: WsMessage = JSON.parse(e.data);
                onMessageRef.current(msg);
            } catch {
                // ignore malformed
            }
        };

        ws.onerror = () => console.debug("[WS] operator error");

        return () => {
            ws.close();
            wsRef.current = null;
        };
    }, [sessionId]);
}