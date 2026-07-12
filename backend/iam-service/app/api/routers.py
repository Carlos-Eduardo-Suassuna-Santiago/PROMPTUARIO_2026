from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.domain.models.schemas import (
    AssignRoleRequest,
    ChangePasswordRequest,
    DeactivateUserRequest,
    DoctorListResponse,
    DoctorResponse,
    ForgotPasswordRequest,
    LoginRequest,
    PatientRegisterRequest,
    RefreshRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserCreate,
    UserListResponse,
    UserResponse,
    UserUpdate,
)
from app.domain.models.user import User
from app.domain.services.auth_service import AuthService, UserService
from app.infrastructure.repositories.user_repository import UserRepository
from shared.middleware.auth import make_auth_dependency

get_current_user, require_roles = make_auth_dependency(
    settings.JWT_SECRET_KEY, settings.JWT_ALGORITHM
)

auth_router = APIRouter(prefix="/auth", tags=["Auth"])
users_router = APIRouter(prefix="/users", tags=["Users"])


def _get_services(request: Request):
    return request.app.state.session_factory, request.app.state.publisher, request.app.state.redis


# ─── Auth endpoints ───────────────────────────────────────────────────────────

@auth_router.post("/login", response_model=TokenResponse, summary="Autenticar usuário")
async def login(body: LoginRequest, request: Request):
    sf, pub, redis = _get_services(request)
    async with sf() as session:
        svc = AuthService(session, pub, redis)
        svc._ip_address = request.client.host if request.client else None
        return await svc.login(body.email, body.password)


@auth_router.post("/refresh", response_model=TokenResponse, summary="Renovar access token")
async def refresh(body: RefreshRequest, request: Request):
    sf, pub, redis = _get_services(request)
    async with sf() as session:
        svc = AuthService(session, pub, redis)
        return await svc.refresh_tokens(body.refresh_token)


@auth_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Encerrar sessão")
async def logout(
    body: RefreshRequest,
    request: Request,
    user=Depends(get_current_user),
):
    sf, pub, redis = _get_services(request)
    raw_token = request.headers.get("Authorization", "").replace("Bearer ", "")
    async with sf() as session:
        svc = AuthService(session, pub, redis)
        await svc.logout(body.refresh_token, raw_token)


@auth_router.post(
    "/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Alterar senha",
)
async def change_password(
    body: ChangePasswordRequest,
    request: Request,
    user=Depends(get_current_user),
):
    sf, pub, redis = _get_services(request)
    async with sf() as session:
        svc = AuthService(session, pub, redis)
        await svc.change_password(user.sub, body.current_password, body.new_password)


@auth_router.post(
    "/forgot-password",
    summary="Solicitar redefinição de senha",
)
async def forgot_password(body: ForgotPasswordRequest, request: Request):
    sf, pub, redis = _get_services(request)
    async with sf() as session:
        svc = AuthService(session, pub, redis)
        return await svc.forgot_password(body.email)


@auth_router.post(
    "/reset-password",
    summary="Redefinir senha com token",
)
async def reset_password(body: ResetPasswordRequest, request: Request):
    sf, pub, redis = _get_services(request)
    async with sf() as session:
        svc = AuthService(session, pub, redis)
        return await svc.reset_password(body.token, body.new_password)


@auth_router.post(
    "/register-patient",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Auto-cadastro de paciente",
)
async def register_patient(body: PatientRegisterRequest, request: Request):
    sf, pub, _ = _get_services(request)
    async with sf() as session:
        svc = UserService(session, pub)
        user = await svc.register_patient(
            email=body.email,
            password=body.password,
            full_name=body.full_name,
            cpf=body.cpf,
            date_of_birth=body.date_of_birth,
            gender=body.gender,
            phone=body.phone,
        )
        return UserResponse.model_validate(user)


# ─── Users endpoints ──────────────────────────────────────────────────────────

