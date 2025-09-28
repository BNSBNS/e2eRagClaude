"use client"
import React, { useState, useRef, useEffect } from 'react';
import { useWebSocket } from '@/hooks/useWebSocket';
import { apiClient } from '@/lib/api';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface Message {
  id: string;
  type: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  sources?: any[];
}

export const ChatInterface: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [ragMode, setRagMode] = useState<'traditional' | 'graph'>('traditional');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  
  const { sendMessage, lastMessage } = useWebSocket();

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (lastMessage) {
      const data = JSON.parse(lastMessage.data);
      if (data.type === 'chat_response') {
        setMessages(prev => [...prev, {
          id: Date.now().toString(),
          type: 'assistant',
          content: data.content.answer,
          timestamp: new Date(),
          sources: data.content.sources
        }]);
        setLoading(false);
      }
    }
  }, [lastMessage]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      type: 'user',
      content: input,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setLoading(true);
    setInput('');

    // Send message via WebSocket for real-time response
    sendMessage({
      type: 'chat',
      content: input,
      rag_mode: ragMode
    });
  };

  return (
    <div className="flex flex-col h-full">
      {/* RAG Mode Selector */}
      <div className="p-4 border-b">
        <div className="flex space-x-4">
          <label className="flex items-center">
            <input
              type="radio"
              value="traditional"
              checked={ragMode === 'traditional'}
              onChange={(e) => setRagMode(e.target.value as any)}
              className="mr-2"
            />
            Traditional RAG
          </label>
          <label className="flex items-center">
            <input
              type="radio"
              value="graph"
              checked={ragMode === 'graph'}
              onChange={(e) => setRagMode(e.target.value as any)}
              className="mr-2"
            />
            Graph RAG
          </label>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-3xl p-3 rounded-lg ${
                message.type === 'user'
                  ? 'bg-blue-500 text-white'
                  : 'bg-gray-100 text-gray-900'
              }`}
            >
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {message.content}
              </ReactMarkdown>
              {message.sources && (
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
          <button
            type="submit"
            disabled={loading}
            className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50"
          >
            Send
          </button>
        </div>
      </form>
    </div>
  );
};