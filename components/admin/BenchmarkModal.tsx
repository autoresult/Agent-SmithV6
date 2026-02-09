'use client';

import { useState, Fragment } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  BarChart3,
  Loader2,
  Trophy,
  Brain,
  Zap,
  FileText,
  AlertCircle,
  CheckCircle2,
  Sparkles,
  Bot,
  Settings2,
} from 'lucide-react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Slider } from '@/components/ui/slider';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

import { useEffect } from 'react';
import { useToast } from '@/hooks/use-toast';

interface ModeMetrics {
  avg_score: number;
  true_rate: number;
  raw_scores: number[];
  chunk_quality?: number; // LLM Judge score (1-5)
}

interface Strategy {
  type: string;
  count: number;
  modes: {
    standard: ModeMetrics;
    hyde: ModeMetrics;
    hybrid: ModeMetrics; // NOVO: Modo híbrido (Dense + Sparse BM25)
  };
}

interface BenchmarkResult {
  benchmark_id: string;
  fixed_threshold: number;
  winner: string; // Format: "strategy_mode" (e.g., "semantic_hyde")
  strategies: Strategy[];
  metadata: {
    total_questions: number;
    execution_time_seconds: number;
    winner_true_rate?: number;
  };
}

interface Props {
  companyId: string;
}

