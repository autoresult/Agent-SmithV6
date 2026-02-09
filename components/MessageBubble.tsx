import { Message } from '@/lib/types';
import VoiceMessage from './VoiceMessage';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { User, Loader2 } from 'lucide-react';
import {
  parseUCPContent,
  extractUCPData,
  ProductCarousel,
  ProductCard,
  CheckoutButton,
  UCPData,
} from '@/components/ucp';

interface MessageBubbleProps {
  message: Message;
  userAvatar?: string;
  userName?: string;
  onSendMessage?: (message: string) => void;
}

// ... (omitindo UCPLoadingState e UCPRenderer para brevidade no diff, mas mantendo no arquivo) ...
// Nota: O tool replace_file_content precisa de contexto exato.
// Como imports estão no topo, e lógica no meio, melhor fazer em 2 chunks.

// CHUNK 1: Imports

// Componente para estados de loading UCP
function UCPLoadingState({ type }: { type: string }) {
  const messages: Record<string, string> = {
    search: 'Buscando produtos...',
    detail: 'Carregando detalhes...',
    checkout: 'Gerando link de pagamento...',
    default: 'Processando...',
  };

  return (
    <div className="flex items-center gap-3 bg-zinc-900/50 border border-zinc-800 rounded-xl p-4">
      <Loader2 className="h-5 w-5 animate-spin text-blue-500" />
      <span className="text-sm text-zinc-400">{messages[type] || messages.default}</span>
    </div>
  );
}

// Componente para renderizar conteúdo UCP
function UCPRenderer({
  data,
  onSendMessage,
}: {
  data: UCPData;
  onSendMessage?: (message: string) => void;
}) {
  switch (data.type) {
    case 'ucp_product_list':
      return (
        <ProductCarousel
          products={data.products}
          shopDomain={data.shop_domain}
          query={data.query}
          onSendMessage={onSendMessage}
        />
      );

    case 'ucp_product_detail':
      return <ProductCard product={data.product} size="large" onSendMessage={onSendMessage} />;

    case 'ucp_checkout':
      return <CheckoutButton data={data} />;

    default:
      return null;
  }
}

