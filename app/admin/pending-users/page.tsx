'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { UserCheck, CheckCircle, XCircle, User } from 'lucide-react';
import { logSystemAction } from '@/lib/logger';

// Safe types (without sensitive fields)
interface SafeUser {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  status: string;
  company_id: string | null;
  created_at: string;
  phone: string | null;
  cpf: string;
}

interface SafeCompany {
  id: string;
  company_name: string;
  status: string;
}

export default function AdminPendingUsersPage() {
  const [users, setUsers] = useState<SafeUser[]>([]);
  const [companies, setCompanies] = useState<SafeCompany[]>([]);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState<string | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [usersResponse, companiesResponse] = await Promise.all([
        fetch('/api/admin/users'),
        fetch('/api/admin/companies?status=active'),
      ]);

      if (!usersResponse.ok || !companiesResponse.ok) {
        throw new Error('Erro ao carregar dados');
      }

      const usersData = await usersResponse.json();
      const companiesData = await companiesResponse.json();

      // Filter only pending users
      const pendingUsers = (usersData.users || []).filter((u: SafeUser) => u.status === 'pending');
      setUsers(pendingUsers);
      setCompanies(companiesData.companies || []);
    } catch (error) {
      console.error('Error loading data:', error);
    } finally {
      setLoading(false);
    }
  };

  const approveUser = async (userId: string, companyId: string) => {
    if (!companyId) {
      alert('Selecione uma empresa antes de aprovar');
      return;
    }

    setProcessing(userId);
    try {
      const user = users.find((u) => u.id === userId);
      const company = companies.find((c) => c.id === companyId);

      const response = await fetch('/api/admin/users/status', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ userId, action: 'approve', companyId }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || 'Failed to approve');
      }

      await logSystemAction({
        userId,
        companyId,
        actionType: 'USER_APPROVED',
        resourceType: 'user',
        resourceId: userId,
        details: {
          userEmail: user?.email,
          userName: `${user?.first_name} ${user?.last_name}`,
          companyName: company?.company_name,
        },
        status: 'success',
      });

      await loadData();
    } catch (error) {
      console.error('Error approving user:', error);

      await logSystemAction({
        actionType: 'USER_APPROVED',
        resourceType: 'user',
        resourceId: userId,
        details: { error: String(error) },
        status: 'error',
        errorMessage: 'Erro ao aprovar usuário',
      });

      alert('Erro ao aprovar usuário');
    } finally {
      setProcessing(null);
    }
  };

  const rejectUser = async (userId: string) => {
    if (!confirm('Tem certeza que deseja rejeitar este usuário?')) return;

    setProcessing(userId);
    try {
      const user = users.find((u) => u.id === userId);

      const response = await fetch('/api/admin/users/status', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ userId, action: 'reject' }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || 'Failed to reject');
      }

      await logSystemAction({
        userId,
        actionType: 'USER_REJECTED',
        resourceType: 'user',
        resourceId: userId,
        details: {
          userEmail: user?.email,
          userName: `${user?.first_name} ${user?.last_name}`,
        },
        status: 'success',
      });

      await loadData();
    } catch (error) {
      console.error('Error rejecting user:', error);

      await logSystemAction({
        actionType: 'USER_REJECTED',
        resourceType: 'user',
        resourceId: userId,
        details: { error: String(error) },
        status: 'error',
        errorMessage: 'Erro ao rejeitar usuário',
      });

      alert('Erro ao rejeitar usuário');
    } finally {
      setProcessing(null);
    }
  };

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-2">Aprovações Pendentes</h1>
        <p className="text-gray-400">Revise e aprove novos usuários no sistema</p>
      </div>

      {loading ? (
        <div className="text-white">Carregando usuários pendentes...</div>
      ) : (
        <div className="space-y-4">
          {users.map((user) => (
            <Card key={user.id} className="bg-[#1A1A1A] border-[#2D2D2D]">
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 bg-gradient-to-br from-orange-600 to-red-600 rounded-lg flex items-center justify-center">
                      <User className="w-6 h-6 text-white" />
                    </div>
                    <div>
                      <CardTitle className="text-white text-xl">
                        {user.first_name} {user.last_name}
                      </CardTitle>
                      <p className="text-sm text-gray-400 mt-1">{user.email}</p>
                    </div>
                  </div>
                  <Badge className="bg-orange-500/20 text-orange-400 border-orange-500/30">
                    Pendente
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                  <div>
                    <p className="text-xs text-gray-400 mb-1">CPF</p>
                    <p className="text-white font-medium">{user.cpf}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-400 mb-1">Telefone</p>
                    <p className="text-white font-medium">{user.phone || 'Não informado'}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-400 mb-1">Data de Cadastro</p>
                    <p className="text-white font-medium">
                      {new Date(user.created_at).toLocaleDateString('pt-BR')}
                    </p>
                  </div>
                </div>

                <div className="flex flex-col sm:flex-row gap-4">
                  <div className="flex-1">
                    <Select
                      onValueChange={(value) => {
                        const userElement = document.getElementById(`company-${user.id}`);
                        if (userElement) userElement.dataset.companyId = value;
                      }}
                    >
                      <SelectTrigger className="bg-[#2D2D2D] border-[#3D3D3D] text-white">
                        <SelectValue placeholder="Selecione uma empresa" />
                      </SelectTrigger>
                      <SelectContent className="bg-[#2D2D2D] border-[#3D3D3D]">
                        {companies.map((company) => (
                          <SelectItem key={company.id} value={company.id} className="text-white">
                            {company.company_name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="flex gap-2" id={`company-${user.id}`}>
                    <Button
                      onClick={() => {
                        const companyId = document.getElementById(`company-${user.id}`)?.dataset
                          .companyId;
                        if (companyId) approveUser(user.id, companyId);
                      }}
                      disabled={processing === user.id}
                      className="bg-green-600 hover:bg-green-700 text-white"
                    >
                      <CheckCircle className="w-4 h-4 mr-2" />
                      {processing === user.id ? 'Aprovando...' : 'Aprovar'}
                    </Button>
                    <Button
                      onClick={() => rejectUser(user.id)}
                      disabled={processing === user.id}
                      variant="destructive"
                    >
                      <XCircle className="w-4 h-4 mr-2" />
                      Rejeitar
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}

          {users.length === 0 && (
            <Card className="bg-[#1A1A1A] border-[#2D2D2D]">
              <CardContent className="py-12 text-center">
                <UserCheck className="w-12 h-12 text-gray-600 mx-auto mb-4" />
                <h3 className="text-white font-medium mb-2">Nenhuma aprovação pendente</h3>
                <p className="text-gray-400 text-sm">
                  Todos os usuários foram processados. Novos cadastros aparecerão aqui.
                </p>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
