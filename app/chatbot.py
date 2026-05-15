from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path
from typing import Dict, List, Tuple

from dotenv import load_dotenv
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

from app.config import RETRIEVER_K, SUMMARY_RETRIEVER_K, VECTOR_DIR
from app.vectorstore import load_vectorstore


load_dotenv()

SYSTEM_PROMPT = """Eres un asistente profesional de consulta documental, similar a ChatGPT.
Responde SOLO con informacion presente en el contexto recuperado.

Reglas:
- Responde en espanol claro, coherente y profesional.
- Contesta directamente la pregunta del usuario.
- No inventes datos, nombres, codigo ni componentes que no esten en el contexto.
- Si la respuesta no aparece en el contexto, responde: "No encuentro esa informacion en los documentos cargados."
- No devuelvas nombres de archivo como respuesta.
- No repitas la pregunta como respuesta.

Contexto:
{context}

Pregunta:
{question}

Respuesta:"""

FALLBACK_ANSWER = "No encuentro esa informacion en los documentos cargados."
GREETING_ANSWER = "Hola. Soy tu asistente documental. Puedes subir un PDF, TXT o DOCX y hacerme preguntas sobre su contenido."

NOISE_PATTERNS = [
    r"NA HORA DE RESPONDER",
    r"A HORA DE RESPONDER",
]

STOPWORDS = {
    "para",
    "pero",
    "como",
    "cual",
    "cuando",
    "donde",
    "quien",
    "porque",
    "sobre",
    "entre",
    "este",
    "esta",
    "estos",
    "estas",
    "documento",
    "archivo",
    "pregunta",
    "respuesta",
    "idea",
    "principal",
    "resumen",
    "trata",
    "dice",
    "explica",
    "tiene",
    "hacer",
    "hace",
    "usar",
    "usa",
    "son",
    "los",
    "las",
    "una",
    "unos",
    "unas",
    "del",
    "con",
    "que",
}

SUMMARY_TERMS = {
    "resumen",
    "resumir",
    "resume",
    "idea principal",
    "de que trata",
    "puntos clave",
    "principales puntos",
    "explica el documento",
}

DEFINITION_TERMS = {"que es", "define", "definicion", "significa", "concepto"}


def build_llm():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    return ChatOpenAI(model="gpt-4o-mini", temperature=0.1)


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def normalize_answer_text(text: str) -> str:
    lines = [normalize_text(line) for line in text.splitlines()]
    clean_lines = [line for line in lines if line]
    return "\n".join(clean_lines).strip()


def strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text)
    return "".join(character for character in normalized if unicodedata.category(character) != "Mn")


def is_greeting(question: str) -> bool:
    normalized = strip_accents(normalize_text(question).lower()).strip("?!. ")
    return normalized in {"hola", "buenas", "buenos dias", "buenas tardes", "buenas noches", "hello", "hi"}


def extract_keywords(question: str) -> List[str]:
    plain_question = strip_accents(question.lower())
    words = re.findall(r"[a-zA-Z0-9_+#.-]{3,}", plain_question)
    return [word for word in words if word not in STOPWORDS]


def is_summary_request(question: str) -> bool:
    plain_question = strip_accents(question.lower())
    return any(term in plain_question for term in SUMMARY_TERMS)


def is_definition_request(question: str) -> bool:
    plain_question = strip_accents(question.lower())
    return any(term in plain_question for term in DEFINITION_TERMS)


def split_context_sentences(context: str) -> List[str]:
    clean_context = context.replace("\r", "\n")
    parts = re.split(r"(?<=[.!?])\s+|\n+", clean_context)
    sentences = []
    for part in parts:
        sentence = normalize_text(part)
        if len(sentence) < 18:
            continue
        if re.fullmatch(r"[\w.-]+\.(pdf|docx|txt)", sentence, flags=re.IGNORECASE):
            continue
        sentences.append(sentence)
    return sentences


def score_sentence(sentence: str, keywords: List[str]) -> int:
    normalized = strip_accents(sentence.lower())
    score = 0
    for keyword in keywords:
        if keyword in normalized:
            score += 3 if len(keyword) > 5 else 1
    if any(term in normalized for term in ("objetivo", "permite", "sistema", "proyecto", "funciona")):
        score += 1
    if any(term in normalized for term in ("conclusion", "resultado", "importante", "principal", "consiste")):
        score += 1
    return score


def infer_code_summary(context: str) -> str | None:
    normalized = strip_accents(context.lower())
    details = []

    if "arduino" in normalized:
        details.append("Arduino")
    if "dht" in normalized:
        details.append("sensor DHT")
    if "temperatura" in normalized:
        details.append("temperatura")
    if "humedad" in normalized:
        details.append("humedad")
    if "lcd" in normalized or "i2c" in normalized or "liquidcrystal" in normalized:
        details.append("pantalla LCD I2C")

    if not details:
        return None

    unique_details = []
    for detail in details:
        if detail not in unique_details:
            unique_details.append(detail)

    return "La idea principal del documento es presentar un proyecto o codigo relacionado con " + ", ".join(unique_details) + "."


def unique_sentences(sentences: List[str]) -> List[str]:
    seen = set()
    unique = []
    for sentence in sentences:
        key = strip_accents(sentence.lower())[:140]
        if key in seen:
            continue
        seen.add(key)
        unique.append(sentence)
    return unique


