import logging
import os
from pathlib import Path
from uuid import uuid4
from typing import Any, Dict, Tuple, List
from flask import Flask, jsonify, request, send_from_directory, Response
from flask_cors import CORS
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge
from werkzeug.utils import secure_filename

from app.chatbot import RagChatbot
from app.config import ALLOWED_EXTENSIONS, BASE_DIR, DATA_DIR, MAX_CONTENT_LENGTH, MAX_UPLOAD_MB, UPLOAD_DIR
from app.document_loader import iter_documents, load_documents
from app.vectorstore import create_vectorstore

# Configuración de Logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder=str(BASE_DIR / "web"), static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
CORS(app)

# Inicialización de almacenamiento
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)
chatbot = RagChatbot()


def allowed_file(filename: str) -> bool:
    """Valida extensiones de archivo permitidas."""
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def json_response(message: str, status_code: int = 200, **kwargs) -> Tuple[Response, int]:
    """Estandariza todas las respuestas de la API."""
    success = status_code < 400
    payload = {"success": success, "message": message, **kwargs}
    return jsonify(payload), status_code


@app.before_request
def reject_oversized_request():
    if request.path.startswith("/api/") and request.content_length and request.content_length > MAX_CONTENT_LENGTH:
        return json_response(
            f"El archivo es demasiado pesado. El limite configurado es {MAX_UPLOAD_MB} MB por solicitud.",
            413,
        )


@app.errorhandler(RequestEntityTooLarge)
def file_too_large(_error):
    return json_response(
        f"El archivo es demasiado pesado. El limite configurado es {MAX_UPLOAD_MB} MB por solicitud.",
        413,
    )


@app.errorhandler(HTTPException)
def handle_http_error(error):
    if request.path.startswith("/api/"):
        return json_response(str(error.description), error.code or 500)
    return error


@app.errorhandler(Exception)
def handle_unexpected_error(error):
    logger.error(f"Error inesperado: {error}", exc_info=True)
    if request.path.startswith("/api/"):
        return json_response("Error interno del servidor. Por favor, contacte a soporte.", 500)
    return "Error interno", 500


@app.get("/")
def home():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/health")
def health():
    """Endpoint para verificar el estado del sistema."""
    mode = "openai" if chatbot.llm is not None else "local-rag"
    return json_response("Chatbot RAG activo", 200, mode=mode)


@app.post("/api/upload")
def upload_documents():
    """Carga y procesa nuevos documentos para la base vectorial."""
    files = request.files.getlist("files")
    if not files:
        return json_response("Sube al menos un archivo PDF, TXT o DOCX.", 400)

    saved_paths = []
    try:
        for file in files:
            if not file.filename:
                continue
            if not allowed_file(file.filename):
                return json_response(f"Formato no permitido: {file.filename}.", 400)

            filename = f"{uuid4().hex}_{secure_filename(file.filename)}"
            path = UPLOAD_DIR / filename
            file.save(path)
            saved_paths.append(path)
    except Exception as e:
        logger.error(f"Error guardando archivos: {e}")
        return json_response("Error al guardar archivos en el servidor.", 500)

    if not saved_paths:
        return json_response("No se recibieron archivos validos.", 400)

    try:
        documents = iter_documents(saved_paths)
        create_vectorstore(documents)
        chatbot.reload()
    except Exception as e:
        logger.error(f"Error en procesamiento RAG: {e}")
        return json_response(f"Error al procesar el contenido: {str(e)}", 400)

    return json_response("Documentos analizados con éxito.", files=[p.name for p in saved_paths])


@app.post("/api/index-sample")
def index_sample_data():
    """Indexa documentos predeterminados de la carpeta data/."""
    paths = [path for path in DATA_DIR.iterdir() if path.suffix.lower() in ALLOWED_EXTENSIONS]
    if not paths:
        return json_response("No hay documentos en la carpeta data/.", 404)

    try:
        documents = load_documents(paths)
        create_vectorstore(documents)
        chatbot.reload()
    except Exception as exc:
        return json_response(f"Error al indexar carpeta data: {str(exc)}", 500)

    return json_response("Documentos de data/ indexados.", files=[p.name for p in paths])


@app.post("/api/chat")
def chat():
    """Maneja la conversación con el chatbot."""
    payload = request.get_json(silent=True) or {}
    question = payload.get("question", "")
    session_id = payload.get("session_id", "default")
    
    if not question:
        return json_response("La pregunta es obligatoria.", 400)

    try:
        result = chatbot.ask(question, session_id=session_id)
        return jsonify(result) # El objeto result ya tiene el formato profesional
    except ValueError as ve:
        return json_response(str(ve), 400)
    except Exception as e:
        logger.error(f"Error en flujo de chat: {e}")
        return json_response("Error al generar la respuesta.", 500)


if __name__ == "__main__":
    # En la nube se usa el puerto que asigne el proveedor (PORT)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG", "False") == "True")
