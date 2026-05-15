from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
VECTOR_DIR = BASE_DIR / "storage" / "faiss_index"
UPLOAD_DIR = BASE_DIR / "uploads"

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".docx"}
MAX_UPLOAD_MB = 500
MAX_CONTENT_LENGTH = MAX_UPLOAD_MB * 1024 * 1024

CHUNK_SIZE = 650
CHUNK_OVERLAP = 90
RETRIEVER_K = 3
SUMMARY_RETRIEVER_K = 10
VECTOR_BATCH_SIZE = 48
MIN_PAGE_TEXT_CHARS = 25

DEFAULT_MODEL_NAME = "google/flan-t5-base"
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
