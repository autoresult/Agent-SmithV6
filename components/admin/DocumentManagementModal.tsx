'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  FileText,
  Upload,
  Trash2,
  Eye,
  AlertCircle,
  CheckCircle,
  Loader2,
  MoreVertical,
  RefreshCw,
  Brain,
  Zap,
  FileStack,
  Bot,
  Database,
  BarChart3,
  AlertTriangle,
} from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { BenchmarkModal } from './BenchmarkModal';

interface Document {
  document_id: string;
  file_name: string;
  file_type: string;
  file_size: number;
  status: string;
  chunks_count: number;
  ingestion_strategy?: string;
  quality_score?: number;
  error_message?: string;
  created_at: string;
  processed_at?: string;
  agent_id?: string | null;
}

interface DocumentStats {
  total_documents: number;
  total_chunks: number;
  total_characters: number;
  avg_chunk_size: number;
  min_chunk_size: number;
  max_chunk_size: number;
  documents_by_status: Record<string, number>;
  total_file_size: number;
}

interface Props {
  companyId: string;
  companyName: string;
}

export function DocumentManagementModal({ companyId, companyName }: Props) {
  const [open, setOpen] = useState(false);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [stats, setStats] = useState<DocumentStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  // Strategy selection
  const [selectedStrategy, setSelectedStrategy] = useState<string>('semantic');

  // Agent selection
  const [agents, setAgents] = useState<{ id: string; name: string }[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState<string>('');

  // Reprocess dialog state
  const [reprocessDoc, setReprocessDoc] = useState<Document | null>(null);
  const [reprocessStrategy, setReprocessStrategy] = useState<string>('semantic');
  const [reprocessing, setReprocessing] = useState(false);

  // 🔥 FIX: Estado para controlar qual dropdown está aberto (evita focus trap deadlock)
  const [openDropdownId, setOpenDropdownId] = useState<string | null>(null);

  const { toast } = useToast();
  const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

  useEffect(() => {
    if (open) {
      loadDocuments();
      loadStats();
      loadAgents();
    }
  }, [open]);

  const loadAgents = async () => {
    try {
      const response = await fetch(`${BACKEND_URL}/api/agents/company/${companyId}`);
      if (response.ok) {
        const data = await response.json();
        setAgents(data);

        // Se só tem 1 agente, seleciona automaticamente
        if (data.length === 1) {
          setSelectedAgentId(data[0].id);
        }
      }
    } catch (error) {
      console.error('Error loading agents:', error);
    }
  };

  const loadDocuments = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${BACKEND_URL}/documents/?company_id=${companyId}`);
      if (response.ok) {
        const data = await response.json();
        setDocuments(data);
      }
    } catch (error) {
      console.error('Error loading documents:', error);
      toast({
        title: 'Erro',
        description: 'Falha ao carregar documentos',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  const loadStats = async () => {
    try {
      const response = await fetch(`${BACKEND_URL}/documents/stats/${companyId}`);
      if (response.ok) {
        const data = await response.json();
        setStats(data);
      }
    } catch (error) {
      console.error('Error loading stats:', error);
    }
  };

  const handleFileUpload = async () => {
    // Validação: Agente é obrigatório
    if (!selectedAgentId) {
      toast({
        title: 'Agente obrigatório',
        description: 'Selecione um agente antes de fazer upload do documento.',
        variant: 'destructive',
      });
      return;
    }

    if (!selectedFile) {
      toast({
        title: 'Arquivo obrigatório',
        description: 'Selecione um arquivo para upload.',
        variant: 'destructive',
      });
      return;
    }

    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('company_id', companyId);
      formData.append('strategy', selectedStrategy);
      formData.append('agent_id', selectedAgentId);

      const response = await fetch(`${BACKEND_URL}/documents/upload`, {
        method: 'POST',
        body: formData,
      });

      if (response.ok) {
        const result = await response.json();
        setSelectedFile(null);
        loadDocuments();
        loadStats();

        const agentName = agents.find((a) => a.id === selectedAgentId)?.name || 'Agente';
        toast({
          title: 'Sucesso',
          description: `Documento enviado para ${agentName}. Processando...`,
        });
      } else {
        const error = await response.json();
        toast({
          title: 'Erro',
          description: error.detail || 'Erro ao enviar documento',
          variant: 'destructive',
        });
      }
    } catch (error) {
      console.error('Error uploading document:', error);
      toast({
        title: 'Erro',
        description: 'Erro ao enviar documento',
        variant: 'destructive',
      });
    } finally {
      setUploading(false);
    }
  };

  const handleReprocess = async () => {
    if (!reprocessDoc) return;

    setReprocessing(true);
    try {
      const response = await fetch(`${BACKEND_URL}/documents/reprocess`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          document_id: reprocessDoc.document_id,
          company_id: companyId,
          strategy: reprocessStrategy,
        }),
      });

      if (response.ok) {
        setReprocessDoc(null);
        loadDocuments();
        loadStats();
        toast({
          title: 'Sucesso',
          description: `Documento sendo reprocessado com ${getStrategyLabel(reprocessStrategy)}`,
        });
      } else {
        const error = await response.json();
        toast({
          title: 'Erro',
          description: error.detail || 'Erro ao reprocessar',
          variant: 'destructive',
        });
      }
    } catch (error) {
      console.error('Error reprocessing:', error);
      toast({
        title: 'Erro',
        description: 'Erro ao reprocessar documento',
        variant: 'destructive',
      });
    } finally {
      setReprocessing(false);
    }
  };

  const handleDelete = async (documentId: string) => {
    if (!confirm('Tem certeza que deseja deletar este documento?')) return;

    try {
      const response = await fetch(
        `${BACKEND_URL}/documents/${documentId}?company_id=${companyId}`,
        {
          method: 'DELETE',
        },
      );

      if (response.ok) {
        loadDocuments();
        loadStats();
        toast({
          title: 'Sucesso',
          description: 'Documento deletado',
        });
      } else {
        toast({
          title: 'Erro',
          description: 'Erro ao deletar documento',
          variant: 'destructive',
        });
      }
    } catch (error) {
      console.error('Error deleting document:', error);
      toast({
        title: 'Erro',
        description: 'Erro ao deletar documento',
        variant: 'destructive',
      });
    }
  };

  // 🔥 FIX: Handler para abrir dialog de reprocess SEM focus trap conflict
  const handleOpenReprocessDialog = useCallback((doc: Document) => {
    // 1. Fecha o dropdown PRIMEIRO (síncrono)
    setOpenDropdownId(null);

    // 2. Aguarda o dropdown fechar completamente antes de abrir o dialog
    // Usa requestAnimationFrame para garantir que o DOM atualizou
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        setReprocessDoc(doc);
        setReprocessStrategy(doc.ingestion_strategy || 'semantic');
      });
    });
  }, []);

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
  };

  const getStrategyLabel = (strategy?: string) => {
    switch (strategy) {
      case 'semantic':
        return 'IA Semântica';
      case 'page':
        return 'Página a Página';
      case 'recursive':
        return 'Rápido';
      case 'agentic':
        return 'Agente';
      default:
        return strategy || 'Desconhecido';
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed':
        return (
          <Badge className="bg-green-500/20 text-green-400 border-green-500/30">
            <CheckCircle className="w-3 h-3 mr-1" />
            Completo
          </Badge>
        );
      case 'processing':
      case 'pending':
        return (
          <Badge className="bg-blue-500/20 text-blue-400 border-blue-500/30">
            <Loader2 className="w-3 h-3 mr-1 animate-spin" />
            Processando...
          </Badge>
        );
      case 'failed':
        return (
          <Badge className="bg-red-500/20 text-red-400 border-red-500/30">
            <AlertCircle className="w-3 h-3 mr-1" />
            Falhou
          </Badge>
        );
      default:
        return <Badge className="bg-gray-500/20 text-gray-400 border-gray-500/30">{status}</Badge>;
    }
  };

  const getStrategyBadge = (strategy?: string) => {
    switch (strategy) {
      case 'semantic':
        return (
          <Badge className="bg-purple-500/20 text-purple-400 border-purple-500/30">
            <Brain className="w-3 h-3 mr-1" />
            IA Semântica
          </Badge>
        );
      case 'page':
        return (
          <Badge className="bg-blue-500/20 text-blue-400 border-blue-500/30">
            <FileStack className="w-3 h-3 mr-1" />
            Página
          </Badge>
        );
      case 'recursive':
        return (
          <Badge className="bg-gray-500/20 text-gray-400 border-gray-500/30">
            <Zap className="w-3 h-3 mr-1" />
            Rápido
          </Badge>
        );
      case 'agentic':
        return (
          <Badge className="bg-yellow-500/20 text-yellow-400 border-yellow-500/30">
            <Brain className="w-3 h-3 mr-1" />
            Agente
          </Badge>
        );
      default:
        return null;
    }
  };

  const getAgentName = (agentId?: string | null) => {
    if (!agentId) return 'Sem agente';
    const agent = agents.find((a) => a.id === agentId);
    return agent ? agent.name : 'Desconhecido';
  };

  // Verifica se pode fazer upload (arquivo + agente selecionados)
  const canUpload = selectedFile && selectedAgentId;

  return (
    <>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogTrigger asChild>
          <Button
            variant="outline"
            className="bg-transparent border-[#3D3D3D] text-gray-400 hover:text-white hover:bg-[#2D2D2D]"
          >
            <Database className="w-4 h-4 mr-2" />
            Base de Conhecimento
          </Button>
        </DialogTrigger>
        <DialogContent className="bg-[#1A1A1A] border-[#2D2D2D] text-white max-w-6xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-2xl font-bold">
              Base de Conhecimento RAG - {companyName}
            </DialogTitle>
          </DialogHeader>

          {/* Estatísticas (Cards) */}
          {stats && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              <Card className="bg-[#0A0A0A] border-[#2D2D2D]">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs text-gray-400">Total de Docs</p>
                      <p className="text-2xl font-bold text-white">{stats.total_documents}</p>
                    </div>
                    <FileText className="w-8 h-8 text-blue-500" />
                  </div>
                </CardContent>
              </Card>

              <Card className="bg-[#0A0A0A] border-[#2D2D2D]">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs text-gray-400">Total de Chunks</p>
                      <p className="text-2xl font-bold text-white">{stats.total_chunks}</p>
                    </div>
                    <BarChart3 className="w-8 h-8 text-purple-500" />
                  </div>
                </CardContent>
              </Card>

              <Card className="bg-[#0A0A0A] border-[#2D2D2D]">
                <CardContent className="p-4">
                  <div>
                    <p className="text-xs text-gray-400">Tamanho Total</p>
                    <p className="text-lg font-bold text-white">
                      {formatBytes(stats.total_file_size)}
                    </p>
                    <p className="text-xs text-gray-500 mt-1">
                      {stats.total_characters.toLocaleString()} caracteres
                    </p>
                  </div>
                </CardContent>
              </Card>

              <Card className="bg-[#0A0A0A] border-[#2D2D2D]">
                <CardContent className="p-4">
                  <div>
                    <p className="text-xs text-gray-400">Tamanho dos Chunks</p>
                    <p className="text-sm font-medium text-white">
                      Média: {stats.avg_chunk_size} chars
                    </p>
                    <p className="text-xs text-gray-500">
                      Min: {stats.min_chunk_size} / Max: {stats.max_chunk_size}
                    </p>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}

          {/* Upload Card */}
          <Card className="bg-[#0A0A0A] border-[#2D2D2D] mb-6">
            <CardContent className="p-4">
              <div className="space-y-4">
                {/* Alerta se não tem agentes */}
                {agents.length === 0 && (
                  <div className="flex items-center gap-2 p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
                    <AlertTriangle className="w-5 h-5 text-yellow-500" />
                    <p className="text-sm text-yellow-400">
                      Nenhum agente cadastrado. Crie um agente antes de fazer upload de documentos.
                    </p>
                  </div>
                )}

                <div className="grid grid-cols-1 md:grid-cols-12 gap-4">
                  {/* File Input */}
                  <div className="md:col-span-5">
                    <label className="text-sm font-medium text-gray-300 mb-2 block">Arquivo</label>
                    <input
                      type="file"
                      accept=".pdf,.docx,.txt,.md,.csv"
                      onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                      className="w-full text-sm text-gray-400 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:font-semibold file:bg-gradient-to-r file:from-blue-600 file:to-cyan-600 file:text-white hover:file:from-blue-700 hover:file:to-cyan-700"
                    />
                    <p className="text-xs text-gray-500 mt-1">PDF, DOCX, TXT, MD, CSV (Max 10MB)</p>
                  </div>

                  {/* Agent Selector - OBRIGATÓRIO */}
                  <div className="md:col-span-4">
                    <label className="text-sm font-medium text-gray-300 mb-2 block">
                      Vincular ao Agente <span className="text-red-400">*</span>
                    </label>
                    <Select
                      value={selectedAgentId}
                      onValueChange={setSelectedAgentId}
                      disabled={agents.length === 0}
                    >
                      <SelectTrigger
                        className={`bg-[#1A1A1A] border-[#2D2D2D] text-white ${!selectedAgentId && selectedFile ? 'border-red-500/50' : ''
                          }`}
                      >
                        <SelectValue placeholder="Selecione um agente..." />
                      </SelectTrigger>
                      <SelectContent className="bg-[#1A1A1A] border-[#2D2D2D]">
                        {agents.map((agent) => (
                          <SelectItem key={agent.id} value={agent.id} className="text-white">
                            <div className="flex items-center gap-2">
                              <Bot className="w-3 h-3 text-blue-400" />
                              {agent.name}
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    {!selectedAgentId && selectedFile && (
                      <p className="text-xs text-red-400 mt-1">
                        Selecione um agente para continuar
                      </p>
                    )}
                  </div>

                  {/* Strategy Selector */}
                  <div className="md:col-span-3">
                    <label className="text-sm font-medium text-gray-300 mb-2 block">
                      Estratégia de Ingestão
                    </label>
                    <Select value={selectedStrategy} onValueChange={setSelectedStrategy}>
                      <SelectTrigger className="bg-[#1A1A1A] border-[#2D2D2D] text-white">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className="bg-[#1A1A1A] border-[#2D2D2D]">
                        <SelectItem value="agentic" className="text-yellow-400">
                          🧠 Agent Chunking
                        </SelectItem>
                        <SelectItem value="semantic" className="text-purple-400">
                          🤖 IA Semântica
                        </SelectItem>
                        <SelectItem value="page" className="text-blue-400">
                          📄 Página a Página
                        </SelectItem>
                        <SelectItem value="recursive" className="text-gray-400">
                          ⚡ Rápido
                        </SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="flex items-center justify-end pt-2">
                  <Button
                    onClick={handleFileUpload}
                    disabled={!canUpload || uploading}
                    className="bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-700 hover:to-cyan-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {uploading ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Processando...
                      </>
                    ) : (
                      <>
                        <Upload className="w-4 h-4 mr-2" />
                        Fazer Upload
                      </>
                    )}
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Benchmark Button */}
          <div className="mb-6">
            <BenchmarkModal companyId={companyId} />
          </div>

          {/* Lista de Documentos */}
          <div className="space-y-3">
            <h3 className="text-lg font-semibold text-white mb-3">
              Documentos ({documents.length})
            </h3>
            {loading ? (
              <p className="text-gray-400 text-center py-8">Carregando...</p>
            ) : documents.length === 0 ? (
              <Card className="bg-[#0A0A0A] border-[#2D2D2D]">
                <CardContent className="py-8 text-center">
                  <FileText className="w-12 h-12 text-gray-600 mx-auto mb-2" />
                  <p className="text-gray-400">Nenhum documento encontrado</p>
                </CardContent>
              </Card>
            ) : (
              documents.map((doc) => (
                <Card key={doc.document_id} className="bg-[#0A0A0A] border-[#2D2D2D]">
                  <CardContent className="p-4">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2 flex-wrap">
                          <FileText className="w-4 h-4 text-blue-400" />
                          <h4 className="text-white font-medium">{doc.file_name}</h4>
                          {getStatusBadge(doc.status)}
                          {getStrategyBadge(doc.ingestion_strategy)}
                          {/* Badge do Agente */}
                          <Badge
                            variant="outline"
                            className={`border-gray-700 bg-transparent ${doc.agent_id
                              ? 'text-blue-400 border-blue-500/30'
                              : 'text-yellow-400 border-yellow-500/30'
                              }`}
                          >
                            <Bot className="w-3 h-3 mr-1" />
                            {getAgentName(doc.agent_id)}
                          </Badge>
                        </div>
                        {/* Info grid */}
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                          <div>
                            <p className="text-gray-500">Tipo</p>
                            <p className="text-gray-300">{doc.file_type.toUpperCase()}</p>
                          </div>
                          <div>
                            <p className="text-gray-500">Tamanho</p>
                            <p className="text-gray-300">{formatBytes(doc.file_size)}</p>
                          </div>
                          <div>
                            <p className="text-gray-500">Chunks</p>
                            <p className="text-gray-300">{doc.chunks_count}</p>
                          </div>
                          <div>
                            <p className="text-gray-500">Upload</p>
                            <p className="text-gray-300">
                              {new Date(doc.created_at).toLocaleDateString('pt-BR')}
                            </p>
                          </div>
                        </div>
                        {doc.error_message && (
                          <p className="text-red-400 text-xs mt-2">Erro: {doc.error_message}</p>
                        )}
                      </div>

                      {/* 🔥 FIX: Dropdown com controle de estado explícito */}
                      <DropdownMenu
                        open={openDropdownId === doc.document_id}
                        onOpenChange={(isOpen) => {
                          setOpenDropdownId(isOpen ? doc.document_id : null);
                        }}
                      >
                        <DropdownMenuTrigger asChild>
                          <Button
                            size="sm"
                            variant="outline"
                            className="bg-transparent border-[#3D3D3D] text-gray-400 hover:text-white ml-4"
                          >
                            <MoreVertical className="w-4 h-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent className="bg-[#1A1A1A] border-[#2D2D2D]" align="end">
                          <DropdownMenuItem
                            className="text-gray-300 hover:bg-[#2D2D2D] cursor-pointer"
                            onClick={() => {
                              setOpenDropdownId(null); // Fecha dropdown
                              window.open(
                                `${BACKEND_URL}/documents/chunks/${companyId}?document_id=${doc.document_id}`,
                                '_blank',
                              );
                            }}
                          >
                            <Eye className="w-4 h-4 mr-2" /> Ver Chunks
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            className="text-blue-400 hover:bg-[#2D2D2D] cursor-pointer"
                            onClick={() => handleOpenReprocessDialog(doc)}
                          >
                            <RefreshCw className="w-4 h-4 mr-2" /> Trocar Inteligência
                          </DropdownMenuItem>
                          <DropdownMenuSeparator className="bg-[#2D2D2D]" />
                          <DropdownMenuItem
                            className="text-red-400 hover:bg-[#2D2D2D] cursor-pointer"
                            onClick={() => {
                              setOpenDropdownId(null); // Fecha dropdown
                              handleDelete(doc.document_id);
                            }}
                          >
                            <Trash2 className="w-4 h-4 mr-2" /> Deletar
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </CardContent>
                </Card>
              ))
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* Reprocess Dialog - 🔥 FIX: Adicionado modal={true} explícito */}
      <Dialog
        open={!!reprocessDoc}
        onOpenChange={(isOpen) => {
          if (!isOpen) {
            setReprocessDoc(null);
          }
        }}
        modal={true}
      >
        <DialogContent className="bg-[#1A1A1A] border-[#2D2D2D] text-white">
          <DialogHeader>
            <DialogTitle>Trocar Estratégia de Chunking</DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="p-3 bg-[#0A0A0A] rounded border border-[#2D2D2D]">
              <p className="text-sm text-gray-400">Arquivo:</p>
              <p className="font-medium text-white">{reprocessDoc?.file_name}</p>
            </div>

            {/* Mostra o agente do documento */}
            <div className="p-3 bg-[#0A0A0A] rounded border border-[#2D2D2D]">
              <p className="text-sm text-gray-400">Agente:</p>
              <p className="font-medium text-blue-400 flex items-center gap-2">
                <Bot className="w-4 h-4" />
                {getAgentName(reprocessDoc?.agent_id)}
              </p>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-300">Nova Estratégia</label>
              <Select value={reprocessStrategy} onValueChange={setReprocessStrategy}>
                <SelectTrigger className="bg-[#0A0A0A] border-[#2D2D2D] text-white">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-[#1A1A1A] border-[#2D2D2D]">
                  <SelectItem value="agentic" className="text-yellow-400">
                    🧠 Agent Chunking
                  </SelectItem>
                  <SelectItem value="semantic" className="text-purple-400">
                    🤖 IA Semântica
                  </SelectItem>
                  <SelectItem value="page" className="text-blue-400">
                    📄 Página a Página
                  </SelectItem>
                  <SelectItem value="recursive" className="text-gray-400">
                    ⚡ Recursive
                  </SelectItem>
                </SelectContent>
              </Select>
              <p className="text-xs text-gray-500">
                O documento será re-indexado do zero com a nova estratégia
              </p>
            </div>
          </div>

          <div className="flex justify-end gap-3">
            <Button
              variant="outline"
              onClick={() => setReprocessDoc(null)}
              className="bg-transparent border-[#3D3D3D] text-gray-400"
            >
              Cancelar
            </Button>
            <Button
              onClick={handleReprocess}
              disabled={reprocessing}
              className="bg-gradient-to-r from-blue-600 to-cyan-600"
            >
              {reprocessing ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" /> Processando...
                </>
              ) : (
                'Confirmar Troca'
              )}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
