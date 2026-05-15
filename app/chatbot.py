from __future__ import annotations
from dotenv import load_dotenv
load_dotenv() # Mover al principio del archivo

import os
import re
import logging
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

from .config import RETRIEVER_K, SUMMARY_RETRIEVER_K, VECTOR_DIR
from .vectorstore import load_vectorstore

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Eres un Asistente Virtual Inteligente y experto en análisis de documentos. Tu misión es ayudar al usuario de forma amable, profesional y precisa.

HISTORIAL DE CONVERSACIÓN (Últimos mensajes):
{history}

NORMAS DE RESPUESTA:
1. Sé cordial: Saluda si el usuario te saluda y despídete si el usuario se va.
2. Estructura: Usa **negritas** para resaltar y listas para organizar información compleja.
3. Contexto: Prioriza la información de los DOCUMENTOS RECUPERADOS. Si el usuario hace una pregunta general que no requiere los documentos (como "¿cómo estás?"), responde con tu personalidad de IA.
4. Honestidad: Si te preguntan algo sobre los documentos y la respuesta NO está en ellos, indícalo amablemente sin inventar datos.
5. Fluidez: Utiliza el HISTORIAL para entender el hilo de la charla.
6. No repetición: No repitas la misma información en el mismo mensaje. Sé conciso y directo.
6. Claridad: No uses tecnicismos internos ni nombres de archivos del sistema.

CONTEXTO RECUPERADO:
{context}

PREGUNTA DEL USUARIO:
{question}

