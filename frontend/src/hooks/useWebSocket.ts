import { useEffect, useRef, useState, useCallback } from 'react';

interface UseWebSocketOptions {
  maxRetries?: number;
  onMessage?: (event: MessageEvent) => void;
  onOpen?: (event: Event) => void;
  onClose?: (event: CloseEvent) => void;
  onError?: (event: Event) => void;
}

export function useWebSocket(url: string | null, options: UseWebSocketOptions = {}) {
  const { maxRetries = 10, onMessage, onOpen, onClose, onError } = options;

  const [connected, setConnected] = useState(false);
  const [reconnectAttempt, setReconnectAttempt] = useState(0);
  const [lastMessage, setLastMessage] = useState<MessageEvent | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const attemptRef = useRef(0);

  // Keep latest callbacks in refs to avoid resetting connection on callback change
  const onMessageRef = useRef(onMessage);
  const onOpenRef = useRef(onOpen);
  const onCloseRef = useRef(onClose);
  const onErrorRef = useRef(onError);

  useEffect(() => {
    onMessageRef.current = onMessage;
    onOpenRef.current = onOpen;
    onCloseRef.current = onClose;
    onErrorRef.current = onError;
  });

  const connect = useCallback(() => {
    if (!url) return;

    // Clean up existing
    if (wsRef.current) {
      wsRef.current.close();
    }

    console.log(`[useWebSocket] Connecting to ${url}...`);
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = (event) => {
      setConnected(true);
      setReconnectAttempt(0);
      attemptRef.current = 0;
      if (onOpenRef.current) {
        onOpenRef.current(event);
      }
    };

    ws.onmessage = (event) => {
      setLastMessage(event);
      if (onMessageRef.current) {
        onMessageRef.current(event);
      }
    };

    ws.onerror = (event) => {
      if (onErrorRef.current) {
        onErrorRef.current(event);
      }
    };

    ws.onclose = (event) => {
      setConnected(false);
      if (onCloseRef.current) {
        onCloseRef.current(event);
      }

      // Reconnect logic
      if (attemptRef.current < maxRetries) {
        // Exponential backoff: 2^attempt * 1000ms with jitter, capped at 30s
        const backoff = Math.min(30000, Math.pow(2, attemptRef.current) * 1000);
        // Add random jitter between 0 and 1000ms
        const jitter = Math.random() * 1000;
        const delay = backoff + jitter;

        attemptRef.current += 1;
        setReconnectAttempt(attemptRef.current);
        console.log(`[useWebSocket] Connection closed. Reconnecting in ${(delay / 1000).toFixed(1)}s (attempt ${attemptRef.current}/${maxRetries})...`);

        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, delay);
      } else {
        console.warn('[useWebSocket] Max reconnect attempts reached.');
      }
    };
  }, [url, maxRetries]);

  useEffect(() => {
    connect();

    return () => {
      if (wsRef.current) {
        // Clear close handler to avoid triggering reconnect logic on unmount
        wsRef.current.onclose = null;
        wsRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [connect]);

  const send = useCallback((data: string | ArrayBufferLike | Blob | ArrayBufferView) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(data);
      return true;
    }
    return false;
  }, []);

  return {
    connected,
    reconnectAttempt,
    lastMessage,
    send,
  };
}
