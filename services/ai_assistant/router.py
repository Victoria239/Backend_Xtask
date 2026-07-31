"""AI Assistant HTTP routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_service_db
from shared.dependencies import get_current_tenant_id, get_current_user_id
from services.ai_assistant.schemas import (
    ChatRequest,
    ChatResponse,
    ConversationOut,
    MessageOut,
)
from services.ai_assistant.service import AssistantService

router = APIRouter()


def get_service(db: AsyncSession = Depends(get_service_db("ai_assistant"))) -> AssistantService:
    return AssistantService(db)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    service: AssistantService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
    user_id: int = Depends(get_current_user_id),
):
    return await service.chat(
        tenant_id=tenant_id,
        user_id=user_id,
        message=payload.message,
        conversation_id=payload.conversation_id,
        top_k=payload.top_k,
    )


@router.get("/conversations", response_model=list[ConversationOut])
async def list_conversations(
    service: AssistantService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
    user_id: int = Depends(get_current_user_id),
):
    return await service.list_conversations(tenant_id, user_id)


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
async def list_messages(
    conversation_id: int,
    service: AssistantService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
    user_id: int = Depends(get_current_user_id),
):
    return await service.list_messages(tenant_id, user_id, conversation_id)
