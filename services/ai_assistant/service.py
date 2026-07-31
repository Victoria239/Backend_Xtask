"""AI Assistant orchestration — RAG retrieval + LLM completion + DB tools."""

from __future__ import annotations

import json
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.ai_assistant.llm import LlmAnswer, get_llm_provider
from services.ai_assistant.models import Conversation, Message
from services.ai_assistant.schemas import Citation, ChatResponse
from services.ai_assistant.fallback import answer_from_intent, build_fallback_answer
from services.ai_assistant.tools import (
    TOOL_DEFINITIONS,
    execute_tool,
    summary_for_citation,
)
from services.rag.repository import RagRepository
from services.rag.service import RagService

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = (
    "Eres el copiloto interno de XTask. Respondes en español de forma concisa y "
    "profesional.\n\n"
    "Tienes dos fuentes de información complementarias:\n"
    "1. CONTEXT (corpus RAG): fragmentos de documentos, decisiones (ADRs), "
    "   reuniones, knowledge wiki y procesos.\n"
    "2. Tools: funciones que consultan la base de datos en vivo "
    "   (empleados, OKRs, contratos, pagos, ausencias).\n\n"
    "Usa el CONTEXT para preguntas conceptuales o históricas. Llama a las tools "
    "cuando necesites datos operativos actuales (quién, cuántos, cuándo, status). "
    "Si la pregunta requiere ambas, combínalas en la respuesta.\n\n"
    "Cita las fuentes: cuando uses CONTEXT, menciona el título del documento. "
    "Cuando uses tools, indica brevemente qué consulta hiciste. Si no tenés "
    "información suficiente, dilo explícitamente — nunca inventes."
)


MAX_TOOL_ITERATIONS = 4


