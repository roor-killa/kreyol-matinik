"""
Router /auth — Inscription, connexion, profil
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import create_access_token, hash_password, verify_password
from ..database import get_db
from ..dependencies import get_current_user
from ..models.models import Contributeur, User
from ..schemas.schemas import LoginRequest, TokenResponse, UserCreate, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(body: UserCreate, db: Session = Depends(get_db)) -> TokenResponse:
    """Inscrit un nouvel utilisateur et crée son profil contributeur."""
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=409, detail="Email déjà utilisé")
    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        name=body.name,
    )
    db.add(user)
    db.flush()  # récupère user.id sans commit
    contrib = Contributeur(user_id=user.id, pseudo=body.name)
    db.add(contrib)
    db.commit()
    db.refresh(user)
    token = create_access_token(user.id, str(user.role))
    return TokenResponse(token=token, user=UserOut.from_user(user))


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Authentifie un utilisateur et retourne un token JWT."""
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Identifiants invalides")
    token = create_access_token(user.id, str(user.role))
    return TokenResponse(token=token, user=UserOut.from_user(user))


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)) -> UserOut:
    """Retourne le profil de l'utilisateur connecté."""
    return UserOut.from_user(current_user)
