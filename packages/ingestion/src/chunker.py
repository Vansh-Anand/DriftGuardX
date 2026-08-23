

class BaseChunker:
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_text(self, text: str) -> list[str]:
        """Simple deterministic sliding window chunker."""
        if not text:
            return []

        words = text.split()
        chunks = []

        if len(words) <= self.chunk_size:
            return [" ".join(words)]

        i = 0
        while i < len(words):
            chunk = words[i:i + self.chunk_size]
            chunks.append(" ".join(chunk))
            i += (self.chunk_size - self.chunk_overlap)

        return chunks
