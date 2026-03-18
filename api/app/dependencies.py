from typing import Optional

from fastapi import Depends, Header, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .auth import decode_token
from .config import settings
from .database import get_db

security = HTTPBearer(auto_error=False)


def require_api_key(x_api_key: str = Header(...)) -> str:
    """Vérifie l'en-tête X-API-Key (usage interne scraper/admin legacy)."""
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Clé API invalide")
    return x_api_key


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
):
    """Extrait et valide le token JWT Bearer, retourne l'utilisateur."""
    from .models.models import User

    if credentials is None:
        raise HTTPException(status_code=401, detail="Token d'authentification requis")
    payload = decode_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=401, detail="Token invalide ou expiré")
    user = db.get(User, int(payload["sub"]))
    if user is None:
        raise HTTPException(status_code=401, detail="Utilisateur introuvable")
    return user


def require_admin(current_user=Depends(get_current_user)):
    """Vérifie que l'utilisateur connecté a le rôle admin."""
    if current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Accès réservé aux administrateurs")
    return current_user


class PaginationParams:
    def __init__(
        self,
        page: int = Query(default=1, ge=1, description="Numéro de page"),
        limit: int = Query(default=20, ge=1, le=3000, description="Résultats par page"),
    ):
        self.page = page
        self.limit = limit

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit
