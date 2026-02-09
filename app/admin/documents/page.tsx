'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { FileText } from 'lucide-react';
import { useAdminRole } from '@/hooks/useAdminRole';
import { DocumentManagementModal } from '@/components/admin/DocumentManagementModal';

export default function DocumentsPage() {
  const { role, companyId, isLoading } = useAdminRole();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && role !== 'company_admin') {
      router.push('/admin');
    }
  }, [role, isLoading, router]);

  if (isLoading) {
    return (
      <div className="p-8">
        <div className="text-white">Carregando...</div>
      </div>
    );
  }

  if (!companyId) {
    return (
      <div className="p-8">
        <div className="text-red-400">Erro: Empresa não encontrada</div>
      </div>
    );
  }

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-2 flex items-center gap-3">
          <FileText className="w-8 h-8" />
          Base de Conhecimento
        </h1>
        <p className="text-gray-400">
          Faça upload de documentos para treinar seu agente com informações específicas da sua
          empresa
        </p>
      </div>

      <Card className="bg-[#1A1A1A] border-[#2D2D2D]">
        <CardHeader>
          <CardTitle className="text-white">Gerenciar Documentos</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-gray-400 text-sm mb-6">
            Envie PDFs, documentos e outros arquivos que o agente deve conhecer. O sistema
            processará automaticamente e utilizará essas informações para responder aos clientes.
          </p>
          <DocumentManagementModal companyId={companyId} companyName="Sua Empresa" />
        </CardContent>
      </Card>

      <div className="mt-6 p-4 bg-green-500/10 border border-green-500/30 rounded-lg">
        <p className="text-sm text-green-400">
          ✨ <strong>Suportado:</strong> PDFs, arquivos de texto, planilhas e apresentações. O
          agente irá indexar e usar essas informações para responder perguntas.
        </p>
      </div>
    </div>
  );
}
