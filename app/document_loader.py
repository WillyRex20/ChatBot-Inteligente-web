import logging
from pathlib import Path
from typing import Iterable, Iterator, List

from langchain_community.document_loaders import Docx2txtLoader, TextLoader
from langchain_core.documents import Document
from pypdf import PdfReader

from .config import ALLOWED_EXTENSIONS, MIN_PAGE_TEXT_CHARS

logger = logging.getLogger(__name__)


def validate_document(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"No se encontro el archivo: {path}")
    if path.suffix.lower() not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise ValueError(f"Formato no permitido. Usa: {allowed}")


def _clean_text(text: str) -> str:
    return " ".join((text or "").replace("\x00", "").replace("\ufffd", "").split())


def _load_pdf_with_pymupdf(path: Path) -> List[Document]:
    import fitz

    documents: List[Document] = []
    scanned_pages = 0

    with fitz.open(path) as pdf:
        for index, page in enumerate(pdf):
            text = _clean_text(page.get_text("text"))

            if len(text) < MIN_PAGE_TEXT_CHARS:
                scanned_pages += 1

            if text:
                documents.append(
                    Document(
                        page_content=text,
                        metadata={
                            "source": str(path),
                            "page": index,
                            "total_pages": pdf.page_count,
                        },
                    )
                )

    if not documents:
        raise ValueError(
            "El PDF no contiene texto seleccionable. Parece ser escaneado o una imagen. "
            "Para leerlo se necesita OCR: convierte el PDF a texto/OCR antes de subirlo."
        )

    return documents


def _load_pdf_with_pypdf(path: Path) -> List[Document]:
    documents: List[Document] = []
    reader = PdfReader(str(path))

    for index, page in enumerate(reader.pages):
        text = _clean_text(page.extract_text() or "")
        if text:
            documents.append(
                Document(
                    page_content=text,
                    metadata={
                        "source": str(path),
                        "page": index,
                        "total_pages": len(reader.pages),
                    },
                )
            )

    if not documents:
        raise ValueError(
            "No se pudo extraer texto del PDF. Si es un PDF escaneado, primero necesita OCR."
        )

    return documents


def load_pdf(path: Path) -> List[Document]:
    try:
        return _load_pdf_with_pymupdf(path)
    except Exception as e:
        if not isinstance(e, ImportError):
            logger.warning(f"Error con PyMuPDF en {path.name}: {e}. Intentando pypdf...")
        return _load_pdf_with_pypdf(path)


def load_document(path: str | Path) -> List[Document]:
    document_path = Path(path)
    validate_document(document_path)
    extension = document_path.suffix.lower()

    if extension == ".pdf":
        return load_pdf(document_path)
    if extension == ".docx":
        try:
            return Docx2txtLoader(str(document_path)).load()
        except Exception as e:
            logger.error(f"Error cargando Word {document_path.name}: {e}")
            raise ValueError(f"No se pudo leer el archivo Word: {document_path.name}")
            
    # Intento de lectura de texto con detección de codificación
    for encoding in ["utf-8", "latin-1", "cp1252"]:
        try:
            loader = TextLoader(str(document_path), encoding=encoding)
            return loader.load()
        except UnicodeDecodeError:
            continue
        except Exception as e:
            logger.error(f"Error cargando TXT {document_path.name}: {e}")
            break
            
    raise ValueError(f"No se pudo leer el archivo {document_path.name}. Verifica que no esté corrupto o sea un formato diferente.")


def iter_documents(paths: Iterable[str | Path]) -> Iterator[Document]:
    for path in paths:
        yield from load_document(path)


def load_documents(paths: Iterable[str | Path]) -> List[Document]:
    return list(iter_documents(paths))
