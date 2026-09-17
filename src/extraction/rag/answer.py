from __future__ import annotations

from extraction.clients.groq import get_groq_client
from extraction.errors import ExtractionError
from extraction.rag.models import RetrievedParent
from extraction.settings import Settings

SYSTEM_PROMPT = (
    "You answer questions using only the provided document passages. "
    "If the passages are not enough, say you cannot answer from the indexed documents. "
    "Cite the filename and unit (page, slide, sheet, or time range) you used. "
    "Be concise and factual."
)
CANNOT_ANSWER = "I cannot answer from the indexed documents."


def _parent_label(parent: RetrievedParent) -> str:
    return f"{parent.filename} | {parent.unit_type} {parent.unit_index}"


def build_prompt(question: str, parents: list[RetrievedParent]) -> str:
    blocks = []
    for parent in parents:
        blocks.append(f"### {_parent_label(parent)}\n{parent.parent_text}")
    passages = "\n\n".join(blocks) if blocks else "(no passages retrieved)"
    return f"Question:\n{question}\n\nPassages:\n{passages}"


def answer_question(settings: Settings, question: str, parents: list[RetrievedParent]) -> str:
    client = get_groq_client(settings)
    if client is None:
        raise ExtractionError("LLM_UNAVAILABLE", "GROQ_API_KEY is not set.")
    response = client.chat.completions.create(
        model=settings.groq_llm_model,
        temperature=0.1,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_prompt(question, parents)},
        ],
    )
    text = (response.choices[0].message.content or "").strip()
    if not text:
        raise ExtractionError("LLM_EMPTY", "The answer model returned no text.")
    return text