@users_router.get(
    "",
    response_model=UserListResponse,
    summary="Listar usuários",
    dependencies=[Depends(require_roles("ADMIN"))],
)
async def list_users(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    role: str | None = Query(None),
    is_active: bool | None = Query(None),
):
    sf, pub, _ = _get_services(request)
    async with sf() as session:
        svc = UserService(session, pub)
        items, total = await svc.list_users(page, size, role, is_active)
        return UserListResponse(
            items=[UserResponse.model_validate(u) for u in items],
            total=total,
            page=page,
            size=size,
        )


@users_router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar usuário",
    dependencies=[Depends(require_roles("ADMIN", "ATTENDANT"))],
)
async def create_user(body: UserCreate, request: Request, current_user=Depends(get_current_user)):
    sf, pub, _ = _get_services(request)
    async with sf() as session:
        svc = UserService(session, pub)
        # ATTENDANT só pode criar usuários com role PATIENT
        if current_user.role == "ATTENDANT" and body.role != "PATIENT":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Atendente só pode cadastrar pacientes",
            )
        user = await svc.create_user(body.email, body.password, body.full_name, body.role, body.cpf)
        return UserResponse.model_validate(user)


@users_router.get("/me", response_model=UserResponse, summary="Dados do usuário autenticado")
async def get_me(request: Request, user=Depends(get_current_user)):
    sf, pub, _ = _get_services(request)
    async with sf() as session:
        svc = UserService(session, pub)
        u = await svc.get_user(user.sub)
        return UserResponse.model_validate(u)


@users_router.get(
    "/doctors",
    response_model=DoctorListResponse,
    summary="Listar médicos disponíveis",
)
async def list_doctors(request: Request, user=Depends(get_current_user)):
    """Lista todos os usuários com role DOCTOR (acessível para pacientes)."""
    sf, pub, _ = _get_services(request)
    async with sf() as session:
        repo = UserRepository(session)
        result = await session.execute(
            select(User).where(User.role == "DOCTOR", User.is_active == True)
        )
        doctors = result.scalars().all()
        return DoctorListResponse(
            items=[DoctorResponse.model_validate(d) for d in doctors],
            total=len(doctors),
        )


@users_router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Buscar usuário por ID",
    dependencies=[Depends(require_roles("ADMIN"))],
)
async def get_user(user_id: str, request: Request):
    sf, pub, _ = _get_services(request)
    async with sf() as session:
        svc = UserService(session, pub)
        return UserResponse.model_validate(await svc.get_user(user_id))


@users_router.put("/{user_id}", response_model=UserResponse, summary="Atualizar usuário")
async def update_user(
    user_id: str,
    body: UserUpdate,
    request: Request,
    current_user=Depends(get_current_user),
):
    # Users can only edit themselves unless ADMIN
    if current_user.role != "ADMIN" and current_user.sub != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado")
    sf, pub, _ = _get_services(request)
    async with sf() as session:
        svc = UserService(session, pub)
        return UserResponse.model_validate(
            await svc.update_user(user_id, body.full_name, body.email, body.cpf)
        )


@users_router.put(
    "/{user_id}/role",
    response_model=UserResponse,
    summary="Atribuir role",
    dependencies=[Depends(require_roles("ADMIN"))],
)
async def assign_role(user_id: str, body: AssignRoleRequest, request: Request):
    sf, pub, _ = _get_services(request)
    async with sf() as session:
        svc = UserService(session, pub)
        return UserResponse.model_validate(await svc.assign_role(user_id, body.role))


@users_router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desativar usuário",
    dependencies=[Depends(require_roles("ADMIN"))],
)
async def deactivate_user(
    user_id: str,
    body: DeactivateUserRequest,
    request: Request,
    current_user=Depends(get_current_user),
):
    sf, pub, _ = _get_services(request)
    async with sf() as session:
        svc = UserService(session, pub)
        await svc.deactivate_user(user_id, body.reason, current_user.sub)