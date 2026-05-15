from pathlib import Path
from uuid import uuid4

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge
from werkzeug.utils import secure_filename

from app.chatbot import RagChatbot
from app.config import ALLOWED_EXTENSIONS, BASE_DIR, DATA_DIR, MAX_CONTENT_LENGTH, MAX_UPLOAD_MB, UPLOAD_DIR
from app.document_loader import iter_documents, load_documents
from app.vectorstore import create_vectorstore


app = Flask(__name__, static_folder=str(BASE_DIR / "web"), static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
CORS(app)

chatbot = RagChatbot()


def allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def json_error(message: str, status_code: int = 400):
    return jsonify({"error": message, "status": status_code}), status_code


@app.before_request
def reject_oversized_request():
    if request.path.startswith("/api/") and request.content_length and request.content_length > MAX_CONTENT_LENGTH:
        return json_error(
            f"El archivo es demasiado pesado. El limite configurado es {MAX_UPLOAD_MB} MB por solicitud.",
            413,
        )


@app.errorhandler(RequestEntityTooLarge)
def file_too_large(_error):
    return json_error(
        f"El archivo es demasiado pesado. El limite configurado es {MAX_UPLOAD_MB} MB por solicitud.",
        413,
    )


@app.errorhandler(HTTPException)
def http_error(error):
    if request.path.startswith("/api/"):
        return json_error(error.description or "No se pudo completar la solicitud.", error.code or 500)
    return error


@app.errorhandler(Exception)
def unexpected_error(error):
    app.logger.exception(error)
    if request.path.startswith("/api/"):
        return json_error(
            "Ocurrio un error interno al procesar la solicitud. Reinicia el servidor e intenta nuevamente.",
            500,
        )
    return json_error("Ocurrio un error interno.", 500)


@app.get("/")
def home():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/health")
def health():
    mode = "openai" if chatbot.llm is not None else "local-rag"
    return jsonify({"status": "ok", "message": "Chatbot RAG activo", "mode": mode})


@app.post("/api/upload")
def upload_documents():
    files = request.files.getlist("files")
    if not files:
        return json_error("Sube al menos un archivo PDF, TXT o DOCX.")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    saved_paths = []

    for file in files:
        if not file.filename:
            continue
        if not allowed_file(file.filename):
            return json_error(f"Formato no permitido: {file.filename}. Usa PDF, TXT o DOCX.")

        filename = f"{uuid4().hex}_{secure_filename(file.filename)}"
        path = UPLOAD_DIR / filename
        file.save(path)
        saved_paths.append(path)

    if not saved_paths:
        return json_error("No se recibieron archivos validos.")

    try:
        documents = iter_documents(saved_paths)
        create_vectorstore(documents)
        chatbot.reload()
    except Exception as exc:
        return json_error(f"No se pudo leer el documento. Motivo: {exc}", 400)

    return jsonify(
        {
            "message": "Documentos procesados correctamente.",
            "files": [path.name for path in saved_paths],
            "documents": len(saved_paths),
        }
    )


@app.post("/api/index-sample")
def index_sample_data():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    paths = [path for path in DATA_DIR.iterdir() if path.suffix.lower() in ALLOWED_EXTENSIONS]
    if not paths:
        return json_error("No hay documentos en la carpeta data/.")

    try:
        documents = load_documents(paths)
        create_vectorstore(documents)
        chatbot.reload()
    except Exception as exc:
        return json_error(f"No se pudo indexar la carpeta data/. Motivo: {exc}", 400)

    return jsonify({"message": "Documentos de data/ indexados.", "files": [p.name for p in paths]})


@app.post("/api/chat")
def chat():
    payload = request.get_json(silent=True) or {}
    question = payload.get("question", "")
    session_id = payload.get("session_id", "default")

    try:
        result = chatbot.ask(question, session_id=session_id)
        return jsonify(result)
    except Exception as exc:
        return json_error(str(exc), 400)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
