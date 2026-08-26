from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from rag_shared.config import Settings, get_settings
from rag_shared.core.deps import CurrentUser, get_current_user
from rag_shared.core.errors import AppError
from rag_shared.db.session import get_db
from rag_shared.models.enums import UserRole, UserStatus
from rag_shared.schemas.api import UserResponse
from rag_shared.services.audit import write_audit_log
from rag_shared.services.users import get_user_by_email, to_user_response

router = APIRouter(prefix="/auth", tags=["auth"])

oauth = OAuth()


def _configure_oauth(settings: Settings) -> None:
    if settings.google_client_id and settings.google_client_secret:
        oauth.register(
            name="google",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )


@router.get("/google/login")
async def google_login(request: Request, settings: Settings = Depends(get_settings)):
    _configure_oauth(settings)
    if "google" not in oauth._clients:
        raise AppError(
            "INTERNAL_ERROR",
            "Google OAuth is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.",
            status_code=503,
        )
    redirect_uri = settings.oauth_redirect_uri
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/google/callback")
async def google_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    _configure_oauth(settings)
    if "google" not in oauth._clients:
        raise AppError("INTERNAL_ERROR", "Google OAuth is not configured.", status_code=503)

    token = await oauth.google.authorize_access_token(request)
    userinfo = token.get("userinfo")
    if not userinfo:
        userinfo = await oauth.google.parse_id_token(request, token)

    email = (userinfo.get("email") or "").lower()
    name = userinfo.get("name") or email
    if not email:
        raise AppError("AUTH_INVALID", "Google account did not provide an email.", status_code=401)

    user = await get_user_by_email(db, email)
    if not user:
        if email == settings.super_admin_email.lower():
            user = await _bootstrap_super_admin(db, email=email, name=name)
            await write_audit_log(
                db,
                event_type="SUPER_ADMIN_BOOTSTRAP",
                actor_user_id=user.id,
                resource_type="user",
                resource_id=user.id,
                details={"email": email},
            )
        else:
            raise AppError(
                "USER_NOT_PROVISIONED",
                "Your account is not provisioned. Contact an administrator.",
                status_code=403,
            )
    elif email == settings.super_admin_email.lower() and user.role != UserRole.SUPER_ADMIN:
        user.role = UserRole.SUPER_ADMIN
        user.is_super_admin_seed = True
        user.status = UserStatus.ACTIVE

    if user.status != UserStatus.ACTIVE:
        raise AppError("NOT_AUTHORIZED", "User account is inactive.", status_code=403)

    request.session["user_id"] = user.id
    await db.commit()
    return RedirectResponse(url=settings.frontend_url)


async def _bootstrap_super_admin(db: AsyncSession, *, email: str, name: str):
    from rag_shared.models.entities import User

    user = User(
        email=email,
        name=name,
        role=UserRole.SUPER_ADMIN,
        status=UserStatus.ACTIVE,
        is_super_admin_seed=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user, attribute_names=["department_assignments"])
    return user


@router.get("/me", response_model=UserResponse)
async def auth_me(current: CurrentUser = Depends(get_current_user)) -> UserResponse:
    return to_user_response(current.user)


@router.post("/logout")
async def logout(request: Request) -> dict[str, str]:
    request.session.clear()
    return {"status": "logged_out"}