RESPUESTA ESTRUCTURADA:"""

FALLBACK_ANSWER = "Lo siento, la información solicitada no se encuentra en los documentos cargados actualmente."

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
        self.llm = None
        self.prompt = PromptTemplate(template=SYSTEM_PROMPT, input_variables=["context", "question", "history"])
        # Diccionario para almacenar el historial de conversación por sesión
        self.histories: Dict[str, List[Dict[str, str]]] = {}
        self.reload()

    def reload(self) -> None:
        """Recarga el almacén de vectores y el modelo de lenguaje."""
        self.llm = self._build_llm()
        self.histories = {}
        logger.info(f"Chatbot LLM reloaded. Mode: {'OpenAI' if self.llm else 'Local'}")

    def _build_llm(self) -> Optional[Any]:
        """Intenta construir el modelo de OpenAI si la API Key está configurada."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or api_key == "tu_clave" or len(api_key) < 10:
            logger.warning("OPENAI_API_KEY no detectada. El chatbot funcionará en modo extractivo local.")
            return None
        try:
            return ChatOpenAI(model="gpt-4o-mini", temperature=0.1, openai_api_key=api_key)
        except Exception as e:
            logger.error(f"Error al inicializar OpenAI LLM: {e}")
            return None

    def ask(self, question: str, session_id: str = "default") -> Dict[str, Any]:
        """Procesa una pregunta y genera una respuesta basada en el contexto."""
        clean_question = question.strip()
        if not clean_question:
            raise ValueError("Escribe una pregunta para consultar el documento.")

        # Cargar base vectorial específica de la sesión
        session_vector_dir = VECTOR_DIR / re.sub(r'[^a-zA-Z0-9_-]', '_', session_id)
        vectorstore = None
        try:
            vectorstore = load_vectorstore(session_vector_dir)
        except FileNotFoundError:
            # Si no hay documentos y no hay LLM, no podemos hacer nada
            if self.llm is None:
                raise ValueError("Este chat no tiene documentos cargados. Sube un archivo primero.")
            # Si hay LLM pero no hay documentos, permitimos solo saludos/charla general
            if not self._is_greeting(clean_question) and not self._is_general_chat(clean_question):
                raise ValueError("No hay documentos cargados en este chat para analizar. Por favor, sube un archivo primero.")

        is_summary = self._is_summary_request(clean_question)
        source_documents = []
        
        if vectorstore:
            search_k = SUMMARY_RETRIEVER_K if is_summary else RETRIEVER_K
            search_query = (
                "resumen idea principal objetivo puntos clave contenido del documento"
                if is_summary
                else clean_question
            )
            source_documents = vectorstore.similarity_search(search_query, k=search_k)

        if self.llm is not None:
            # Obtener los últimos 3 intercambios del historial para dar contexto
            session_history = self.histories.get(session_id, [])[-3:]
            history_str = "\n".join([f"Usuario: {h['question']}\nAsistente: {h['answer']}" for h in session_history])
            
            context = "\n\n".join(document.page_content for document in source_documents) if source_documents else "No hay documentos cargados."
            prompt_text = self.prompt.format(
                context=context, 
                question=clean_question, 
                history=history_str if history_str else "No hay mensajes previos."
            )
            
            response = self.llm.invoke(prompt_text)
            raw_answer = getattr(response, "content", str(response))
        else:
            # Lógica local para saludos o búsqueda
            if self._is_greeting(clean_question):
                raw_answer = "¡Hola! Soy tu asistente documental local. Sube un archivo para empezar a analizarlo."
            elif not source_documents:
                return self._build_error_response(clean_question, session_id)
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
        greetings = {"hola", "buenas", "buenos dias", "buenas tardes", "buenas noches", "hello", "hi", "saludos"}
        return any(g in normalized for g in greetings)

    def _is_general_chat(self, text: str) -> bool:
        normalized = self._strip_accents(text.lower())
        general = {"quien eres", "que haces", "como estas", "ayuda", "gracias", "chau", "adios"}
        return any(g in normalized for g in general)

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
        # Añadimos ';' como delimitador para intentar separar el código de los comentarios
        parts = re.split(r"(?<=[.!?|;])\s+|\n+", context.replace("\r", "\n"))
        return [s for s in (self._normalize_text(p) for p in parts) if len(s) > 10]

    def _unique_sentences(self, sentences: List[str]) -> List[str]:
        unique = []
        seen_keys = set()
        for s in sentences:
            key = self._strip_accents(s.lower())[:140]
            if key not in seen_keys:
                seen_keys.add(key)
                unique.append(s)
        return unique

    def _extract_keywords(self, text: str) -> List[str]:
        words = re.findall(r"[a-zA-Z0-9_+#.-]{3,}", self._strip_accents(text.lower()))
        return [w for w in words if w not in STOPWORDS]

    def _score_sentence(self, sentence: str, keywords: List[str]) -> int:
        norm = self._strip_accents(sentence.lower())
        score = sum(3 if len(k) > 5 else 1 for k in keywords if k in norm)
        if any(t in norm for t in ("objetivo", "permite", "sistema", "resultado", "principal")): score += 1
        
        # Penalizar fuertemente frases que parecen código técnico
        code_symbols = sum(sentence.count(c) for c in "(){}[]#;<>=")
        if code_symbols > 2:
            score -= (code_symbols * 2)
            
        if len(sentence) > 10 and (sentence.count(' ') / len(sentence)) < 0.15:
            score -= 5

        # Penalizar términos técnicos de programación comunes en Arduino/C++
        if any(w in norm for w in ["void", "int", "setup", "loop", "include", "define", "serial.", "lcd.", "delay"]):
            score -= 3
        return score

    def _build_summary_logic(self, context: str, sentences: List[str], keywords: List[str]) -> str:
        # Mejoramos la selección de frases para el resumen
        scored = [(self._score_sentence(s, keywords), i, s) for i, s in enumerate(sentences)]
        ranked = sorted(scored, key=lambda x: x[0], reverse=True)
        
        selected = sorted([s for _, _, s in ranked[:4]], key=lambda s: sentences.index(s))
        if not selected:
            selected = sentences[:3] # Fallback a las primeras frases si no hay keywords
        # Evitar redundancia: el primer punto clave no debe ser igual a la introducción
        bullets_source = selected[1:] if len(selected) > 1 else selected
        bullets = "\n".join(f"* {p}" for p in bullets_source)
        intro = f"El documento aborda principalmente: **{selected[0][0].lower() + selected[0][1:]}**"
        return f"{intro}\n\n**Puntos clave identificados:**\n{bullets}"

    def _build_direct_logic(self, question: str, sentences: List[str], keywords: List[str]) -> str:
        if not sentences:
            return FALLBACK_ANSWER
            
        ranked = sorted(((self._score_sentence(s, keywords), s) for s in sentences), key=lambda x: x[0], reverse=True)
        
        # Solo tomamos frases que tengan al menos una coincidencia de palabra clave (score > 0)
        best_sentences = [s for score, s in ranked[:3] if score > 0]
        
        # Si la relevancia es nula, es preferible el Fallback que inventar o dar basura
        if not best_sentences and ranked[0][0] <= 0:
            return FALLBACK_ANSWER
            
        best = "\n".join(best_sentences)
        if not best: return FALLBACK_ANSWER
        prefix = "Según los documentos subidos" if not self._is_definition_request(question) else "Definición encontrada"
        return f"{prefix}: {best}"

    def _clean_answer(self, answer: str, question: str) -> str:
        # Procesamos las líneas para identificar comentarios de código o lenguaje natural
        lines = []
        for line in answer.splitlines():
            line = line.strip()
            if not line: continue
            
            # Si tiene un comentario '//', priorizamos la parte explicativa humana
            if "//" in line:
                parts = line.split("//")
                # Si la parte izquierda es código denso, nos quedamos solo con la derecha (comentario)
                if any(c in parts[0] for c in "(){}[]#;<>=") or len(parts[0].strip()) < 10:
                    line = parts[1].strip()
            
            # Limpiar caracteres técnicos, llaves y entidades HTML para que el texto sea entendible
            line = line.replace("{", "").replace("}", "").replace(";", "").replace("(", "").replace(")", "").replace("#", "")
            line = line.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&amp;", "&")
            
            # Si la línea resultante parece puro código residual sin sentido humano, la saltamos
            norm_line = self._strip_accents(line.lower())
            if any(norm_line.startswith(w) for w in ["include", "define", "void ", "int ", "serial.", "lcd."]):
                continue
            
            # Filtro final de símbolos técnicos excesivos
            if sum(line.count(c) for c in "={}[]<>") > 1:
                continue
                
            if line:
                lines.append(line)

        cleaned = "\n".join(filter(None, [self._normalize_text(l) for l in lines]))
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
