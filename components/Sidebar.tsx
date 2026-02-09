'use client';

import { useState, useEffect } from 'react';
import { MessageSquare, Plus, Menu, X } from 'lucide-react';
// 🔒 SECURITY: Removed direct supabase import - using API routes instead
import { Conversation } from '@/lib/types';
import { AccountMenu } from '@/components/AccountMenu';

interface SidebarProps {
  userId: string;
  currentSessionId: string;
  onSelectConversation: (sessionId: string) => void;
  onNewConversation: () => void;
}

export function Sidebar({
  userId,
  currentSessionId,
  onSelectConversation,
  onNewConversation,
}: SidebarProps) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    if (userId) {
      loadConversations();
    }
  }, [userId, currentSessionId]);

  // 🔒 SECURITY: Using API route instead of direct Supabase access
  const loadConversations = async () => {
    try {
      const response = await fetch('/api/conversations');
      if (response.ok) {
        const data = await response.json();
        setConversations(data.conversations || []);
      }
    } catch (error) {
      console.error('Error loading conversations:', error);
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffInHours = (now.getTime() - date.getTime()) / (1000 * 60 * 60);

    if (diffInHours < 24) return 'Hoje';
    if (diffInHours < 48) return 'Ontem';
    return date.toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' });
  };

  const handleNewConversation = () => {
    onNewConversation();
    setIsOpen(false);
  };

  const handleSelectConversation = (sessionId: string) => {
    onSelectConversation(sessionId);
    setIsOpen(false);
  };

  return (
    <>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="fixed top-4 left-4 z-50 p-2 rounded-lg bg-white/5 border border-white/10 hover:bg-white/10 text-white transition-colors lg:hidden backdrop-blur-sm"
      >
        {isOpen ? <X size={20} /> : <Menu size={20} />}
      </button>

      <div
        className={`fixed inset-y-0 left-0 z-40 w-64 backdrop-blur-2xl bg-white/[0.02] border-r border-white/30 transform transition-transform duration-200 ease-in-out lg:translate-x-0 ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex flex-col h-full">
          <div className="p-4 border-b border-white/30">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <img src="/smith-logo.png" alt="Smith Logo" className="w-7 h-7 rounded-full object-cover" />
                <h2 className="text-sm font-semibold text-white/70">Smithv6.0</h2>
              </div>
              <AccountMenu />
            </div>
            <button
              onClick={handleNewConversation}
              className="w-full flex items-center gap-2 px-4 py-3 rounded-lg bg-emerald-500 text-white hover:bg-emerald-600 transition-all shadow-lg shadow-emerald-500/20"
            >
              <Plus size={18} />
              <span className="font-medium">Nova Conversa</span>
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-4">
            <div className="space-y-1">
              {conversations.map((conv) => (
                <button
                  key={conv.id}
                  onClick={() => handleSelectConversation(conv.session_id)}
                  className={`w-full text-left p-3 rounded-lg transition-colors ${
                    conv.session_id === currentSessionId
                      ? 'bg-emerald-500/10 border border-emerald-500/30'
                      : 'hover:bg-white/[0.05] border border-transparent'
                  }`}
                >
                  <div className="flex items-start gap-2">
                    <MessageSquare size={16} className="mt-1 flex-shrink-0 text-white/40" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-white/90 truncate">
                        {conv.title || 'Nova conversa'}
                      </p>
                      <p className="text-xs text-white/40 mt-0.5">{formatDate(conv.updated_at)}</p>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {isOpen && (
        <div
          onClick={() => setIsOpen(false)}
          className="fixed inset-0 bg-black/40 z-30 lg:hidden backdrop-blur-sm"
        />
      )}
    </>
  );
}
