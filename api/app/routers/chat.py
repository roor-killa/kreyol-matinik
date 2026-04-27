"""
Router /chat — Chatbot Fèfèn (RAG pgvector + OpenAI — Phase 7)

Priorité des moteurs :
  1. FefenPGVector  — RAG pgvector + GPT-4o  (si OPENAI_API_KEY défini)
  2. FefenRAG       — TF-IDF + HuggingFace   (si HF_TOKEN défini)
  3. Fefen          — TF-IDF pur             (fallback toujours disponible)

Le moteur est chargé au lifespan dans app.state.fefen.
Ce router ne change pas — il appelle simplement fefen.reply().
"""
import uuid

from fastapi import APIRouter, Request

from ..schemas.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])

# Fallback si aucun moteur n'est chargé
_STUB_REPLIES = [
    "Mwen ka tchenbé ! Yo ka krié mwen Fèfèn ! é ou mèm, say i di a ?",
    "Sa ou vlé savé ? Mwen la pou aidé'w !",
    "Kréyòl la dous, palé'y toujou !",
    "Bonjou ! Ki jan ou rélé ? Mwen ka rélé Fèfèn !",
]


@router.post("", response_model=ChatResponse, summary="Chatbot Fèfèn")
def chat(request_body: ChatRequest, request: Request) -> ChatResponse:
    """Envoie un message au chatbot Fèfèn — RAG pgvector ou TF-IDF selon config."""
    session_id = request_body.session_id or f"sess_{uuid.uuid4().hex[:8]}"

    fefen = getattr(request.app.state, "fefen", None)
    if fefen is not None:
        reply = fefen.reply(request_body.message)
    else:
        reply = _STUB_REPLIES[len(request_body.message) % 4]

    # Détermine la version du modèle pour la réponse
    model_version = "fèfèn-0.2-tfidf"
    if fefen is not None:
        class_name = type(fefen).__name__
        if class_name == "FefenPGVector":
            model_version = "fèfèn-1.0-pgvector-gpt4o"
        elif class_name == "FefenRAG":
            model_version = "fèfèn-0.3-tfidf-hf"

    return ChatResponse(
        reply=reply,
        session_id=session_id,
        model_version=model_version,
    )