export function BenchmarkModal({ companyId }: Props) {
  const [open, setOpen] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [result, setResult] = useState<BenchmarkResult | null>(null);

  // 🔥 Estados para Job Polling
  const [progress, setProgress] = useState<number>(0);
  const [statusMessage, setStatusMessage] = useState<string>('');

  // 🔥 Novos Estados de Configuração
  const [agents, setAgents] = useState<{ id: string; name: string }[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState<string>('');
  const [threshold, setThreshold] = useState<number>(0.62);
  const [totalQuestions, setTotalQuestions] = useState<number>(10);
  const [sampleSize, setSampleSize] = useState<number>(1);

  const { toast } = useToast();
  const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

  useEffect(() => {
    if (open) {
      loadAgents();
    }
  }, [open]);

  const loadAgents = async () => {
    try {
      const response = await fetch(`${BACKEND_URL}/api/agents/company/${companyId}`);
      if (response.ok) {
        const data = await response.json();
        setAgents(data);
        if (data.length === 1) {
          setSelectedAgentId(data[0].id);
        }
      }
    } catch (error) {
      console.error('Error loading agents:', error);
    }
  };

  // 🔥 Helper para mensagens amigáveis de status
  const getStatusLabel = (status: string): string => {
    const labels: Record<string, string> = {
      queued: 'Aguardando início...',
      generating_dataset: 'Gerando perguntas com IA...',
      questions_generated: 'Perguntas geradas!',
      running_recursive: 'Testando: Recursive Chunking...',
      running_semantic: 'Testando: Semantic Chunking...',
      running_page: 'Testando: Page Chunking...',
      running_agentic: 'Testando: Agentic Chunking...',
      completed: 'Finalizado!',
      failed: 'Erro no benchmark',
    };
    return labels[status] || status;
  };

  const runBenchmark = async () => {
    if (!selectedAgentId) {
      toast({
        title: 'Agente Obrigatório',
        description: 'Selecione um agente para executar o benchmark.',
        variant: 'destructive',
      });
      return;
    }

    setIsRunning(true);
    setResult(null);
    setProgress(0);
    setStatusMessage('Iniciando...');

    try {
      // 1. Iniciar Job (retorna imediatamente com job_id)
      const startRes = await fetch(`${BACKEND_URL}/documents/benchmark/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          company_id: companyId,
          agent_id: selectedAgentId,
          sample_size: sampleSize,
          threshold: threshold,
          total_questions: totalQuestions,
        }),
      });

      if (!startRes.ok) {
        const error = await startRes.json();
        throw new Error(error.detail || 'Falha ao iniciar benchmark');
      }

      const { job_id } = await startRes.json();

      toast({
        title: '🔬 Benchmark Iniciado',
        description: `Job ${job_id.slice(0, 8)}... em execução`,
      });

      // 2. Loop de Polling (a cada 2s)
      const pollInterval = setInterval(async () => {
        try {
          const statusRes = await fetch(`${BACKEND_URL}/documents/benchmark/status/${job_id}`);
          if (!statusRes.ok) return;

          const data = await statusRes.json();
          setProgress(data.progress || 0);
          setStatusMessage(getStatusLabel(data.status));

          if (data.status === 'completed') {
            clearInterval(pollInterval);
            setResult(data.result);
            setIsRunning(false);

            // Parse winner
            const [winnerStrategy, winnerMode] = data.result.winner.split('_');
            const modeLabels: Record<string, string> = {
              standard: 'Standard',
              hyde: 'HyDE',
              hybrid: 'Hybrid',
            };
            const winnerLabel = `${getStrategyLabel(winnerStrategy)} (${modeLabels[winnerMode] || winnerMode})`;

            toast({
              title: '✅ Benchmark Concluído!',
              description: `🏆 Vencedor: ${winnerLabel} - ${(data.result.metadata.winner_true_rate || 0) * 100}% de precisão`,
            });
          } else if (data.status === 'failed') {
            clearInterval(pollInterval);
            setIsRunning(false);
            toast({
              title: 'Erro no Benchmark',
              description: data.result?.error || 'Falha desconhecida',
              variant: 'destructive',
            });
          }
        } catch (e) {
          console.error('Polling error:', e);
        }
      }, 2000);
    } catch (error) {
      console.error('Benchmark error:', error);
      toast({
        title: 'Erro',
        description: error instanceof Error ? error.message : 'Erro ao iniciar benchmark',
        variant: 'destructive',
      });
      setIsRunning(false);
    }
  };

  const getStrategyLabel = (strategy: string) => {
    const labels: Record<string, string> = {
      semantic: 'IA Semantica',
      page: 'Pagina a Pagina',
      recursive: 'Recursive',
      agentic: 'Agent Chunking',
    };
    return labels[strategy] || strategy;
  };

  const getStrategyBadge = (strategy: string, mode: string, isWinner: boolean) => {
    const winnerClass = isWinner
      ? 'ring-2 ring-yellow-400 ring-offset-2 ring-offset-[#1A1A1A]'
      : '';

    const strategyBadges: Record<string, { bg: string; text: string; border: string; icon: any }> =
    {
      semantic: {
        bg: 'bg-purple-500/20',
        text: 'text-purple-400',
        border: 'border-purple-500/30',
        icon: Brain,
      },
      page: {
        bg: 'bg-blue-500/20',
        text: 'text-blue-400',
        border: 'border-blue-500/30',
        icon: FileText,
      },
      recursive: {
        bg: 'bg-gray-500/20',
        text: 'text-gray-400',
        border: 'border-gray-500/30',
        icon: Zap,
      },
      agentic: {
        bg: 'bg-yellow-500/20',
        text: 'text-yellow-400',
        border: 'border-yellow-500/30',
        icon: Brain,
      },
    };

    const badge = strategyBadges[strategy] || strategyBadges.recursive;
    const Icon = badge.icon;
    const label =
      mode === 'hyde' ? `${getStrategyLabel(strategy)} + HyDE` : getStrategyLabel(strategy);

    return (
      <Badge
        className={`${badge.bg} ${badge.text} ${badge.border} ${winnerClass} flex items-center gap-1`}
      >
        {isWinner && <Trophy className="w-3 h-3 text-yellow-400" />}
        <Icon className="w-3 h-3" />
        {label}
        {mode === 'hyde' && <Sparkles className="w-3 h-3 ml-1 text-cyan-400" />}
      </Badge>
    );
  };

  const getScoreColor = (score: number) => {
    if (score >= 0.85) return 'text-green-400';
    if (score >= 0.7) return 'text-blue-400';
    if (score >= 0.5) return 'text-yellow-400';
    return 'text-red-400';
  };

  const getTrueRateColor = (rate: number) => {
    if (rate >= 0.85) return 'bg-green-500';
    if (rate >= 0.7) return 'bg-blue-500';
    if (rate >= 0.5) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  const getTrueRateWidth = (rate: number) => {
    return `${Math.round(rate * 100)}%`;
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button
          variant="outline"
          className="bg-gradient-to-r from-purple-500/10 to-blue-500/10 border-purple-500/30 hover:from-purple-500/20 hover:to-blue-500/20"
        >
          <BarChart3 className="mr-2 h-4 w-4" />
          📊 Benchmark Global
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-5xl max-h-[90vh] overflow-y-auto bg-[#1A1A1A] border-gray-800">
        <DialogHeader>
          <DialogTitle className="text-2xl font-bold bg-gradient-to-r from-purple-400 to-blue-400 bg-clip-text text-transparent">
            🏆 Benchmark de Estratégias × Modos de Recuperação
          </DialogTitle>
          <p className="text-sm text-gray-400 mt-2">
            Comparação técnica das estratégias de chunking com Standard vs HyDE vs Hybrid retrieval
          </p>
        </DialogHeader>

        <div className="space-y-4">
          {/* Configurações do Benchmark */}
          {!result && (
            <Card className="bg-[#0A0A0A] border-[#2D2D2D]">
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2 text-gray-200">
                  <Settings2 className="w-4 h-4 text-purple-400" />
                  Configuração do Teste
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Agente Selector */}
                  <div className="space-y-2">
                    <Label className="text-xs text-gray-400">Agente (Obrigatório)</Label>
                    <Select value={selectedAgentId} onValueChange={setSelectedAgentId}>
                      <SelectTrigger className="bg-[#1A1A1A] border-[#2D2D2D] text-white h-9">
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
                  </div>

                  {/* Sample Size */}
                  <div className="space-y-2">
                    <Label className="text-xs text-gray-400">Docs para Teste (Min 1)</Label>
                    <Input
                      type="number"
                      min={1}
                      max={10}
                      value={sampleSize}
                      onChange={(e) => setSampleSize(parseInt(e.target.value) || 1)}
                      className="bg-[#1A1A1A] border-[#2D2D2D] text-white h-9"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Total Questions */}
                  <div className="space-y-2">
                    <Label className="text-xs text-gray-400">Total de Perguntas (5-30)</Label>
                    <Input
                      type="number"
                      min={5}
                      max={30}
                      value={totalQuestions}
                      onChange={(e) => setTotalQuestions(parseInt(e.target.value) || 10)}
                      className="bg-[#1A1A1A] border-[#2D2D2D] text-white h-9"
                    />
                  </div>

                  {/* Threshold Slider */}
                  <div className="space-y-3">
                    <div className="flex justify-between">
                      <Label className="text-xs text-gray-400">Threshold de Similaridade</Label>
                      <span className="text-xs font-mono text-blue-400">
                        {threshold.toFixed(2)}
                      </span>
                    </div>
                    <Slider
                      value={[threshold]}
                      min={0.0}
                      max={1.0}
                      step={0.01}
                      onValueChange={(vals) => setThreshold(vals[0])}
                      className="py-1"
                    />
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Info Cards (Atualizado para mostrar valores dinâmicos) */}
          <div className="grid grid-cols-3 gap-3">
            <Card className="bg-gray-900/50 border-gray-800">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm text-gray-400">Threshold Configurado</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold text-blue-400">{threshold.toFixed(2)}</p>
              </CardContent>
            </Card>
            <Card className="bg-gray-900/50 border-gray-800">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm text-gray-400">Combinações</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold text-purple-400">4 × 3 = 12</p>
              </CardContent>
            </Card>
            <Card className="bg-gray-900/50 border-gray-800">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm text-gray-400">Perguntas/Teste</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold text-green-400">
                  {result?.metadata.total_questions || totalQuestions}
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Run Button / Progress */}
          {!result && (
            <div className="space-y-4">
              {isRunning ? (
                <div className="space-y-3">
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-400">{statusMessage}</span>
                    <span className="text-blue-400 font-mono">{progress}%</span>
                  </div>
                  <div className="h-3 w-full bg-secondary overflow-hidden rounded-full">
                    <div
                      className="h-full bg-blue-500 transition-all duration-500 ease-in-out"
                      style={{ width: `${progress}%` }}
                    />
                  </div>
                  <p className="text-xs text-gray-500 text-center">
                    O benchmark pode levar alguns minutos. Não feche esta janela.
                  </p>
                </div>
              ) : (
                <Button
                  onClick={runBenchmark}
                  className="w-full bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700"
                  size="lg"
                >
                  <BarChart3 className="mr-2 h-5 w-5" />
                  Iniciar Benchmark
                </Button>
              )}
            </div>
          )}

          {/* Results Matrix */}
          {result && (
            <div className="space-y-4">
              {/* Winner Banner */}
              <Card className="bg-gradient-to-r from-yellow-500/10 to-orange-500/10 border-yellow-500/30">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-yellow-400">
                    <Trophy className="w-5 h-5" />
                    Vencedor: {result.winner.replace('_', ' → ').toUpperCase()}
                  </CardTitle>
                  <CardDescription className="text-gray-300">
                    True Rate: {((result.metadata.winner_true_rate || 0) * 100).toFixed(1)}% |
                    Tempo: {result.metadata.execution_time_seconds.toFixed(1)}s
                  </CardDescription>
                </CardHeader>
              </Card>

              {/* Matrix Table */}
              <Card className="bg-gray-900/50 border-gray-800">
                <CardHeader>
                  <CardTitle className="text-lg">Matriz de Resultados</CardTitle>
                  <CardDescription>
                    Cada estratégia testada com 3 modos: Standard, HyDE e Hybrid (Dense + Sparse
                    BM25)
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead>
                        <tr className="border-b border-gray-800">
                          <th className="text-left p-3 text-sm font-semibold text-gray-400">
                            Estratégia
                          </th>
                          <th className="text-left p-3 text-sm font-semibold text-gray-400">
                            Modo
                          </th>
                          <th className="text-center p-3 text-sm font-semibold text-gray-400">
                            Avg Score
                          </th>
                          <th className="text-left p-3 text-sm font-semibold text-gray-400">
                            True Rate
                          </th>
                          <th className="text-center p-3 text-sm font-semibold text-purple-400">
                            🤖 LLM Judge
                          </th>
                          <th className="text-center p-3 text-sm font-semibold text-gray-400">
                            Status
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {result.strategies.map((strategy) => (
                          <Fragment key={strategy.type}>
                            {/* Standard Mode Row */}
                            <tr
                              className="border-b border-gray-800/50 hover:bg-gray-800/30"
                            >
                              <td className="p-3" rowSpan={3}>
                                {getStrategyBadge(strategy.type, 'standard', false)}
                              </td>
                              <td className="p-3">
                                <span className="text-sm text-gray-400">Standard</span>
                              </td>
                              <td className="p-3 text-center">
                                <span
                                  className={`font-mono font-semibold ${getScoreColor(strategy.modes.standard.avg_score)}`}
                                >
                                  {strategy.modes.standard.avg_score.toFixed(3)}
                                </span>
                              </td>
                              <td className="p-3">
                                <div className="flex items-center gap-2">
                                  <div className="flex-1 bg-gray-800 rounded-full h-6 overflow-hidden">
                                    <div
                                      className={`h-full ${getTrueRateColor(strategy.modes.standard.true_rate)} transition-all duration-500`}
                                      style={{
                                        width: getTrueRateWidth(strategy.modes.standard.true_rate),
                                      }}
                                    />
                                  </div>
                                  <span className="text-sm font-semibold text-gray-300 w-16">
                                    {Math.round(strategy.modes.standard.true_rate * strategy.count)}
                                    /{strategy.count}
                                  </span>
                                </div>
                              </td>
                              <td className="p-3 text-center">
                                <span className="font-mono font-semibold text-purple-400">
                                  {strategy.modes.standard.chunk_quality?.toFixed(1) || '-'}/5
                                </span>
                              </td>
                              <td className="p-3 text-center">
                                {result.winner === `${strategy.type}_standard` ? (
                                  <Badge className="bg-yellow-500/20 text-yellow-400 border-yellow-500/30">
                                    <Trophy className="w-3 h-3 mr-1" />
                                    Vencedor
                                  </Badge>
                                ) : (
                                  <span className="text-gray-600">-</span>
                                )}
                              </td>
                            </tr>

                            {/* HyDE Mode Row */}
                            <tr
                              className="border-b border-gray-800 hover:bg-cyan-900/10"
                            >
                              <td className="p-3">
                                <span className="text-sm text-cyan-400 flex items-center gap-1">
                                  <Sparkles className="w-3 h-3" />
                                  HyDE
                                </span>
                              </td>
                              <td className="p-3 text-center">
                                <span
                                  className={`font-mono font-semibold ${getScoreColor(strategy.modes.hyde.avg_score)}`}
                                >
                                  {strategy.modes.hyde.avg_score.toFixed(3)}
                                </span>
                              </td>
                              <td className="p-3">
                                <div className="flex items-center gap-2">
                                  <div className="flex-1 bg-gray-800 rounded-full h-6 overflow-hidden">
                                    <div
                                      className={`h-full ${getTrueRateColor(strategy.modes.hyde.true_rate)} transition-all duration-500`}
                                      style={{
                                        width: getTrueRateWidth(strategy.modes.hyde.true_rate),
                                      }}
                                    />
                                  </div>
                                  <span className="text-sm font-semibold text-gray-300 w-16">
                                    {Math.round(strategy.modes.hyde.true_rate * strategy.count)}/
                                    {strategy.count}
                                  </span>
                                </div>
                              </td>
                              <td className="p-3 text-center">
                                <span className="font-mono font-semibold text-purple-400">
                                  {strategy.modes.hyde.chunk_quality?.toFixed(1) || '-'}/5
                                </span>
                              </td>
                              <td className="p-3 text-center">
                                {result.winner === `${strategy.type}_hyde` ? (
                                  <Badge className="bg-yellow-500/20 text-yellow-400 border-yellow-500/30">
                                    <Trophy className="w-3 h-3 mr-1" />
                                    Vencedor
                                  </Badge>
                                ) : (
                                  <span className="text-gray-600">-</span>
                                )}
                              </td>
                            </tr>

                            {/* Hybrid Mode Row */}
                            <tr
                              className="border-b border-gray-800 hover:bg-gradient-to-r hover:from-purple-900/10 hover:to-blue-900/10"
                            >
                              <td className="p-3">
                                <span className="text-sm bg-gradient-to-r from-purple-400 to-blue-400 bg-clip-text text-transparent flex items-center gap-1 font-semibold">
                                  <Zap className="w-3 h-3 text-purple-400" />
                                  Hybrid
                                </span>
                              </td>
                              <td className="p-3 text-center">
                                <span
                                  className={`font-mono font-semibold ${getScoreColor(strategy.modes.hybrid.avg_score)}`}
                                >
                                  {strategy.modes.hybrid.avg_score.toFixed(3)}
                                </span>
                              </td>
                              <td className="p-3">
                                <div className="flex items-center gap-2">
                                  <div className="flex-1 bg-gray-800 rounded-full h-6 overflow-hidden">
                                    <div
                                      className={`h-full ${getTrueRateColor(strategy.modes.hybrid.true_rate)} transition-all duration-500`}
                                      style={{
                                        width: getTrueRateWidth(strategy.modes.hybrid.true_rate),
                                      }}
                                    />
                                  </div>
                                  <span className="text-sm font-semibold text-gray-300 w-16">
                                    {Math.round(strategy.modes.hybrid.true_rate * strategy.count)}/
                                    {strategy.count}
                                  </span>
                                </div>
                              </td>
                              <td className="p-3 text-center">
                                <span className="font-mono font-semibold text-purple-400">
                                  {strategy.modes.hybrid.chunk_quality?.toFixed(1) || '-'}/5
                                </span>
                              </td>
                              <td className="p-3 text-center">
                                {result.winner === `${strategy.type}_hybrid` ? (
                                  <Badge className="bg-yellow-500/20 text-yellow-400 border-yellow-500/30">
                                    <Trophy className="w-3 h-3 mr-1" />
                                    Vencedor
                                  </Badge>
                                ) : (
                                  <span className="text-gray-600">-</span>
                                )}
                              </td>
                            </tr>
                          </Fragment>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>

              {/* Legend */}
              <Card className="bg-gray-900/30 border-gray-800">
                <CardContent className="pt-6">
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <p className="text-gray-400 mb-2 font-semibold">📊 Métricas:</p>
                      <ul className="space-y-1 text-gray-500">
                        <li>
                          <strong className="text-gray-400">Avg Score:</strong> Similaridade média
                          do Top 1
                        </li>
                        <li>
                          <strong className="text-gray-400">True Rate:</strong> % doc correto com
                          score ≥ 0.70
                        </li>
                        <li>
                          <strong className="text-purple-400">🤖 LLM Judge:</strong> Avaliação da
                          qualidade dos chunks (1-5) por Claude Sonnet 4.5
                        </li>
                      </ul>
                    </div>
                    <div>
                      <p className="text-gray-400 mb-2 font-semibold">🔍 Modos:</p>
                      <ul className="space-y-1 text-gray-500">
                        <li>
                          <strong className="text-gray-400">Standard:</strong> Busca com embedding
                          da pergunta
                        </li>
                        <li>
                          <strong className="text-cyan-400">HyDE:</strong> Busca com embedding de
                          documento hipotético
                        </li>
                        <li>
                          <strong className="bg-gradient-to-r from-purple-400 to-blue-400 bg-clip-text text-transparent">
                            Hybrid:
                          </strong>{' '}
                          Fusão Dense + Sparse (BM25)
                        </li>
                      </ul>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Run Again */}
              <Button
                onClick={runBenchmark}
                disabled={isRunning}
                variant="outline"
                className="w-full"
              >
                <BarChart3 className="mr-2 h-4 w-4" />
                Executar Novamente
              </Button>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
