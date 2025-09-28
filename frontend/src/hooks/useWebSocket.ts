// src/hooks/useWebSocket.ts
import { useEffect, useRef, useState } from 'react';

export const useWebSocket = () => {
  const [lastMessage, setLastMessage] = useState<MessageEvent | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected'>('disconnected');
  const ws = useRef<WebSocket | null>(null);

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) return;

    const wsUrl = `ws://localhost:8000/ws/user_id?token=${token}`;
    ws.current = new WebSocket(wsUrl);

    ws.current.onopen = () => {
      setConnectionStatus('connected');
    };

    ws.current.onmessage = (event) => {
      setLastMessage(event);
    };

    ws.current.onclose = () => {
      setConnectionStatus('disconnected');
    };

    return () => {
      ws.current?.close();
    };
  }, []);

  const sendMessage = (message: any) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(message));
    }
  };

  return { lastMessage, connectionStatus, sendMessage };
};