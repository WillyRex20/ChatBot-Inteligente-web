from pathlib import Path
from typing import Iterable, Iterator, List

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

from .config import CHUNK_OVERLAP, CHUNK_SIZE, RETRIEVER_K, VECTOR_BATCH_SIZE, VECTOR_DIR
from .embeddings import get_embeddings


def get_splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )


def split_documents(documents: Iterable[Document]) -> List[Document]:
    splitter = get_splitter()
    return splitter.split_documents(list(documents))


def iter_chunks(documents: Iterable[Document]) -> Iterator[Document]:
    splitter = get_splitter()
    for document in documents:
        for chunk in splitter.split_documents([document]):
            content = " ".join(chunk.page_content.split())
            if content:
                chunk.page_content = content
                yield chunk


def create_vectorstore(documents: Iterable[Document], persist_path: Path = VECTOR_DIR) -> FAISS:
    embeddings = get_embeddings()
    vectorstore: FAISS | None = None
    batch: List[Document] = []
    chunk_count = 0

    for chunk in iter_chunks(documents):
        batch.append(chunk)
        if len(batch) < (VECTOR_BATCH_SIZE or 1):
            continue

        if vectorstore is None:
            vectorstore = FAISS.from_documents(batch, embeddings)
        else:
            vectorstore.add_documents(batch)
        chunk_count += len(batch)
        batch = []

    if batch:
        if vectorstore is None:
            vectorstore = FAISS.from_documents(batch, embeddings)
        else:
            vectorstore.add_documents(batch)
        chunk_count += len(batch)

    if vectorstore is None or chunk_count == 0:
        raise ValueError("No se pudo extraer texto util de los documentos.")

    persist_path.mkdir(parents=True, exist_ok=True)
    vectorstore.save_local(str(persist_path))
    return vectorstore


def load_vectorstore(persist_path: Path = VECTOR_DIR) -> FAISS:
    index_file = persist_path / "index.faiss"
    if not index_file.exists():
        raise FileNotFoundError("Aun no existe una base vectorial. Sube o indexa documentos primero.")

    return FAISS.load_local(
        str(persist_path),
        get_embeddings(),
        allow_dangerous_deserialization=True,
    )


def as_retriever(vectorstore: FAISS):
    return vectorstore.as_retriever(search_kwargs={"k": RETRIEVER_K})