class AssistantService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.rag = RagService(RagRepository(db))
        self.llm = get_llm_provider()

    async def _get_or_create_conversation(
        self, tenant_id: int, user_id: int, conversation_id: int | None
    ) -> Conversation:
        if conversation_id is not None:
            res = await self.db.execute(
                select(Conversation).where(
                    Conversation.id == conversation_id,
                    Conversation.tenant_id == tenant_id,
                    Conversation.user_id == user_id,
                )
            )
            conv = res.scalar_one_or_none()
            if conv:
                return conv
        conv = Conversation(tenant_id=tenant_id, user_id=user_id, title=None)
        self.db.add(conv)
        await self.db.flush()
        return conv

    async def _record_message(
        self,
        conversation_id: int,
        tenant_id: int,
        role: str,
        content: str,
        citations: list | None = None,
    ) -> None:
        self.db.add(
            Message(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                role=role,
                content=content,
                citations=citations or [],
            )
        )
        await self.db.flush()

    async def list_conversations(self, tenant_id: int, user_id: int):
        res = await self.db.execute(
            select(Conversation)
            .where(Conversation.tenant_id == tenant_id, Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
            .limit(50)
        )
        return list(res.scalars().all())

    async def list_messages(self, tenant_id: int, user_id: int, conversation_id: int):
        # Ensure ownership
        owner = await self.db.execute(
            select(Conversation.id).where(
                Conversation.id == conversation_id,
                Conversation.tenant_id == tenant_id,
                Conversation.user_id == user_id,
            )
        )
        if owner.scalar_one_or_none() is None:
            return []
        res = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id, Message.tenant_id == tenant_id)
            .order_by(Message.id.asc())
        )
        return list(res.scalars().all())

    async def _chat_with_tools(
        self,
        tenant_id: int,
        user_prompt: str,
        citations: list[Citation],
    ) -> LlmAnswer:
        """Run a tool-using conversation loop with the LLM.

        Mutates `citations` in-place by appending one synthetic citation per
        tool invocation (with `source_type="db"`).
        """
        messages: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        # Pseudo IDs for synthetic DB citations. Real RAG docs use positive ids;
        # use negatives here to avoid collisions.
        next_synthetic_id = -1

        for _ in range(MAX_TOOL_ITERATIONS):
            turn = await self.llm.turn(messages, tools=TOOL_DEFINITIONS)

            if not turn.tool_calls:
                # Final answer reached.
                return LlmAnswer(answer=turn.content or "", provider=self.llm.name)

            # Persist the assistant turn with the tool_calls before executing,
            # so the next call has the full history.
            messages.append({
                "role": "assistant",
                "content": turn.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                        },
                    }
                    for tc in turn.tool_calls
                ],
            })

            for tc in turn.tool_calls:
                raw = await execute_tool(self.db, tenant_id, tc.name, tc.arguments)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": raw,
                })
                citations.append(
                    Citation(
                        document_id=next_synthetic_id,
                        document_title=f"{tc.name}()",
                        position=0,
                        score=1.0,
                        snippet=summary_for_citation(tc.name, tc.arguments, raw),
                        source_type="db",
                        source_uri=f"db://{tc.name}",
                    )
                )
                next_synthetic_id -= 1

        # Hit the iteration cap — return what we have.
        return LlmAnswer(
            answer=(
                "No pude completar la consulta en menos de "
                f"{MAX_TOOL_ITERATIONS} pasos. Revisá los datos recolectados en las citas."
            ),
            provider=self.llm.name,
        )

    async def chat(
        self,
        tenant_id: int,
        user_id: int,
        message: str,
        conversation_id: int | None,
        top_k: int = 4,
    ) -> ChatResponse:
        conv = await self._get_or_create_conversation(tenant_id, user_id, conversation_id)
        await self._record_message(conv.id, tenant_id, "user", message)

        hits = await self.rag.search(tenant_id, message, top_k=top_k)

        citations: list[Citation] = []
        if hits:
            context_blocks = []
            for h in hits:
                context_blocks.append(
                    f"[{h.document_title} · fragmento #{h.position}]\n{h.content}"
                )
                citations.append(
                    Citation(
                        document_id=h.document_id,
                        document_title=h.document_title,
                        position=h.position,
                        score=h.score,
                        snippet=h.content[:240],
                        source_type=getattr(h, "source_type", "raw"),
                        source_uri=getattr(h, "source_uri", None),
                    )
                )
            context = "\n\n---\n\n".join(context_blocks)
            user_prompt = f"CONTEXT:\n{context}\n\nQUESTION:\n{message}"
            used_rag = True
        else:
            user_prompt = "QUESTION:\n" + message
            used_rag = False

        rag_titles = [c.document_title for c in citations if c.source_type in ("vault", "raw", "upload", "policy")]

        # ─── Estrategia híbrida (decidida tras el QA) ───
        # Para preguntas de DATOS (intención clara), usamos el camino determinístico:
        # ejecuta la tool y devuelve datos exactos. Es más confiable que el LLM con
        # modelos pequeños, que tienden a alucinar al usar function calling.
        # Para preguntas CONCEPTUALES, usamos el LLM con contexto RAG (con fallback).
        intent_result = await answer_from_intent(self.db, tenant_id, message)

        if intent_result is not None:
            answer_text, tool_used, tool_data = intent_result
            citations.append(
                Citation(
                    document_id=-99, document_title=f"{tool_used}()",
                    position=0, score=1.0,
                    snippet=summary_for_citation(tool_used, {}, json.dumps(tool_data, default=str)),
                    source_type="db", source_uri=f"db://{tool_used}",
                )
            )
            llm_answer = LlmAnswer(answer=answer_text, provider=f"{self.llm.name}:data")
        else:
            # Pregunta conceptual → LLM con RAG, con degradación elegante.
            try:
                llm_answer = await self.llm.complete(SYSTEM_PROMPT, user_prompt)
                if not (llm_answer.answer or "").strip():
                    raise ValueError("LLM devolvió respuesta vacía")
            except Exception as exc:  # noqa: BLE001
                logger.warning("LLM no disponible (%s), usando fallback", exc)
                answer_text, tool_used, tool_data = await build_fallback_answer(
                    self.db, tenant_id, message, rag_titles,
                )
                if tool_used and tool_data is not None:
                    citations.append(
                        Citation(
                            document_id=-99, document_title=f"{tool_used}()",
                            position=0, score=1.0,
                            snippet=summary_for_citation(tool_used, {}, json.dumps(tool_data, default=str)),
                            source_type="db", source_uri=f"db://{tool_used}",
                        )
                    )
                llm_answer = LlmAnswer(answer=answer_text, provider=f"{self.llm.name}:fallback")

        await self._record_message(
            conv.id,
            tenant_id,
            "assistant",
            llm_answer.answer,
            citations=[c.model_dump() for c in citations],
        )

        return ChatResponse(
            conversation_id=conv.id,
            answer=llm_answer.answer,
            citations=citations,
            provider=llm_answer.provider,
            used_rag=used_rag,
        )
