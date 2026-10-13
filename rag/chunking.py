"""
Dual Chunking Strategies for Policy Documents.
Implements Strategy A (Fixed-Size Chunking with Overlap) and Strategy B (Sentence-Based Chunking).
"""

import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, List


@dataclass
class TextChunk:
    chunk_id: str
    doc_id: str
    content: str
    strategy: str
    char_length: int
    index: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def fixed_size_chunking(
    text: str,
    doc_id: str,
    window: int = 200,
    overlap: int = 40,
) -> List[TextChunk]:
    """
    Strategy A: Fixed-Size Chunking with Overlap.
    Window: 200 characters | Overlap: 40 characters.
    Slide step: window - overlap = 160 characters.
    """
    cleaned_text = " ".join(text.split())
    chunks: List[TextChunk] = []
    
    if not cleaned_text:
        return chunks

    step = max(1, window - overlap)
    start = 0
    idx = 0
    text_len = len(cleaned_text)

    while start < text_len:
        end = min(start + window, text_len)
        chunk_str = cleaned_text[start:end].strip()
        if chunk_str:
            chunks.append(
                TextChunk(
                    chunk_id=f"{doc_id}_fixed_{idx}",
                    doc_id=doc_id,
                    content=chunk_str,
                    strategy="fixed",
                    char_length=len(chunk_str),
                    index=idx,
                )
            )
            idx += 1
        if end >= text_len:
            break
        start += step

    return chunks


def sentence_based_chunking(
    text: str,
    doc_id: str,
) -> List[TextChunk]:
    """
    Strategy B: Sentence-Based Chunking.
    Splits text across sentence boundaries, preserving full semantic policy conditions.
    """
    # Remove markdown header lines if any, or normalize them
    lines = text.strip().splitlines()
    body_lines = [line.strip() for line in lines if not line.strip().startswith("#") and line.strip()]
    normalized_text = " ".join(body_lines)

    # Split using sentence boundary regex: period, exclamation, or question mark followed by whitespace
    raw_sentences = re.split(r"(?<=[.!?])\s+", normalized_text)
    
    chunks: List[TextChunk] = []
    idx = 0
    for sentence in raw_sentences:
        clean_sentence = sentence.strip()
        if clean_sentence:
            chunks.append(
                TextChunk(
                    chunk_id=f"{doc_id}_sentence_{idx}",
                    doc_id=doc_id,
                    content=clean_sentence,
                    strategy="sentence",
                    char_length=len(clean_sentence),
                    index=idx,
                )
            )
            idx += 1

    return chunks
