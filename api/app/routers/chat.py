"""
Router /chat — Chatbot Fèfèn (retrieval TF-IDF — Phase 6)

Le moteur Fèfèn est chargé depuis app.state.fefen (initialisé au lifespan).
Fallback sur des réponses statiques si l'index n'est pas disponible.
"""
import uuid

from fastapi import APIRouter, Request

from ..schemas.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])

# Fallback si Fèfèn n'est pas chargé (tests unitaires, démarrage rapide)
_STUB_REPLIES = [
    "Mwen ka tchenbé ! Yo ka krié mwen Fèfèn ! é ou mèm, say i di a ?",
    "Sa ou vlé savé ? Mwen la pou aidé'w !",
    "Kréyòl la dous, palé'y toujou !",
    "Bonjou ! Ki jan ou rélé ? Mwen ka rélé Fèfèn !",
]


@router.post("", response_model=ChatResponse, summary="Chatbot Fèfèn")
def chat(request_body: ChatRequest, request: Request) -> ChatResponse:
    """Envoie un message au chatbot Fèfèn — réponse retrieval TF-IDF."""
    session_id = request_body.session_id or f"sess_{uuid.uuid4().hex[:8]}"

    fefen = getattr(request.app.state, "fefen", None)
    if fefen is not None:
        reply = fefen.reply(request_body.message)
    else:
        reply = _STUB_REPLIES[len(request_body.message) % 4]

    return ChatResponse(
        reply=reply,
        session_id=session_id,
        model_version="fèfèn-0.2-tfidf",
    )
