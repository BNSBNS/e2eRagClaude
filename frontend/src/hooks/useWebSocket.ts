// src/hooks/useWebSocket.ts
/**
 * Secure WebSocket Hook with JWT Authentication
 *
 * IMPORTANT SECURITY UPDATE:
 * This hook now includes JWT token authentication for all WebSocket connections.
 * The token is passed as a query parameter since WebSocket API doesn't support
 * custom headers in browser environments.
 *
 * Features:
 * - JWT authentication via query parameter
 * - Automatic reconnection (except for auth failures)
 * - Connection status tracking
 * - Message queueing during disconnection
 * - Graceful error handling
 */

import { useEffect, useRef, useState, useCallback } from 'react';

// WebSocket connection status types
export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

// WebSocket message types
export interface WebSocketMessage {
  type: string;
  [key: string]: any;
}

export const useWebSocket = () => {
  const [lastMessage, setLastMessage] = useState<MessageEvent | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('disconnected');
  const ws = useRef<WebSocket | null>(null);
  const reconnectTimeout = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttempts = useRef<number>(0);
  const maxReconnectAttempts = 5;
  const messageQueue = useRef<any[]>([]);

  /**
   * Connect to WebSocket with JWT authentication
   *
   * Educational Note:
   * WebSocket connections are established using the ws:// protocol (or wss:// for secure).
   * Unlike HTTP requests, WebSocket connections persist, allowing bidirectional communication.
   *
   * Why query parameter for token?
   * - Browser WebSocket API doesn't support custom headers
   * - Query params are the standard approach for WebSocket auth
   * - Token is validated once at connection time, not per message
   */
  const connect = useCallback(() => {
    const token = localStorage.getItem('access_token');

    if (!token) {
      console.error('No access token available for WebSocket connection');
      setConnectionStatus('error');
      return;
    }

    // Get API URL from environment
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    // Convert HTTP URL to WebSocket URL
    const wsUrl = apiUrl.replace('http://', 'ws://').replace('https://', 'wss://');

    // CRITICAL: Pass token as query parameter for authentication
    const connectionUrl = `${wsUrl}/ws/connect?token=${token}`;

    console.log('Connecting to WebSocket with authentication...');
    setConnectionStatus('connecting');

    try {
      ws.current = new WebSocket(connectionUrl);

      ws.current.onopen = () => {
        console.log('WebSocket connected successfully with JWT authentication');
        setConnectionStatus('connected');
        reconnectAttempts.current = 0;

        // Clear any pending reconnection attempts
        if (reconnectTimeout.current) {
          clearTimeout(reconnectTimeout.current);
          reconnectTimeout.current = null;
        }

        // Send any queued messages
        while (messageQueue.current.length > 0) {
          const queuedMessage = messageQueue.current.shift();
          ws.current?.send(JSON.stringify(queuedMessage));
        }

        // Send initial ping to verify connection
        ws.current?.send(JSON.stringify({ type: 'ping' }));
      };

      ws.current.onmessage = (event) => {
        setLastMessage(event);

        // Log received messages (useful for debugging)
        try {
          const data = JSON.parse(event.data);
          console.log('WebSocket message received:', data.type);
        } catch (e) {
          console.log('WebSocket message received (non-JSON)');
        }
      };

      ws.current.onerror = (error) => {
        console.error('WebSocket error:', error);
        setConnectionStatus('error');
      };

      ws.current.onclose = (event) => {
        console.log('WebSocket closed:', {
          code: event.code,
          reason: event.reason,
          wasClean: event.wasClean
        });
        setConnectionStatus('disconnected');

        /**
         * Handle reconnection based on close code
         *
         * Close Codes:
         * - 1000: Normal closure (don't reconnect)
         * - 1001: Going away (don't reconnect)
         * - 1008: Policy violation (auth failed - don't reconnect)
         * - 1011: Internal error (reconnect)
         * - Other: Network issue (reconnect)
         */
        const shouldReconnect =
          event.code !== 1000 && // Normal closure
          event.code !== 1001 && // Going away
          event.code !== 1008 && // Policy violation (auth failed)
          reconnectAttempts.current < maxReconnectAttempts;

        if (shouldReconnect) {
          reconnectAttempts.current += 1;
          const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000);

          console.log(
            `Attempting reconnection ${reconnectAttempts.current}/${maxReconnectAttempts} ` +
            `in ${delay}ms...`
          );

          reconnectTimeout.current = setTimeout(() => {
            connect();
          }, delay);
        } else if (event.code === 1008) {
          console.error('WebSocket authentication failed. Token may be invalid or expired.');
          // Could trigger a token refresh or redirect to login here
        } else if (reconnectAttempts.current >= maxReconnectAttempts) {
          console.error('Max reconnection attempts reached. Please refresh the page.');
        }
      };

    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
      setConnectionStatus('error');
    }
  }, []);

  // Connect on mount
  useEffect(() => {
    connect();

    // Cleanup on unmount
    return () => {
      if (reconnectTimeout.current) {
        clearTimeout(reconnectTimeout.current);
      }
      ws.current?.close(1000, 'Component unmounted');
    };
  }, [connect]);

  /**
   * Send message through WebSocket
   *
   * If connection is not open, message is queued and sent when connection is restored.
   * This prevents message loss during temporary disconnections.
   *
   * @param message - Message object to send (will be JSON stringified)
   */
  const sendMessage = useCallback((message: WebSocketMessage) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket not connected. Queueing message...');
      messageQueue.current.push(message);

      // Attempt to reconnect if disconnected
      if (connectionStatus === 'disconnected') {
        connect();
      }
    }
  }, [connectionStatus, connect]);

  /**
   * Manually reconnect WebSocket
   * Useful for forcing reconnection after token refresh
   */
  const reconnect = useCallback(() => {
    if (ws.current) {
      ws.current.close(1000, 'Manual reconnection');
    }
    reconnectAttempts.current = 0;
    connect();
  }, [connect]);

  return {
    lastMessage,
    connectionStatus,
    sendMessage,
    reconnect,
    isConnected: connectionStatus === 'connected'
  };
};