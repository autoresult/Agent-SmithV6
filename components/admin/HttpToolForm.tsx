'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { Plus, Trash2, Save, ArrowLeft, Loader2, Info } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
// 🔥 CORREÇÃO: Usar o hook padrão do projeto ao invés de 'sonner'
import { useToast } from '@/hooks/use-toast';

export interface HttpTool {
  id?: string;
  name: string;
  description: string;
  method: string;
  url: string;
  headers: { key: string; value: string }[];
  parameters: { name: string; type: string; description: string }[];
  body_template?: string; // Template JSON com {{param}} para injeção
}

interface Props {
  initialData?: HttpTool | null;
  agentId: string;
  onSave: (tool: HttpTool) => Promise<void>;
  onCancel: () => void;
}

export function HttpToolForm({ initialData, agentId, onSave, onCancel }: Props) {
  const [loading, setLoading] = useState(false);
  // 🔥 CORREÇÃO: Inicializar o hook
  const { toast } = useToast();

  const [formData, setFormData] = useState<HttpTool>(
    initialData
      ? {
          ...initialData,
          headers: Array.isArray(initialData.headers) ? initialData.headers : [],
          body_template: initialData.body_template || '',
        }
      : {
          name: '',
          description: '',
          method: 'GET',
          url: '',
          headers: [],
          parameters: [],
          body_template: '',
        },
  );

  const addHeader = () =>
    setFormData({ ...formData, headers: [...formData.headers, { key: '', value: '' }] });
  const removeHeader = (i: number) =>
    setFormData({ ...formData, headers: formData.headers.filter((_, idx) => idx !== i) });

  const addParam = () =>
    setFormData({
      ...formData,
      parameters: [...formData.parameters, { name: '', type: 'string', description: '' }],
    });
  const removeParam = (i: number) =>
    setFormData({ ...formData, parameters: formData.parameters.filter((_, idx) => idx !== i) });

  const handleSubmit = async () => {
    // Validação dos campos obrigatórios
    if (!formData.name || !formData.url || !formData.description) {
      // 🔥 CORREÇÃO: Sintaxe correta do use-toast
      toast({
        title: 'Campos obrigatórios',
        description: 'Por favor, preencha Nome, URL e Descrição.',
        variant: 'destructive',
      });
      return;
    }

    setLoading(true);
    try {
      await onSave(formData);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-right-4 duration-300">
      <div className="flex items-center gap-2 mb-6">
        <Button
          variant="ghost"
          size="sm"
          onClick={onCancel}
          className="text-gray-400 hover:text-white"
        >
          <ArrowLeft className="w-4 h-4 mr-1" /> Voltar
        </Button>
        <h3 className="text-lg font-semibold text-white">
          {initialData ? 'Editar Ferramenta' : 'Nova Ferramenta HTTP'}
        </h3>
      </div>

      <div className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <Label className="text-gray-300">Nome da Variável *</Label>
            <Input
              placeholder="ex: consultar_cep"
              value={formData.name}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  name: e.target.value.replace(/\s+/g, '_').toLowerCase(),
                })
              }
              className="bg-[#1A1A1A] border-[#3D3D3D] text-white font-mono"
            />
            <p className="text-xs text-gray-500 mt-1">
              O Agente usará como:{' '}
              <code className="bg-[#2D2D2D] px-1 rounded">{`{${formData.name || 'variavel'}}`}</code>
            </p>
          </div>
          <div>
            <Label className="text-gray-300">Método HTTP</Label>
            <Select
              value={formData.method}
              onValueChange={(v) => setFormData({ ...formData, method: v })}
            >
              <SelectTrigger className="bg-[#1A1A1A] border-[#3D3D3D] text-white">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-[#1A1A1A] border-[#3D3D3D]">
                {['GET', 'POST', 'PUT', 'DELETE', 'PATCH'].map((m) => (
                  <SelectItem key={m} value={m} className="text-white">
                    {m}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <div>
          <Label className="text-gray-300">Descrição / Gatilho *</Label>
          <Textarea
            placeholder="Descreva quando o agente deve usar esta ferramenta. Ex: Execute quando o usuário quiser saber o status de um pedido."
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            className="bg-[#1A1A1A] border-[#3D3D3D] text-white"
          />
        </div>

        <div>
          <Label className="text-gray-300">URL do Endpoint *</Label>
          <div className="flex gap-2">
            <Badge
              variant="outline"
              className="bg-[#2D2D2D] text-gray-400 border-[#3D3D3D] h-10 px-3 rounded-md flex items-center justify-center"
            >
              {formData.method}
            </Badge>
            <Input
              placeholder="https://api.exemplo.com/v1/resource/{id}"
              value={formData.url}
              onChange={(e) => setFormData({ ...formData, url: e.target.value })}
              className="bg-[#1A1A1A] border-[#3D3D3D] text-white flex-1"
            />
          </div>
          <p className="text-xs text-gray-500 mt-1 flex items-center gap-1">
            <Info className="w-3 h-3" /> Use{' '}
            <code className="text-purple-400">{`{parametro}`}</code> na URL para injetar valores
            dinâmicos.
          </p>
        </div>

        {/* Headers */}
        <Card className="bg-[#0D0D0D] border-[#2D2D2D]">
          <CardContent className="p-4 space-y-3">
            <div className="flex justify-between items-center">
              <Label className="text-white">Headers (Autenticação/Fixos)</Label>
              <Button
                size="sm"
                variant="ghost"
                onClick={addHeader}
                className="h-7 text-xs text-blue-400 hover:text-blue-300 hover:bg-blue-900/20"
              >
                <Plus className="w-3 h-3 mr-1" /> Adicionar
              </Button>
            </div>
            {formData.headers.map((header, index) => (
              <div key={index} className="flex gap-2 items-center">
                <Input
                  placeholder="Key (ex: Authorization)"
                  value={header.key}
                  onChange={(e) => {
                    const newHeaders = [...formData.headers];
                    newHeaders[index].key = e.target.value;
                    setFormData({ ...formData, headers: newHeaders });
                  }}
                  className="bg-[#1A1A1A] border-[#3D3D3D] text-white h-8"
                />
                <Input
                  placeholder="Value (ex: Bearer ...)"
                  value={header.value}
                  onChange={(e) => {
                    const newHeaders = [...formData.headers];
                    newHeaders[index].value = e.target.value;
                    setFormData({ ...formData, headers: newHeaders });
                  }}
                  className="bg-[#1A1A1A] border-[#3D3D3D] text-white h-8"
                />
                <Button
                  size="icon"
                  variant="ghost"
                  className="h-8 w-8 text-gray-500 hover:text-red-400"
                  onClick={() => removeHeader(index)}
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
              </div>
            ))}
            {formData.headers.length === 0 && (
              <p className="text-xs text-gray-600 text-center">Nenhum header configurado.</p>
            )}
          </CardContent>
        </Card>

        {/* Parâmetros */}
        <Card className="bg-[#0D0D0D] border-[#2D2D2D]">
          <CardContent className="p-4 space-y-3">
            <div className="flex justify-between items-center">
              <Label className="text-white">Parâmetros (Extraídos da Conversa)</Label>
              <Button
                size="sm"
                variant="ghost"
                onClick={addParam}
                className="h-7 text-xs text-blue-400 hover:text-blue-300 hover:bg-blue-900/20"
              >
                <Plus className="w-3 h-3 mr-1" /> Adicionar
              </Button>
            </div>
            {formData.parameters.map((param, index) => (
              <div key={index} className="flex gap-2 items-start">
                <Input
                  placeholder="Nome (ex: id)"
                  value={param.name}
                  onChange={(e) => {
                    const newParams = [...formData.parameters];
                    newParams[index].name = e.target.value;
                    setFormData({ ...formData, parameters: newParams });
                  }}
                  className="bg-[#1A1A1A] border-[#3D3D3D] text-white h-8 flex-1"
                />
                <Select
                  value={param.type}
                  onValueChange={(v) => {
                    const newParams = [...formData.parameters];
                    newParams[index].type = v;
                    setFormData({ ...formData, parameters: newParams });
                  }}
                >
                  <SelectTrigger className="bg-[#1A1A1A] border-[#3D3D3D] text-white h-8 w-[100px]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-[#1A1A1A] border-[#3D3D3D]">
                    <SelectItem value="string" className="text-white">
                      Texto
                    </SelectItem>
                    <SelectItem value="integer" className="text-white">
                      Número
                    </SelectItem>
                    <SelectItem value="boolean" className="text-white">
                      Booleano
                    </SelectItem>
                  </SelectContent>
                </Select>
                <Input
                  placeholder="Descrição para a IA (Opcional)"
                  value={param.description}
                  onChange={(e) => {
                    const newParams = [...formData.parameters];
                    newParams[index].description = e.target.value;
                    setFormData({ ...formData, parameters: newParams });
                  }}
                  className="bg-[#1A1A1A] border-[#3D3D3D] text-white h-8 flex-[2]"
                />
                <Button
                  size="icon"
                  variant="ghost"
                  className="h-8 w-8 text-gray-500 hover:text-red-400"
                  onClick={() => removeParam(index)}
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
              </div>
            ))}
            {formData.parameters.length === 0 && (
              <p className="text-xs text-gray-600 text-center">
                Nenhum parâmetro. A ferramenta será chamada sem argumentos.
              </p>
            )}
          </CardContent>
        </Card>

        {/* Body Template - apenas para POST/PUT/PATCH */}
        {['POST', 'PUT', 'PATCH'].includes(formData.method) && (
          <Card className="bg-[#0D0D0D] border-[#2D2D2D]">
            <CardContent className="p-4 space-y-3">
              <div className="flex justify-between items-center">
                <Label className="text-white">Template do Corpo (Body)</Label>
                <Badge variant="outline" className="text-xs text-purple-400 border-purple-400/50">
                  Opcional
                </Badge>
              </div>
              <Textarea
                placeholder={`{
  "user": {
    "name": "{{nome}}",
    "email": "{{email}}"
  },
  "action": "create",
  "timestamp": "{{data}}"
}`}
                value={formData.body_template || ''}
                onChange={(e) => setFormData({ ...formData, body_template: e.target.value })}
                className="bg-[#1A1A1A] border-[#3D3D3D] text-white font-mono text-sm min-h-[150px]"
                rows={8}
              />
              <div className="space-y-1">
                <p className="text-xs text-gray-500 flex items-center gap-1">
                  <Info className="w-3 h-3" />
                  Use <code className="text-purple-400">{`{{parametro}}`}</code> para injetar
                  valores extraídos da conversa.
                </p>
                <p className="text-xs text-gray-600">
                  Se vazio, os parâmetros serão enviados como JSON simples no corpo da requisição.
                </p>
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Botão Salvar Ferramenta - Fixo no fim */}
      <div className="pt-4 border-t border-[#2D2D2D]">
        <Button
          onClick={handleSubmit}
          disabled={loading}
          className="w-full bg-blue-600 hover:bg-blue-700 text-white gap-2"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
          Salvar Ferramenta
        </Button>
      </div>
    </div>
  );
}