export function MessageBubble({
  message,
  userAvatar,
  userName,
  onSendMessage,
}: MessageBubbleProps) {
  const isUser = message.role === 'user';
  const isVoice = message.type === 'voice';

  // 🔥 FIX: Detecta mensagem humana por sender_user_id (novo padrão) OU regex (fallback legado)
  const hasSenderFromDb = !!message.sender_user_id && !!message.sender;
  const humanMatch = !hasSenderFromDb && message.content?.match(/^\[👤\s+(.+?)\]/);
  const isHumanMessage = hasSenderFromDb || !!humanMatch;

  // Nome e avatar do remetente humano
  const humanSenderName = hasSenderFromDb
    ? `${message.sender?.first_name || ''} ${message.sender?.last_name || ''}`.trim()
    : humanMatch
      ? humanMatch[1]
      : null;
  const humanSenderAvatar = hasSenderFromDb ? message.sender?.avatar_url : null;

  // Remove o prefixo do conteúdo para exibição (apenas legado)
  const rawContent = humanMatch ? message.content.replace(/^\[👤\s+.+?\]\n?/, '') : message.content;

  // 🛒 UCP: Detectar e extrair conteúdo de comércio
  let displayContent = rawContent;
  let ucpData: UCPData | null = null;

  if (!isUser && rawContent) {
    const extracted = extractUCPData(rawContent);
    displayContent = extracted.text;
    ucpData = extracted.data;

    // DEBUG: Log para diagnóstico
    if (process.env.NODE_ENV === 'development') {
      console.log('[MessageBubble] Raw content length:', rawContent.length);
      console.log('[MessageBubble] Contains ucp_:', rawContent.includes('ucp_'));
      console.log('[MessageBubble] UCP Data extracted:', ucpData ? ucpData.type : 'null');

      if (rawContent.includes('ucp_') && !ucpData) {
        console.warn('[MessageBubble] ⚠️ Contains "ucp_" but failed to parse!');
        console.warn('[MessageBubble] Content preview:', rawContent.substring(0, 500));
      }
    }
  }

  // FALLBACK: Se não conseguiu parsear mas tem estrutura de produtos
  if (!ucpData && !isUser && rawContent.includes('"type"') && rawContent.includes('ucp_product')) {
    console.warn('[MessageBubble] Attempting fallback JSON extraction...');
    try {
      const jsonMatch = rawContent.match(/\{[\s\S]*"type"[\s\S]*"ucp_[\s\S]*\}/);
      if (jsonMatch) {
        let brackets = 0;
        let start = rawContent.indexOf(jsonMatch[0]);
        let end = start;

        for (let i = start; i < rawContent.length; i++) {
          if (rawContent[i] === '{') brackets++;
          if (rawContent[i] === '}') {
            brackets--;
            if (brackets === 0) {
              end = i + 1;
              break;
            }
          }
        }

        // Check if we actually found a valid block
        if (end <= start) {
          console.warn(
            '[MessageBubble] ⚠️ JSON seems truncated (no closing bracket found). Skipping fallback.',
          );
          return;
        }

        const jsonStr = rawContent.substring(start, end);
        if (!jsonStr.trim()) return;

        const parsed = JSON.parse(jsonStr);

        if (parsed?.type?.startsWith('ucp_')) {
          ucpData = parsed as UCPData;
          displayContent = rawContent.substring(0, start).trim() + rawContent.substring(end).trim();
          console.log('[MessageBubble] ✅ Fallback succeeded!', ucpData.type);
        }
      }
    } catch (e) {
      console.error('[MessageBubble] Fallback parsing failed:', e);
    }
  }

  return (
    <div className={`flex w-full ${isUser ? 'justify-end' : 'justify-start'} mb-6`}>
      {/* 📷 Avatar para mensagens humanas (lado esquerdo) */}
      {isHumanMessage && (
        <div className="flex-shrink-0 mr-2 self-start mt-5">
          <Avatar className="h-6 w-6 border border-zinc-600">
            <AvatarImage src={humanSenderAvatar || ''} />
            <AvatarFallback className="bg-zinc-700 text-zinc-300 text-[10px]">
              <User className="h-3 w-3" />
            </AvatarFallback>
          </Avatar>
        </div>
      )}

      <div className={`flex flex-col max-w-[80%] ${isUser ? 'items-end' : 'items-start'}`}>
        {/* Nome do remetente para mensagens humanas */}
        {isHumanMessage && humanSenderName && (
          <div className="text-[10px] text-red-400 font-semibold mb-1 flex items-center gap-1">
            👤 {humanSenderName}
          </div>
        )}

        {/* Imagem (Se houver) */}
        {message.image_url && (
          <div
            className={`${isHumanMessage ? 'bg-[#18181b] border border-[#27272a]' : 'bg-black'} rounded-2xl p-2 overflow-hidden`}
          >
            <img
              src={message.image_url}
              alt="Anexo"
              className="block w-full h-auto max-h-[400px] max-w-[400px] object-cover cursor-zoom-in hover:opacity-90 transition-opacity rounded-xl"
              onClick={() => window.open(message.image_url, '_blank')}
            />
          </div>
        )}

        {/* Áudio (Se houver) */}
        {isVoice && message.audio_url && (
          <div
            className={`${isHumanMessage ? 'bg-[#18181b] border border-[#27272a]' : 'bg-black'} rounded-2xl px-4 py-3`}
          >
            <VoiceMessage audioUrl={message.audio_url} transcription={undefined} />
          </div>
        )}

        {/* 🛒 UCP Content - Renderização especial para comércio */}
        {ucpData && (
          <div className="w-full mt-2">
            <UCPRenderer data={ucpData} onSendMessage={onSendMessage} />
          </div>
        )}

        {/* Mensagem de texto (apenas se não for placeholder de mídia) */}
        {displayContent &&
          // !ucpData não é mais checado aqui, permitindo modo híbrido
          !message.image_url &&
          !(isVoice && message.audio_url) &&
          !displayContent.includes('Imagem enviada') &&
          !displayContent.includes('Áudio enviado') &&
          displayContent !== '[Mensagem de voz]' && (
            <div
              className={`${
                isUser
                  ? 'bg-black text-white rounded-2xl rounded-br-sm px-4 py-3'
                  : isHumanMessage
                    ? 'bg-zinc-800 text-white rounded-2xl rounded-bl-sm px-4 py-3 border border-zinc-700'
                    : ''
              }`}
            >
              <div
                className={`text-base leading-relaxed prose prose-invert max-w-none
              prose-p:my-2 
              prose-headings:text-zinc-100 
              prose-strong:text-zinc-100
              prose-code:bg-[#1a1a1a] prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded
              prose-pre:bg-[#1a1a1a] prose-pre:border prose-pre:border-[#333]
              prose-ul:my-2 prose-li:my-0.5
              text-white
            `}
              >
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{displayContent}</ReactMarkdown>
              </div>
            </div>
          )}
      </div>
    </div>
  );
}
