'use client';

import { useState, useEffect } from 'react';
import { useAdminRole } from '@/hooks/useAdminRole';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
    DialogFooter,
} from '@/components/ui/dialog';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { toast } from 'sonner';
import {
    Plus,
    Pencil,
    Trash2,
    FileText,
    Eye,
    Loader2,
} from 'lucide-react';

interface LegalDocument {
    id: string;
    type: 'terms_of_use' | 'privacy_policy';
    title: string;
    content: string;
    version: string;
    is_active: boolean;
    created_at: string;
    updated_at: string;
}

const TYPE_LABELS: Record<string, string> = {
    terms_of_use: 'Termos de Uso',
    privacy_policy: 'Política de Privacidade',
};

export default function LegalDocumentsPage() {
    const { role, isLoading: roleLoading } = useAdminRole();
    const router = useRouter();
    const [documents, setDocuments] = useState<LegalDocument[]>([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);

    // Dialog states
    const [formOpen, setFormOpen] = useState(false);
    const [previewOpen, setPreviewOpen] = useState(false);
    const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
    const [editingDoc, setEditingDoc] = useState<LegalDocument | null>(null);
    const [previewDoc, setPreviewDoc] = useState<LegalDocument | null>(null);
    const [deleteDoc, setDeleteDoc] = useState<LegalDocument | null>(null);

    // Form state
    const [formData, setFormData] = useState({
        type: 'terms_of_use' as string,
        title: '',
        content: '',
        version: '',
        is_active: false,
    });

    useEffect(() => {
        if (!roleLoading && role !== 'master') {
            router.push('/admin/team');
        }
    }, [role, roleLoading, router]);

    useEffect(() => {
        if (role === 'master') {
            fetchDocuments();
        }
    }, [role]);

    const fetchDocuments = async () => {
        try {
            setLoading(true);
            const response = await fetch('/api/admin/legal-documents', {
                credentials: 'include',
            });
            if (response.ok) {
                const data = await response.json();
                setDocuments(data.documents || []);
            } else {
                toast.error('Erro ao carregar documentos');
            }
        } catch {
            toast.error('Erro ao conectar com o servidor');
        } finally {
            setLoading(false);
        }
    };

    const openCreateForm = () => {
        setEditingDoc(null);
        setFormData({
            type: 'terms_of_use',
            title: '',
            content: '',
            version: '',
            is_active: false,
        });
        setFormOpen(true);
    };

    const openEditForm = (doc: LegalDocument) => {
        setEditingDoc(doc);
        setFormData({
            type: doc.type,
            title: doc.title,
            content: doc.content,
            version: doc.version,
            is_active: doc.is_active,
        });
        setFormOpen(true);
    };

    const handleSubmit = async () => {
        if (!formData.title || !formData.content || !formData.version) {
            toast.error('Preencha todos os campos obrigatórios');
            return;
        }

        setSaving(true);
        try {
            const url = editingDoc
                ? `/api/admin/legal-documents/${editingDoc.id}`
                : '/api/admin/legal-documents';
            const method = editingDoc ? 'PUT' : 'POST';

            const response = await fetch(url, {
                method,
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify(formData),
            });

            if (response.ok) {
                toast.success(
                    editingDoc ? 'Documento atualizado com sucesso' : 'Documento criado com sucesso',
                );
                setFormOpen(false);
                fetchDocuments();
            } else {
                const data = await response.json();
                toast.error(data.error || 'Erro ao salvar documento');
            }
        } catch {
            toast.error('Erro ao conectar com o servidor');
        } finally {
            setSaving(false);
        }
    };

    const handleDelete = async () => {
        if (!deleteDoc) return;

        try {
            const response = await fetch(`/api/admin/legal-documents/${deleteDoc.id}`, {
                method: 'DELETE',
                credentials: 'include',
            });

            if (response.ok) {
                toast.success('Documento excluído com sucesso');
                setDeleteConfirmOpen(false);
                setDeleteDoc(null);
                fetchDocuments();
            } else {
                toast.error('Erro ao excluir documento');
            }
        } catch {
            toast.error('Erro ao conectar com o servidor');
        }
    };

    if (roleLoading || role !== 'master') {
        return (
            <div className="flex items-center justify-center min-h-[60vh]">
                <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
            </div>
        );
    }

    return (
        <div className="p-8">
            {/* Header */}
            <div className="flex items-center justify-between mb-8">
                <div>
                    <h1 className="text-2xl font-bold text-white flex items-center gap-3">
                        <FileText className="w-7 h-7 text-blue-500" />
                        Termos e Políticas
                    </h1>
                    <p className="text-gray-400 mt-1">
                        Gerencie os Termos de Uso e Política de Privacidade da plataforma
                    </p>
                </div>
                <Button
                    onClick={openCreateForm}
                    className="bg-blue-600 hover:bg-blue-700 text-white"
                >
                    <Plus className="w-4 h-4 mr-2" />
                    Novo Documento
                </Button>
            </div>

            {/* Documents Table */}
            {loading ? (
                <div className="flex items-center justify-center py-20">
                    <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
                </div>
            ) : documents.length === 0 ? (
                <div className="text-center py-20 bg-[#1A1A1A] rounded-lg border border-[#2D2D2D]">
                    <FileText className="w-12 h-12 text-gray-600 mx-auto mb-4" />
                    <p className="text-gray-400 text-lg">Nenhum documento cadastrado</p>
                    <p className="text-gray-500 text-sm mt-1">
                        Crie o primeiro Termos de Uso ou Política de Privacidade
                    </p>
                </div>
            ) : (
                <div className="bg-[#1A1A1A] rounded-lg border border-[#2D2D2D] overflow-hidden">
                    <table className="w-full">
                        <thead>
                            <tr className="border-b border-[#2D2D2D]">
                                <th className="text-left text-gray-400 text-sm font-medium px-6 py-4">Tipo</th>
                                <th className="text-left text-gray-400 text-sm font-medium px-6 py-4">Título</th>
                                <th className="text-left text-gray-400 text-sm font-medium px-6 py-4">Versão</th>
                                <th className="text-left text-gray-400 text-sm font-medium px-6 py-4">Status</th>
                                <th className="text-left text-gray-400 text-sm font-medium px-6 py-4">
                                    Última Atualização
                                </th>
                                <th className="text-right text-gray-400 text-sm font-medium px-6 py-4">Ações</th>
                            </tr>
                        </thead>
                        <tbody>
                            {documents.map((doc) => (
                                <tr
                                    key={doc.id}
                                    className="border-b border-[#2D2D2D] last:border-b-0 hover:bg-[#222222] transition-colors"
                                >
                                    <td className="px-6 py-4">
                                        <Badge
                                            variant="outline"
                                            className={
                                                doc.type === 'terms_of_use'
                                                    ? 'border-blue-500/50 text-blue-400'
                                                    : 'border-purple-500/50 text-purple-400'
                                            }
                                        >
                                            {TYPE_LABELS[doc.type]}
                                        </Badge>
                                    </td>
                                    <td className="px-6 py-4 text-white font-medium">{doc.title}</td>
                                    <td className="px-6 py-4 text-gray-300">{doc.version}</td>
                                    <td className="px-6 py-4">
                                        {doc.is_active ? (
                                            <Badge className="bg-green-500/20 text-green-400 border-green-500/30">
                                                Ativo
                                            </Badge>
                                        ) : (
                                            <Badge
                                                variant="outline"
                                                className="border-gray-600 text-gray-500"
                                            >
                                                Inativo
                                            </Badge>
                                        )}
                                    </td>
                                    <td className="px-6 py-4 text-gray-400 text-sm">
                                        {new Date(doc.updated_at).toLocaleDateString('pt-BR', {
                                            day: '2-digit',
                                            month: '2-digit',
                                            year: 'numeric',
                                            hour: '2-digit',
                                            minute: '2-digit',
                                        })}
                                    </td>
                                    <td className="px-6 py-4">
                                        <div className="flex items-center justify-end gap-2">
                                            <Button
                                                variant="ghost"
                                                size="icon"
                                                className="text-gray-400 hover:text-white hover:bg-[#2D2D2D]"
                                                onClick={() => {
                                                    setPreviewDoc(doc);
                                                    setPreviewOpen(true);
                                                }}
                                                title="Visualizar"
                                            >
                                                <Eye className="w-4 h-4" />
                                            </Button>
                                            <Button
                                                variant="ghost"
                                                size="icon"
                                                className="text-gray-400 hover:text-blue-400 hover:bg-blue-500/10"
                                                onClick={() => openEditForm(doc)}
                                                title="Editar"
                                            >
                                                <Pencil className="w-4 h-4" />
                                            </Button>
                                            <Button
                                                variant="ghost"
                                                size="icon"
                                                className="text-gray-400 hover:text-red-400 hover:bg-red-500/10"
                                                onClick={() => {
                                                    setDeleteDoc(doc);
                                                    setDeleteConfirmOpen(true);
                                                }}
                                                title="Excluir"
                                            >
                                                <Trash2 className="w-4 h-4" />
                                            </Button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            {/* Create/Edit Dialog */}
            <Dialog open={formOpen} onOpenChange={setFormOpen}>
                <DialogContent className="bg-[#1A1A1A] border-[#2D2D2D] text-white max-w-2xl max-h-[90vh] overflow-y-auto">
                    <DialogHeader>
                        <DialogTitle className="text-xl">
                            {editingDoc ? 'Editar Documento' : 'Novo Documento'}
                        </DialogTitle>
                        <DialogDescription className="text-gray-400">
                            {editingDoc ? 'Atualize as informações do documento legal.' : 'Crie um novo Termos de Uso ou Política de Privacidade.'}
                        </DialogDescription>
                    </DialogHeader>

                    <div className="space-y-4 py-4">
                        <div className="space-y-2">
                            <Label className="text-gray-300">Tipo</Label>
                            <Select
                                value={formData.type}
                                onValueChange={(value) => setFormData({ ...formData, type: value })}
                            >
                                <SelectTrigger className="bg-[#2D2D2D] border-[#3D3D3D] text-white">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent className="bg-[#2D2D2D] border-[#3D3D3D]">
                                    <SelectItem value="terms_of_use" className="text-white">
                                        Termos de Uso
                                    </SelectItem>
                                    <SelectItem value="privacy_policy" className="text-white">
                                        Política de Privacidade
                                    </SelectItem>
                                </SelectContent>
                            </Select>
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label className="text-gray-300">Título</Label>
                                <Input
                                    value={formData.title}
                                    onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                                    placeholder="Ex: Termos de Uso v2.0"
                                    className="bg-[#2D2D2D] border-[#3D3D3D] text-white"
                                />
                            </div>
                            <div className="space-y-2">
                                <Label className="text-gray-300">Versão</Label>
                                <Input
                                    value={formData.version}
                                    onChange={(e) => setFormData({ ...formData, version: e.target.value })}
                                    placeholder="Ex: 1.0"
                                    className="bg-[#2D2D2D] border-[#3D3D3D] text-white"
                                />
                            </div>
                        </div>

                        <div className="space-y-2">
                            <Label className="text-gray-300">Conteúdo</Label>
                            <Textarea
                                value={formData.content}
                                onChange={(e) => setFormData({ ...formData, content: e.target.value })}
                                placeholder="Digite o conteúdo do documento aqui..."
                                className="bg-[#2D2D2D] border-[#3D3D3D] text-white min-h-[300px] resize-y"
                            />
                        </div>

                        <div className="flex items-center space-x-2">
                            <Checkbox
                                id="is_active"
                                checked={formData.is_active}
                                onCheckedChange={(checked) =>
                                    setFormData({ ...formData, is_active: checked as boolean })
                                }
                                className="border-gray-600"
                            />
                            <label htmlFor="is_active" className="text-sm text-gray-300 cursor-pointer">
                                Ativar este documento (o documento ativo anterior do mesmo tipo será desativado)
                            </label>
                        </div>
                    </div>

                    <DialogFooter>
                        <Button
                            variant="outline"
                            onClick={() => setFormOpen(false)}
                            className="bg-transparent border-[#3D3D3D] text-gray-400 hover:text-white hover:bg-[#2D2D2D]"
                        >
                            Cancelar
                        </Button>
                        <Button
                            onClick={handleSubmit}
                            disabled={saving}
                            className="bg-blue-600 hover:bg-blue-700 text-white"
                        >
                            {saving ? (
                                <>
                                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                    Salvando...
                                </>
                            ) : editingDoc ? (
                                'Atualizar'
                            ) : (
                                'Criar'
                            )}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Preview Dialog */}
            <Dialog open={previewOpen} onOpenChange={setPreviewOpen}>
                <DialogContent className="bg-[#1A1A1A] border-[#2D2D2D] text-white max-w-2xl max-h-[80vh] overflow-y-auto">
                    <DialogHeader>
                        <DialogTitle className="text-xl flex items-center gap-2">
                            <Eye className="w-5 h-5 text-blue-500" />
                            {previewDoc?.title}
                        </DialogTitle>
                        <DialogDescription className="sr-only">Visualização do documento</DialogDescription>
                    </DialogHeader>
                    <div className="py-4">
                        <div className="flex items-center gap-2 mb-4">
                            <Badge
                                variant="outline"
                                className={
                                    previewDoc?.type === 'terms_of_use'
                                        ? 'border-blue-500/50 text-blue-400'
                                        : 'border-purple-500/50 text-purple-400'
                                }
                            >
                                {previewDoc?.type ? TYPE_LABELS[previewDoc.type] : ''}
                            </Badge>
                            <span className="text-gray-500 text-sm">v{previewDoc?.version}</span>
                            {previewDoc?.is_active && (
                                <Badge className="bg-green-500/20 text-green-400 border-green-500/30">
                                    Ativo
                                </Badge>
                            )}
                        </div>
                        <div className="bg-[#0A0A0A] rounded-lg p-6 border border-[#2D2D2D] whitespace-pre-wrap text-gray-300 text-sm leading-relaxed max-h-[50vh] overflow-y-auto">
                            {previewDoc?.content}
                        </div>
                    </div>
                </DialogContent>
            </Dialog>

            {/* Delete Confirmation Dialog */}
            <Dialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
                <DialogContent className="bg-[#1A1A1A] border-[#2D2D2D] text-white max-w-md">
                    <DialogHeader>
                        <DialogTitle className="text-xl text-red-400">Excluir Documento</DialogTitle>
                        <DialogDescription className="sr-only">Confirmar exclusão</DialogDescription>
                    </DialogHeader>
                    <p className="text-gray-300 py-4">
                        Tem certeza que deseja excluir{' '}
                        <span className="font-semibold text-white">&quot;{deleteDoc?.title}&quot;</span>?
                        <br />
                        <span className="text-sm text-gray-500">Esta ação não pode ser desfeita.</span>
                    </p>
                    <DialogFooter>
                        <Button
                            variant="outline"
                            onClick={() => setDeleteConfirmOpen(false)}
                            className="bg-transparent border-[#3D3D3D] text-gray-400 hover:text-white hover:bg-[#2D2D2D]"
                        >
                            Cancelar
                        </Button>
                        <Button
                            onClick={handleDelete}
                            className="bg-red-600 hover:bg-red-700 text-white"
                        >
                            Excluir
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
}
