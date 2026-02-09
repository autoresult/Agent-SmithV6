'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { formatDistanceToNow } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { UnifiedSidebar } from '@/components/UnifiedSidebar';
import { useUserId } from '@/hooks/useUserId';

interface Conversation {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
  message_count?: number;
}

export default function HistoricoPage() {
  const router = useRouter();
  const { userId: currentUserId } = useUserId();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadConversations();
  }, []);

  const loadConversations = async () => {
    // Middleware já garante autenticação, não precisa verificar aqui
    try {
      const response = await fetch('/api/conversations?include_counts=true');
      if (!response.ok) throw new Error('Failed to load conversations');

      const data = await response.json();
      setConversations(data.conversations || []);
    } catch (error) {
      console.error('Erro ao carregar conversas:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleOpenConversation = (conversationId: string) => {
    router.push(`/dashboard/chat?conversation=${conversationId}`);
  };

  if (loading) {
    return (
      <div className="flex min-h-screen text-white">
        {currentUserId && <UnifiedSidebar userId={currentUserId} />}
        <div className="flex-1 lg:ml-64 flex items-center justify-center">
          <div className="text-gray-400">Carregando histórico...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen text-white">
      {currentUserId && <UnifiedSidebar userId={currentUserId} />}

      <div className="flex-1 lg:ml-64">
        <div className="p-8">
          <div className="max-w-4xl mx-auto">
            <h1 className="text-3xl font-bold mb-8">Histórico de Conversas</h1>

            {conversations.length === 0 ? (
              <div className="bg-gray-900/50 backdrop-blur-sm border border-gray-800 rounded-xl p-12 text-center">
                <p className="text-gray-400 mb-4">Você ainda não tem conversas</p>
                <button
                  onClick={() => router.push('/dashboard/chat')}
                  className="px-6 py-3 bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors"
                >
                  Iniciar primeira conversa
                </button>
              </div>
            ) : (
              <div className="space-y-4">
                {conversations.map((conv) => (
                  <div
                    key={conv.id}
                    onClick={() => handleOpenConversation(conv.id)}
                    className="bg-gray-900/50 backdrop-blur-sm border border-gray-800 rounded-xl p-6 cursor-pointer hover:border-blue-600 transition-colors"
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <h3 className="text-lg font-semibold mb-2">
                          {conv.title || 'Conversa sem título'}
                        </h3>
                        <div className="flex items-center gap-4 text-sm text-gray-400">
                          <span>{conv.message_count} mensagens</span>
                          <span>•</span>
                          <span>
                            Atualizado{' '}
                            {formatDistanceToNow(new Date(conv.updated_at), {
                              addSuffix: true,
                              locale: ptBR,
                            })}
                          </span>
                        </div>
                      </div>
                      <button className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm transition-colors">
                        Abrir
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
