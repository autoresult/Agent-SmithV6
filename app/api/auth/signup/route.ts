import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';
import { createUser, SignupData } from '@/lib/auth';
import { createSession } from '@/lib/session';
import { logSystemAction, getClientInfo } from '@/lib/logger';

// Service Role Client
const supabaseAdmin = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!,
  { auth: { persistSession: false } },
);

export async function POST(request: NextRequest) {
  const { ipAddress, userAgent } = getClientInfo(request);

  try {
    console.log('[SIGNUP] Starting signup process...');
    const body = await request.json();
    console.log('[SIGNUP] Request body received:', { ...body, password: '***' });

    const inviteToken = body.inviteToken;
    let inviteData: any = null;

    // Se tem invite token, validar
    if (inviteToken) {
      console.log('[SIGNUP] Validating invite token:', inviteToken);

      const { data: invite, error: inviteError } = await supabaseAdmin
        .from('invites')
        .select(
          'id, company_id, role, is_owner_invite, email, name, max_uses, current_uses, expires_at',
        )
        .eq('token', inviteToken)
        .single();

      if (inviteError || !invite) {
        console.log('[SIGNUP] Invalid invite token');
        return NextResponse.json({ error: 'Token de convite inválido' }, { status: 404 });
      }

      console.log('[SIGNUP] 🔍 Invite data retrieved:', {
        role: invite.role,
        is_owner_invite: invite.is_owner_invite,
        email: invite.email,
      });

      // Verificar expiração
      const expiresAt = new Date(invite.expires_at);
      if (expiresAt < new Date()) {
        console.log('[SIGNUP] Invite token expired');
        return NextResponse.json({ error: 'Token de convite expirado' }, { status: 410 });
      }

      // Verificar usos
      if (invite.current_uses >= invite.max_uses) {
        console.log('[SIGNUP] Invite token max uses reached');
        return NextResponse.json({ error: 'Token de convite já foi utilizado' }, { status: 451 });
      }

      // Verificar email nominal (se especificado)
      if (invite.email) {
        const inviteEmail = invite.email.toLowerCase().trim();
        const userEmail = body.email.toLowerCase().trim();

        if (inviteEmail !== userEmail) {
          console.log('[SIGNUP] Email mismatch. Expected:', inviteEmail, 'Got:', userEmail);
          return NextResponse.json(
            { error: 'Este convite é exclusivo para outro email' },
            { status: 403 },
          );
        }

        console.log('[SIGNUP] Nominal invite email validated:', inviteEmail);
      }

      inviteData = invite;
      console.log(
        '[SIGNUP] Valid invite for company:',
        invite.company_id,
        'role:',
        invite.role,
        'is_owner:',
        invite.is_owner_invite,
      );
    }

    // Prepare signup data
    // If invite exists:
    // - Use invite's role (admin_company or member)
    // - Extract is_owner_invite flag
    // - ALL users start as 'pending' (require approval)
    const signupData: SignupData = {
      firstName: body.firstName,
      lastName: body.lastName,
      cpf: body.cpf,
      phone: body.phone,
      email: body.email,
      birthDate: body.birthDate,
      password: body.password,
      termsAccepted: body.termsAccepted,
      acceptedTermsVersion: body.acceptedTermsVersion || null,
      companyId: inviteData?.company_id,
      status: 'pending', // ✅ CHANGED: Everyone needs approval
      role: inviteData?.role || undefined,
      isOwner: inviteData?.is_owner_invite || false, // ✅ NEW: Extract owner flag
    };

    console.log('[SIGNUP] 🎯 Data prepared with isOwner:', {
      role: signupData.role,
      isOwner: signupData.isOwner,
      status: signupData.status,
      email: signupData.email,
    });

    if (!signupData.termsAccepted) {
      console.log('[SIGNUP] Error: Terms not accepted');
      return NextResponse.json(
        { error: 'Você deve aceitar os termos e condições' },
        { status: 400 },
      );
    }

    if (
      !signupData.firstName ||
      !signupData.lastName ||
      !signupData.cpf ||
      !signupData.phone ||
      !signupData.email ||
      !signupData.birthDate ||
      !signupData.password
    ) {
      console.log('[SIGNUP] Error: Missing required fields');
      return NextResponse.json({ error: 'Todos os campos são obrigatórios' }, { status: 400 });
    }

    if (signupData.password.length < 6) {
      console.log('[SIGNUP] Error: Password too short');
      return NextResponse.json(
        { error: 'A senha deve ter no mínimo 6 caracteres' },
        { status: 400 },
      );
    }

    console.log('[SIGNUP] Calling createUser...');
    const { user, error } = await createUser(signupData);
    console.log('[SIGNUP] createUser result:', {
      hasUser: !!user,
      error: error,
      userEmail: user?.email,
    });

    if (error || !user) {
      console.log('[SIGNUP] Error from createUser:', error);

      await logSystemAction({
        actionType: 'SIGNUP',
        details: { email: signupData.email, error },
        ipAddress,
        userAgent,
        status: 'error',
        errorMessage: error || 'Erro ao criar usuário',
      });

      return NextResponse.json(
        { error: error || 'Erro ao criar usuário', debug: error },
        { status: 400 },
      );
    }

    const session = createSession(user, false);

    // Se usou invite, incrementar contador
    if (inviteData) {
      console.log('[SIGNUP] Incrementing invite usage counter');
      await supabaseAdmin
        .from('invites')
        .update({ current_uses: inviteData.current_uses + 1 })
        .eq('id', inviteData.id);
    }

    await logSystemAction({
      userId: user.id,
      companyId: user.company_id || undefined,
      actionType: 'SIGNUP',
      resourceType: 'user',
      resourceId: user.id,
      details: {
        email: user.email,
        firstName: user.first_name,
        lastName: user.last_name,
        viaInvite: !!inviteData,
      },
      ipAddress,
      userAgent,
      sessionId: session.userId,
      status: 'success',
    });

    const response = NextResponse.json(
      {
        success: true,
        user: {
          id: user.id,
          email: user.email,
          firstName: user.first_name,
          lastName: user.last_name,
        },
        session,
      },
      { status: 201 },
    );

    response.cookies.set('smith_user_session', JSON.stringify(session), {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      maxAge: 7 * 24 * 60 * 60,
      path: '/',
    });

    return response;
  } catch (error) {
    console.error('Signup API error:', error);

    await logSystemAction({
      actionType: 'ERROR_OCCURRED',
      details: { error: String(error), endpoint: '/api/auth/signup' },
      ipAddress,
      userAgent,
      status: 'error',
      errorMessage: 'Erro interno do servidor',
    });

    return NextResponse.json({ error: 'Erro interno do servidor' }, { status: 500 });
  }
}
