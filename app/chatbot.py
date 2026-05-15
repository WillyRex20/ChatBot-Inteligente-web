from __future__ import annotations

import os
import re
import logging
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

from .config import RETRIEVER_K, SUMMARY_RETRIEVER_K, VECTOR_DIR
from .vectorstore import load_vectorstore

logger = logging.getLogger(__name__)


load_dotenv()

SYSTEM_PROMPT = """Eres un Analista Experto de Documentos. Tu misión es extraer información precisa y presentarla de forma estructurada.

NORMAS DE RESPUESTA:
1. Utiliza **negritas** para conceptos importantes.
2. Si la respuesta contiene varios puntos, usa **listas numeradas o viñetas**.
3. Responde ÚNICAMENTE basándote en el contexto proporcionado.
4. Si la información NO está en el contexto, di exactamente: "Lo siento, la información solicitada no se encuentra en los documentos cargados actualmente."
5. Mantén un tono profesional, objetivo y directo.
6. No menciones nombres técnicos de archivos (como UUIDs).

CONTEXTO RECUPERADO:
{context}

PREGUNTA DEL USUARIO:
{question}

RESPUESTA ESTRUCTURADA:"""

FALLBACK_ANSWER = "Lo siento, la información solicitada no se encuentra en los documentos cargados actualmente."
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


