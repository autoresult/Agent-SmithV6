// app/admin/team/page.tsx

'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import {
  Users,
  UserPlus,
  CheckCircle,
  Copy,
  Clock,
  Shield,
  Crown,
  XCircle,
  PlayCircle,
} from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { useAdminRole } from '@/hooks/useAdminRole';
import { getAdminSession } from '@/lib/adminSession';
import { useRouter } from 'next/navigation';

interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  status: string;
  is_owner?: boolean;
  created_at: string;
}

export default function TeamManagementPage() {
  const { role, companyId, isOwner, isLoading: roleLoading } = useAdminRole();
  const router = useRouter();
  const { toast } = useToast();

  // Pega o ID do usuário logado da sessão admin
  const adminSession = typeof window !== 'undefined' ? getAdminSession() : null;
  const currentUserId = adminSession?.adminId || null;

  const [users, setUsers] = useState<User[]>([]);
  const [pendingUsers, setPendingUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);

  // Estados do Convite
  const [generating, setGenerating] = useState(false);
  const [inviteLink, setInviteLink] = useState('');
  const [showInviteDialog, setShowInviteDialog] = useState(false);
  const [selectedRole, setSelectedRole] = useState<'member' | 'admin_company'>('member');
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteName, setInviteName] = useState('');

  useEffect(() => {
    if (!roleLoading) {
      if (role !== 'company_admin' && role !== 'master') {
        router.push('/admin');
        return;
      }
      loadTeam();
    }
  }, [role, roleLoading, companyId, isOwner]);

  const loadTeam = async () => {
    if (!companyId) return;
    setLoading(true);

    try {
      const response = await fetch('/api/admin/team');
      if (!response.ok) throw new Error('Failed to load team');

      const data = await response.json();
      setUsers(data.users || []);
      setPendingUsers(data.pendingUsers || []);
    } catch (error) {
      console.error('Error loading team:', error);
      toast({
        title: 'Erro',
        description: 'Falha ao carregar equipe',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  const generateInvite = async () => {
    if (!inviteEmail || !inviteEmail.includes('@')) {
      toast({
        title: 'Erro',
        description: 'Por favor, informe um email válido',
        variant: 'destructive',
      });
      return;
    }

    setGenerating(true);
    try {
      const response = await fetch('/api/invites/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          role: selectedRole,
          companyId: companyId,
          email: inviteEmail,
          name: inviteName || null,
          isOwner: false, // Company Admin NUNCA cria outro Owner por aqui
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Falha ao gerar convite');
      }

      setInviteLink(data.inviteLink);
      setShowInviteDialog(true);

      setInviteEmail('');
      setInviteName('');

      toast({
        title: 'Convite gerado!',
        description: `Convite enviado para ${inviteEmail}`,
      });
    } catch (error: any) {
      console.error('Error generating invite:', error);
      toast({
        title: 'Erro',
        description: error.message || 'Falha ao gerar convite',
        variant: 'destructive',
      });
    } finally {
      setGenerating(false);
    }
  };

  const copyToClipboard = () => {
    navigator.clipboard.writeText(inviteLink);
    toast({
      title: 'Copiado!',
      description: 'Link copiado para área de transferência',
    });
  };

  const approveUser = async (userId: string) => {
    try {
      const response = await fetch('/api/admin/team/approve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ userId }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Falha ao aprovar usuário');
      }

      toast({
        title: 'Usuário aprovado!',
        description: data.message,
      });

      await loadTeam();
    } catch (error: any) {
      console.error('Error approving user:', error);
      toast({
        title: 'Erro',
        description: error.message || 'Falha ao aprovar usuário',
        variant: 'destructive',
      });
    }
  };

  // Nova função para atualizar status (Suspender/Ativar)
  const updateUserStatus = async (userId: string, newStatus: 'active' | 'suspended') => {
    try {
      const response = await fetch('/api/admin/users/status', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ userId, status: newStatus }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || 'Failed to update status');
      }

      toast({
        title: newStatus === 'suspended' ? 'Usuário suspenso' : 'Usuário reativado',
        description: `O status do usuário foi alterado para ${newStatus === 'suspended' ? 'suspenso' : 'ativo'}.`,
        variant: newStatus === 'suspended' ? 'destructive' : 'default',
      });

      await loadTeam();
    } catch (error: any) {
      console.error('Error updating user status:', error);
      toast({
        title: 'Erro',
        description: 'Falha ao atualizar status do usuário',
        variant: 'destructive',
      });
    }
  };

  const getRoleBadge = (user: User) => {
    if (user.is_owner) {
      return (
        <Badge className="bg-yellow-500/20 text-yellow-400 border-yellow-500/30 gap-1">
          <Crown className="w-3 h-3" /> Dono
        </Badge>
      );
    }

    if (user.role === 'admin_company' || user.role === 'owner' || user.role === 'admin') {
      return (
        <Badge className="bg-purple-500/20 text-purple-400 border-purple-500/30 gap-1">
          <Shield className="w-3 h-3" /> Admin
        </Badge>
      );
    }

    return <Badge className="bg-gray-500/20 text-gray-400 border-gray-500/30">Membro</Badge>;
  };

  // Lógica para determinar se o usuário atual pode gerenciar o alvo
  const canManageUser = (targetUser: User) => {
    // Não pode gerenciar a si mesmo
    if (targetUser.id === currentUserId) return false;

    // Master pode tudo
    if (role === 'master') return true;

    // Owner pode gerenciar qualquer um que NÃO seja owner
    if (isOwner) {
      return !targetUser.is_owner;
    }

    // Admin Company (que não é owner) pode gerenciar apenas membros
    if (role === 'company_admin') {
      return targetUser.role === 'member';
    }

    return false;
  };

  const canInviteAdmin = role === 'master' || (role === 'company_admin' && isOwner);

  if (roleLoading || loading) {
    return (
      <div className="p-8 flex items-center justify-center h-full">
        <div className="text-white">Carregando equipe...</div>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-2">Gerenciar Equipe</h1>
        <p className="text-gray-400">Convide e gerencie os membros da sua empresa</p>
      </div>

      {/* CARD DE CONVITE */}
      <Card className="bg-[#1A1A1A] border-[#2D2D2D] mb-8">
        <CardHeader>
          <CardTitle className="text-white flex items-center gap-2">
            <UserPlus className="w-5 h-5 text-blue-400" />
            Convidar Novo Colaborador
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-300">Email *</label>
                <Input
                  type="email"
                  placeholder="email@empresa.com"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  className="bg-[#0D0D0D] border-[#2D2D2D] text-white"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-300">Nome (Opcional)</label>
                <Input
                  type="text"
                  placeholder="Nome do colaborador"
                  value={inviteName}
                  onChange={(e) => setInviteName(e.target.value)}
                  className="bg-[#0D0D0D] border-[#2D2D2D] text-white"
                />
              </div>
            </div>

            <div className="space-y-4">
              <label className="text-sm font-medium text-gray-300">Nível de Acesso:</label>
              <div className="space-y-3">
                <label
                  className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                    selectedRole === 'member'
                      ? 'bg-blue-900/20 border-blue-500/50'
                      : 'bg-[#0D0D0D] border-[#2D2D2D] hover:border-gray-600'
                  }`}
                >
                  <input
                    type="radio"
                    name="role"
                    value="member"
                    checked={selectedRole === 'member'}
                    onChange={() => setSelectedRole('member')}
                    className="w-4 h-4 text-blue-600"
                  />
                  <div>
                    <p className="text-white font-medium">Membro</p>
                    <p className="text-xs text-gray-500">Acesso apenas ao chat</p>
                  </div>
                </label>

                {canInviteAdmin && (
                  <label
                    className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                      selectedRole === 'admin_company'
                        ? 'bg-purple-900/20 border-purple-500/50'
                        : 'bg-[#0D0D0D] border-[#2D2D2D] hover:border-gray-600'
                    }`}
                  >
                    <input
                      type="radio"
                      name="role"
                      value="admin_company"
                      checked={selectedRole === 'admin_company'}
                      onChange={() => setSelectedRole('admin_company')}
                      className="w-4 h-4 text-purple-600"
                    />
                    <div>
                      <p className="text-white font-medium">Administrador</p>
                      <p className="text-xs text-gray-500">
                        Acesso total às configurações (menos billing)
                      </p>
                    </div>
                  </label>
                )}
              </div>
            </div>
          </div>

          <Button
            onClick={generateInvite}
            disabled={generating}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white"
          >
            {generating ? 'Gerando e Enviando...' : 'Gerar Convite'}
          </Button>
        </CardContent>
      </Card>

      <Dialog open={showInviteDialog} onOpenChange={setShowInviteDialog}>
        <DialogContent className="bg-[#1A1A1A] border-[#2D2D2D] text-white">
          <DialogHeader>
            <DialogTitle>Convite Gerado</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <p className="text-sm text-green-400">
              ✅ E-mail enviado para <strong>{inviteEmail}</strong>
            </p>
            <p className="text-xs text-gray-400">
              Caso o email falhe, você pode copiar o link abaixo manualmente:
            </p>
            <div className="flex gap-2">
              <Input
                value={inviteLink}
                readOnly
                className="bg-[#0D0D0D] border-[#2D2D2D] text-white text-sm"
              />
              <Button onClick={copyToClipboard} className="bg-blue-600 hover:bg-blue-700">
                <Copy className="w-4 h-4" />
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {pendingUsers.length > 0 && (
        <Card className="bg-[#1A1A1A] border-[#2D2D2D] mb-8 border-l-4 border-l-yellow-500">
          <CardHeader>
            <CardTitle className="text-white flex items-center gap-2">
              <Clock className="w-5 h-5 text-yellow-400" />
              Aprovações Pendentes ({pendingUsers.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {pendingUsers.map((user) => (
                <div
                  key={user.id}
                  className="flex items-center justify-between p-4 bg-[#0D0D0D] rounded-lg border border-[#2D2D2D]"
                >
                  <div>
                    <p className="text-white font-medium">
                      {user.first_name} {user.last_name}
                    </p>
                    <p className="text-sm text-gray-400">{user.email}</p>
                    <div className="flex gap-2 mt-1">
                      {getRoleBadge(user)}
                      <span className="text-xs text-gray-500 flex items-center">
                        • Solicitado em {new Date(user.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                  <Button
                    onClick={() => approveUser(user.id)}
                    className="bg-green-600 hover:bg-green-700 text-white size-sm"
                  >
                    <CheckCircle className="w-4 h-4 mr-2" /> Aprovar
                  </Button>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* LISTA DE EQUIPE (ATIVOS E SUSPENSOS) */}
      <Card className="bg-[#1A1A1A] border-[#2D2D2D]">
        <CardHeader>
          <CardTitle className="text-white flex items-center gap-2">
            <Users className="w-5 h-5" />
            Equipe ({users.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {users.map((user) => (
              <div
                key={user.id}
                className="flex items-center justify-between p-4 bg-[#0D0D0D] rounded-lg border border-[#2D2D2D]"
              >
                <div className="flex items-center gap-4">
                  <div
                    className={`w-10 h-10 rounded-full flex items-center justify-center text-white font-bold ${
                      user.status === 'suspended'
                        ? 'bg-red-900/50'
                        : 'bg-gradient-to-br from-gray-700 to-gray-600'
                    }`}
                  >
                    {user.first_name?.[0]}
                    {user.last_name?.[0]}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <p
                        className={`font-medium ${user.status === 'suspended' ? 'text-red-400 line-through' : 'text-white'}`}
                      >
                        {user.first_name} {user.last_name}
                      </p>
                      {getRoleBadge(user)}
                    </div>
                    <p className="text-sm text-gray-400">{user.email}</p>
                  </div>
                </div>

                <div className="flex items-center gap-4">
                  <div className="text-right">
                    <p className="text-xs text-gray-500">
                      Desde {new Date(user.created_at).toLocaleDateString()}
                    </p>
                    <p
                      className={`text-xs ${user.status === 'suspended' ? 'text-red-500' : 'text-green-500'}`}
                    >
                      ● {user.status === 'suspended' ? 'Suspenso' : 'Ativo'}
                    </p>
                  </div>

                  {/* Botões de Ação */}
                  {canManageUser(user) && (
                    <div className="flex gap-2">
                      {user.status === 'suspended' ? (
                        <Button
                          size="icon"
                          variant="ghost"
                          onClick={() => updateUserStatus(user.id, 'active')}
                          className="hover:bg-green-900/20 text-green-500"
                          title="Reativar Usuário"
                        >
                          <PlayCircle className="w-5 h-5" />
                        </Button>
                      ) : (
                        <Button
                          size="icon"
                          variant="ghost"
                          onClick={() => updateUserStatus(user.id, 'suspended')}
                          className="hover:bg-red-900/20 text-red-500"
                          title="Suspender Usuário"
                        >
                          <XCircle className="w-5 h-5" />
                        </Button>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))}

            {users.length === 0 && (
              <div className="text-center py-12 text-gray-500">Nenhum membro encontrado.</div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