def build_summary_answer(context: str, question: str) -> str:
    code_summary = infer_code_summary(context)
    sentences = unique_sentences(split_context_sentences(context))

    if code_summary and len(sentences) <= 4:
        return code_summary
    if not sentences:
        return FALLBACK_ANSWER

    keywords = extract_keywords(question)
    ranked = sorted(
        ((score_sentence(sentence, keywords), index, sentence) for index, sentence in enumerate(sentences)),
        key=lambda item: (item[0], -item[1]),
        reverse=True,
    )

    selected = []
    for _score, _index, sentence in ranked:
        if sentence not in selected:
            selected.append(sentence)
        if len(selected) >= 4:
            break

    selected = sorted(selected, key=lambda sentence: sentences.index(sentence))
    intro = "El documento trata principalmente sobre"

    if code_summary:
        first = code_summary.replace("La idea principal del documento es presentar", "un")
        body = first[0].lower() + first[1:]
    else:
        body = selected[0][0].lower() + selected[0][1:]
        body = re.sub(r"^este documento[^.]*explica\s+", "", body, flags=re.IGNORECASE)
        body = re.sub(r"^el documento[^.]*explica\s+", "", body, flags=re.IGNORECASE)

    extra_points = selected[1:4]
    if not extra_points:
        return f"{intro} {body}"

    bullets = "\n".join(f"- {point}" for point in extra_points)
    return f"{intro} {body}\n\nPuntos clave:\n{bullets}"


def build_direct_answer(question: str, context: str) -> str:
    keywords = extract_keywords(question)
    sentences = unique_sentences(split_context_sentences(context))
    if not sentences:
        return FALLBACK_ANSWER

    ranked = sorted(
        ((score_sentence(sentence, keywords), sentence) for sentence in sentences),
        key=lambda item: item[0],
        reverse=True,
    )
    best_score = ranked[0][0]

    if keywords and best_score == 0:
        return FALLBACK_ANSWER

    selected = []
    for score, sentence in ranked:
        if len(selected) >= 3:
            break
        if score == 0 and selected:
            break
        if sentence not in selected:
            selected.append(sentence)

    if not selected:
        return FALLBACK_ANSWER

    prefix = "Segun el documento"
    if is_definition_request(question):
        prefix = "De acuerdo con el documento"

    answer = " ".join(selected)
    if not answer.endswith((".", "!", "?")):
        answer += "."
    return f"{prefix}, {answer[0].lower() + answer[1:]}"


def build_local_answer(question: str, source_documents: List) -> str:
    context = "\n".join(document.page_content for document in source_documents)
    context = normalize_text(context)
    if not context:
        return FALLBACK_ANSWER

    if is_summary_request(question):
        return build_summary_answer(context, question)

    return build_direct_answer(question, context)


def clean_answer(answer: str, question: str, source_documents: List) -> str:
    cleaned = normalize_answer_text(answer)
    for pattern in NOISE_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()

    question_clean = strip_accents(normalize_text(question).lower()).strip("?!. ")
    answer_clean = strip_accents(cleaned.lower()).strip("?!. ")

    if not cleaned:
        return FALLBACK_ANSWER
    if answer_clean == question_clean:
        return FALLBACK_ANSWER
    if re.fullmatch(r"[\w-]{8,}_.+\.(pdf|docx|txt)", cleaned, flags=re.IGNORECASE):
        return FALLBACK_ANSWER
    if cleaned.lower().endswith((".pdf", ".docx", ".txt")) and len(cleaned.split()) <= 3:
        return FALLBACK_ANSWER

    return cleaned


def format_sources(source_documents: List) -> List[Dict]:
    sources = []
    for document in source_documents:
        metadata = document.metadata or {}
        source = {
            "source": metadata.get("source", "Documento cargado"),
            "page": metadata.get("page"),
        }
        if source not in sources:
            sources.append(source)
    return sources


class RagChatbot:
    def __init__(self) -> None:
        self.vectorstore = None
        self.llm = None
        self.prompt = PromptTemplate(template=SYSTEM_PROMPT, input_variables=["context", "question"])
        self.histories: Dict[str, List[Tuple[str, str]]] = {}

    def reload(self) -> None:
        self.vectorstore = load_vectorstore(VECTOR_DIR)
        self.llm = build_llm()
        self.histories = {}

    def ask(self, question: str, session_id: str = "default") -> Dict:
        clean_question = question.strip()
        if not clean_question:
            raise ValueError("Escribe una pregunta para consultar el documento.")

        if is_greeting(clean_question):
            history = self.histories.setdefault(session_id, [])
            history.append((clean_question, GREETING_ANSWER))
            return {
                "question": clean_question,
                "answer": GREETING_ANSWER,
                "sources": [],
                "history": history,
            }

        if self.vectorstore is None:
            self.reload()

        search_k = SUMMARY_RETRIEVER_K if is_summary_request(clean_question) else RETRIEVER_K
        search_query = (
            "resumen idea principal objetivo puntos clave contenido del documento"
            if is_summary_request(clean_question)
            else clean_question
        )
        source_documents = self.vectorstore.similarity_search(search_query, k=search_k)

        if self.llm is not None:
            context = "\n\n".join(document.page_content for document in source_documents)
            prompt_text = self.prompt.format(context=context, question=clean_question)
            response = self.llm.invoke(prompt_text)
            raw_answer = getattr(response, "content", str(response))
        else:
            raw_answer = build_local_answer(clean_question, source_documents)

        answer = clean_answer(raw_answer, clean_question, source_documents)
        history = self.histories.setdefault(session_id, [])
        history.append((clean_question, answer))

        return {
            "question": clean_question,
            "answer": answer,
            "sources": format_sources(source_documents),
            "history": history,
        }
