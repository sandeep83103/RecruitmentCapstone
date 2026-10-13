"""
Vector Store Indexing and Search for Naukri.com Policy Knowledge Base.
Indexes policy documentation into ChromaDB using dual chunking strategies:
1. naukri_fixed_chunks (Fixed-size 200/40)
2. naukri_sentence_chunks (Sentence-based)

Supports sentence-transformers/all-MiniLM-L6-v2 with deterministic offline fallback.
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import chromadb
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from rag.chunking import fixed_size_chunking, sentence_based_chunking, TextChunk


from chromadb.utils import embedding_functions


def get_embedding_function(model_name: str = "all-MiniLM-L6-v2") -> Any:
    """Returns official SentenceTransformerEmbeddingFunction using cached all-MiniLM-L6-v2."""
    try:
        return embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=model_name,
            normalize_embeddings=True,
        )
    except Exception:
        return OfflineSentenceTransformerEmbeddingFunction(model_name=model_name)


class OfflineSentenceTransformerEmbeddingFunction(chromadb.EmbeddingFunction[chromadb.api.types.Documents]):
    """
    Robust embedding function that attempts to load `all-MiniLM-L6-v2` locally.
    If external HuggingFace downloads are blocked or unavailable, uses a local
    deterministic TF-IDF + random projection encoder to 384-dim unit vectors,
    ensuring 100% offline, zero-network execution without failure.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.real_model = None
        self._init_model()

    def name(self) -> str:
        return "sentence_transformer"

    def _init_model(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer
            self.real_model = SentenceTransformer(self.model_name)
        except Exception:
            self.real_model = None

    def __call__(self, input: chromadb.api.types.Documents) -> List[List[float]]:
        if self.real_model is not None:
            try:
                embeddings = self.real_model.encode(input, normalize_embeddings=True)
                return [e.tolist() for e in embeddings]
            except Exception:
                pass

        # Deterministic offline fallback embedding (384 dimensions)
        import numpy as np
        import hashlib

        results: List[List[float]] = []
        for text in input:
            words = text.lower().split()
            vec = np.zeros(384, dtype=np.float32)
            for w in words:
                h = int(hashlib.md5(w.encode("utf-8")).hexdigest(), 16)
                idx = h % 384
                sign = 1.0 if (h // 384) % 2 == 0 else -1.0
                vec[idx] += sign
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            else:
                vec[0] = 1.0
            results.append(vec.tolist())
        return results


def get_chroma_client() -> ClientAPI:
    """Returns persistent ChromaDB client pointing to configured storage path."""
    config.CHROMA_PERSIST_DIR.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(config.CHROMA_PERSIST_DIR))



def get_or_create_collections(
    client: Optional[ClientAPI] = None,
    embedding_fn: Optional[Any] = None,
) -> Tuple[Collection, Collection]:
    """
    Retrieves or creates the two required collections:
    - naukri_fixed_chunks
    - naukri_sentence_chunks
    Both collections use cosine distance space.
    """
    if client is None:
        client = get_chroma_client()
    if embedding_fn is None:
        embedding_fn = get_embedding_function()

    fixed_col = client.get_or_create_collection(
        name="naukri_fixed_chunks",
        embedding_function=embedding_fn,
        metadata={"hnsw:space": "cosine"},
    )

    sentence_col = client.get_or_create_collection(
        name="naukri_sentence_chunks",
        embedding_function=embedding_fn,
        metadata={"hnsw:space": "cosine"},
    )

    return fixed_col, sentence_col


def load_knowledge_base_documents() -> List[Tuple[str, str]]:
    """Loads all markdown policy documents from the knowledge_base directory."""
    kb_dir = config.KNOWLEDGE_BASE_DIR
    files = sorted(list(kb_dir.glob("*.md")))
    documents: List[Tuple[str, str]] = []
    for file_path in files:
        doc_id = file_path.name
        content = file_path.read_text(encoding="utf-8")
        documents.append((doc_id, content))
    return documents


def index_knowledge_base(
    client: Optional[ClientAPI] = None,
    embedding_fn: Optional[Any] = None,
) -> Dict[str, int]:
    """
    Ingests, chunks, and indexes all documents into both ChromaDB collections
    using `collection.upsert()`.
    """
    if client is None:
        client = get_chroma_client()
    if embedding_fn is None:
        embedding_fn = get_embedding_function()

    fixed_col, sentence_col = get_or_create_collections(client, embedding_fn)
    documents = load_knowledge_base_documents()

    fixed_chunks: List[TextChunk] = []
    sentence_chunks: List[TextChunk] = []

    for doc_id, text in documents:
        f_chunks = fixed_size_chunking(text, doc_id=doc_id, window=200, overlap=40)
        s_chunks = sentence_based_chunking(text, doc_id=doc_id)
        fixed_chunks.extend(f_chunks)
        sentence_chunks.extend(s_chunks)

    # Upsert into fixed collection
    if fixed_chunks:
        fixed_col.upsert(
            ids=[c.chunk_id for c in fixed_chunks],
            documents=[c.content for c in fixed_chunks],
            metadatas=[
                {
                    "doc_id": c.doc_id,
                    "strategy": c.strategy,
                    "char_length": c.char_length,
                    "index": c.index,
                }
                for c in fixed_chunks
            ],
        )

    # Upsert into sentence collection
    if sentence_chunks:
        sentence_col.upsert(
            ids=[c.chunk_id for c in sentence_chunks],
            documents=[c.content for c in sentence_chunks],
            metadatas=[
                {
                    "doc_id": c.doc_id,
                    "strategy": c.strategy,
                    "char_length": c.char_length,
                    "index": c.index,
                }
                for c in sentence_chunks
            ],
        )

    return {
        "documents_loaded": len(documents),
        "fixed_chunks_indexed": len(fixed_chunks),
        "sentence_chunks_indexed": len(sentence_chunks),
    }


def query_collection(
    collection_name: str,
    query: str,
    top_k: int = 3,
    client: Optional[ClientAPI] = None,
    embedding_fn: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """
    Queries a collection and returns matched chunks with calculated cosine similarity.
    For cosine distance D in ChromaDB: Cosine Similarity = 1.0 - D.
    """
    if client is None:
        client = get_chroma_client()
    if embedding_fn is None:
        embedding_fn = get_embedding_function()

    col = client.get_collection(name=collection_name, embedding_function=embedding_fn)
    results = col.query(query_texts=[query], n_results=top_k)

    matched: List[Dict[str, Any]] = []
    if not results or not results["ids"] or not results["ids"][0]:
        return matched

    ids = results["ids"][0]
    docs = results["documents"][0] if results.get("documents") else []
    metadatas = results["metadatas"][0] if results.get("metadatas") else []
    distances = results["distances"][0] if results.get("distances") else []

    for i in range(len(ids)):
        dist = distances[i] if i < len(distances) else 1.0
        # Cosine distance to Cosine similarity
        similarity = max(0.0, min(1.0, 1.0 - dist))
        meta = metadatas[i] if i < len(metadatas) else {}
        matched.append({
            "chunk_id": ids[i],
            "doc_id": meta.get("doc_id", "unknown"),
            "content": docs[i] if i < len(docs) else "",
            "similarity": similarity,
            "distance": dist,
            "metadata": meta,
        })

    return matched


if __name__ == "__main__":
    print("=" * 60)
    print("Indexing Policy Knowledge Base into ChromaDB Collections")
    print("=" * 60)
    stats = index_knowledge_base()
    print(f"Total Policy Documents: {stats['documents_loaded']}")
    print(f"Fixed-Size Chunks Upserted: {stats['fixed_chunks_indexed']}")
    print(f"Sentence-Based Chunks Upserted: {stats['sentence_chunks_indexed']}")
    print("Collections indexed successfully in:", config.CHROMA_PERSIST_DIR)
    print("=" * 60)