class RagChatbot:
    """Maneja la lógica de RAG (Retrieval Augmented Generation) para el chatbot."""
    
    def __init__(self) -> None:
        self.vectorstore = None
        self.llm = None
        self.prompt = PromptTemplate(template=SYSTEM_PROMPT, input_variables=["context", "question"])
        # Diccionario para almacenar el historial de conversación por sesión
        self.histories: Dict[str, List[Dict[str, str]]] = {}

    def reload(self) -> None:
        """Recarga el almacén de vectores y el modelo de lenguaje."""
        self.vectorstore = load_vectorstore(VECTOR_DIR)
        self.llm = self._build_llm()
        self.histories = {}
        logger.info(f"Chatbot reloaded. Mode: {'OpenAI' if self.llm else 'Local'}")

    def _build_llm(self) -> Optional[ChatOpenAI]:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or api_key == "tu_clave":
            return None
        return ChatOpenAI(model="gpt-4o-mini", temperature=0.1)

    def ask(self, question: str, session_id: str = "default") -> Dict[str, Any]:
        """Procesa una pregunta y genera una respuesta basada en el contexto."""
        clean_question = question.strip()
        if not clean_question:
            raise ValueError("Escribe una pregunta para consultar el documento.")

        if self._is_greeting(clean_question):
            history = self.histories.setdefault(session_id, [])
            history.append({"question": clean_question, "answer": GREETING_ANSWER})
            return {
                "question": clean_question,
                "answer": GREETING_ANSWER,
                "sources": [],
                "history": history,
            }

        if self.vectorstore is None:
            self.reload()

        is_summary = self._is_summary_request(clean_question)
        search_k = SUMMARY_RETRIEVER_K if is_summary else RETRIEVER_K
        search_query = (
            "resumen idea principal objetivo puntos clave contenido del documento"
            if is_summary
            else clean_question
        )
        source_documents = self.vectorstore.similarity_search(search_query, k=search_k)
        
        if not source_documents:
            return self._build_error_response(clean_question, session_id)

        if self.llm is not None:
            context = "\n\n".join(document.page_content for document in source_documents)
            prompt_text = self.prompt.format(context=context, question=clean_question)
            response = self.llm.invoke(prompt_text)
            raw_answer = getattr(response, "content", str(response))
        else:
            raw_answer = self._build_local_answer(clean_question, source_documents)

        answer = self._clean_answer(raw_answer, clean_question)
        history = self.histories.setdefault(session_id, [])
        history.append({"question": clean_question, "answer": answer})

        return {
            "question": clean_question,
            "answer": answer,
            "sources": self._format_sources(source_documents),
            "history": history,
        }

    def _build_error_response(self, question: str, session_id: str) -> Dict[str, Any]:
        history = self.histories.setdefault(session_id, [])
        history.append({"question": question, "answer": FALLBACK_ANSWER})
        return {
            "question": question,
            "answer": FALLBACK_ANSWER,
            "sources": [],
            "history": history,
        }

    # --- Métodos de utilidad y procesamiento ---

    def _is_greeting(self, text: str) -> bool:
        normalized = self._strip_accents(self._normalize_text(text).lower()).strip("?!. ")
        return normalized in {"hola", "buenas", "buenos dias", "buenas tardes", "buenas noches", "hello", "hi"}

    def _normalize_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    def _strip_accents(self, text: str) -> str:
        return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")

    def _is_summary_request(self, text: str) -> bool:
        plain = self._strip_accents(text.lower())
        return any(term in plain for term in SUMMARY_TERMS)

    def _is_definition_request(self, text: str) -> bool:
        plain = self._strip_accents(text.lower())
        return any(term in plain for term in DEFINITION_TERMS)

    def _build_local_answer(self, question: str, source_documents: List) -> str:
        context = self._normalize_text("\n".join(doc.page_content for doc in source_documents))
        if not context: return FALLBACK_ANSWER
        
        sentences = self._unique_sentences(self._split_sentences(context))
        keywords = self._extract_keywords(question)
        
        if self._is_summary_request(question):
            return self._build_summary_logic(context, sentences, keywords)
        return self._build_direct_logic(question, sentences, keywords)

    def _split_sentences(self, context: str) -> List[str]:
        parts = re.split(r"(?<=[.!?])\s+|\n+", context.replace("\r", "\n"))
        return [s for s in (self._normalize_text(p) for p in parts) if len(s) > 18]

    def _unique_sentences(self, sentences: List[str]) -> List[str]:
        seen = set()
        return [s for s in sentences if not (key := self._strip_accents(s.lower())[:140] in seen or seen.add(key))]

    def _extract_keywords(self, text: str) -> List[str]:
        words = re.findall(r"[a-zA-Z0-9_+#.-]{3,}", self._strip_accents(text.lower()))
        return [w for w in words if w not in STOPWORDS]

    def _score_sentence(self, sentence: str, keywords: List[str]) -> int:
        norm = self._strip_accents(sentence.lower())
        score = sum(3 if len(k) > 5 else 1 for k in keywords if k in norm)
        if any(t in norm for t in ("objetivo", "permite", "sistema", "resultado", "principal")): score += 1
        return score

    def _build_summary_logic(self, context: str, sentences: List[str], keywords: List[str]) -> str:
        ranked = sorted(((self._score_sentence(s, keywords), i, s) for i, s in enumerate(sentences)), reverse=True)
        selected = sorted([s for _, _, s in ranked[:4]], key=lambda s: sentences.index(s))
        if not selected:
            return FALLBACK_ANSWER
        bullets = "\n".join(f"* {p}" for p in selected[1:])
        intro = f"El documento aborda principalmente: **{selected[0][0].lower() + selected[0][1:]}**"
        return f"{intro}\n\n**Puntos clave identificados:**\n{bullets}"

    def _build_direct_logic(self, question: str, sentences: List[str], keywords: List[str]) -> str:
        ranked = sorted(((self._score_sentence(s, keywords), s) for s in sentences), key=lambda x: x[0], reverse=True)
        if not ranked or ranked[0][0] == 0: return FALLBACK_ANSWER
        best = " ".join([s for score, s in ranked[:3] if score > 0])
        prefix = "Segun el documento" if not self._is_definition_request(question) else "De acuerdo con el documento"
        return f"{prefix}, {best[0].lower() + best[1:]}"

    def _clean_answer(self, answer: str, question: str) -> str:
        cleaned = "\n".join(filter(None, [self._normalize_text(l) for l in answer.splitlines()]))
        for p in NOISE_PATTERNS: cleaned = re.sub(p, "", cleaned, flags=re.IGNORECASE).strip()
        if not cleaned or self._strip_accents(cleaned.lower()) == self._strip_accents(question.lower()):
            return FALLBACK_ANSWER
        return cleaned

    def _format_sources(self, source_documents: List) -> List[Dict[str, Any]]:
        unique_sources = []
        for doc in source_documents:
            meta = doc.metadata or {}
            raw_source = Path(meta.get("source", "doc")).name
            # Limpiar el prefijo UUID si existe para no mostrar nombres técnicos al usuario
            clean_source = raw_source[33:] if len(raw_source) > 33 and "_" in raw_source[:34] else raw_source
            
            s = {"source": clean_source, "page": meta.get("page")}
            if s not in unique_sources: unique_sources.append(s)
        return unique_sources
