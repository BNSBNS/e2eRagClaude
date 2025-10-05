"use client";

import React, { useEffect, useRef, useState } from "react";
import { useWebSocket } from "@/hooks/useWebSocket";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface Message {
  id: string;
  type: "user" | "assistant";
  content: string;
  timestamp: string; // ISO string
  sources?: any[];
}

type ChatInterfaceProps = {
  documentId: string;
};

export function ChatInterface({ documentId }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [ragMode, setRagMode] = useState<"traditional" | "graph">("traditional");
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const { sendMessage, lastMessage } = useWebSocket();

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (!lastMessage) return;
    try {
      const data = typeof lastMessage.data === "string" ? JSON.parse(lastMessage.data) : lastMessage.data;
      if (!data) return;

      if (data.type === "chat_response") {
        const assistantMsg: Message = {
          id: typeof crypto !== "undefined" && (crypto as any).randomUUID ? (crypto as any).randomUUID() : Date.now().toString(),
          type: "assistant",
          content: data.content?.answer ?? String(data.content ?? ""),
          timestamp: new Date().toISOString(),
          sources: data.content?.sources ?? [],
        };
        setMessages((prev) => [...prev, assistantMsg]);
        setLoading(false);
      } else if (data.type === "chat_partial") {
        // optional: handle streaming partials if your backend sends them
        // Here we append/update a streaming assistant message; simple append:
        const partial = String(data.content ?? "");
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last && last.type === "assistant" && last.content.startsWith("(stream)")) {
            // update last
            const updated = [...prev];
            updated[updated.length - 1] = { ...last, content: `(stream) ${last.content.replace(/^\(stream\)\s*/, "")}${partial}`, timestamp: new Date().toISOString() };
            return updated;
          }
          const msg: Message = {
            id: typeof crypto !== "undefined" && (crypto as any).randomUUID ? (crypto as any).randomUUID() : Date.now().toString(),
            type: "assistant",
            content: `(stream) ${partial}`,
            timestamp: new Date().toISOString(),
          };
          return [...prev, msg];
        });
      }
    } catch (err) {
      console.error("Failed to parse websocket message:", err);
    }
  }, [lastMessage]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed) return;

    const userMessage: Message = {
      id: typeof crypto !== "undefined" && (crypto as any).randomUUID ? (crypto as any).randomUUID() : Date.now().toString(),
      type: "user",
      content: trimmed,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setLoading(true);
    setInput("");

    // Send message via WebSocket for real-time response
    // Include the document id and selected RAG mode
    try {
      sendMessage({
        type: "chat",
        content: trimmed,
        rag_mode: ragMode,
        document_id: documentId,
      });
    } catch (err) {
      console.error("Failed to send websocket message:", err);
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* RAG Mode Selector */}
      <div className="p-4 border-b">
        <div className="flex space-x-4">
          <label className="flex items-center">
            <input
              type="radio"
              name={`rag-mode-${documentId}`}
              value="traditional"
              checked={ragMode === "traditional"}
              onChange={(e) => setRagMode(e.target.value as "traditional" | "graph")}
              className="mr-2"
            />
            Traditional RAG
          </label>
          <label className="flex items-center">
            <input
              type="radio"
              name={`rag-mode-${documentId}`}
              value="graph"
              checked={ragMode === "graph"}
              onChange={(e) => setRagMode(e.target.value as "traditional" | "graph")}
              className="mr-2"
            />
            Graph RAG
          </label>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message) => (
          <div key={message.id} className={`flex ${message.type === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-3xl p-3 rounded-lg ${message.type === "user" ? "bg-blue-500 text-white" : "bg-gray-100 text-gray-900"}`}
            >
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
              {message.sources && message.sources.length > 0 && (
                <div className="mt-2 text-xs opacity-75">
                  Sources: {message.sources.length} documents
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 p-3 rounded-lg">
              <div className="animate-pulse flex space-x-1">
                <div className="rounded-full bg-gray-400 h-2 w-2"></div>
                <div className="rounded-full bg-gray-400 h-2 w-2"></div>
                <div className="rounded-full bg-gray-400 h-2 w-2"></div>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="p-4 border-t">
        <div className="flex space-x-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a question about your documents..."
            className="flex-1 p-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            disabled={loading}
          />
          <button type="submit" disabled={loading} className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50">
            Send
          </button>
        </div>
      </form>
    </div>
  );
}
