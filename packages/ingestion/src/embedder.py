class LocalEmbedder:
    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        revision: str = "main",
        dimension: int = 384,
        allow_download: bool = False,
    ):
        self.model_name = model_name
        self.revision = revision
        self.dimension = dimension
        self.allow_download = allow_download
        self.model = None

    def _load_model(self) -> None:
        if self.model is None:
            import os

            if not self.allow_download:
                os.environ["HF_HUB_OFFLINE"] = "1"
            from sentence_transformers import SentenceTransformer

            self.model = SentenceTransformer(self.model_name)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generates embeddings for a list of texts."""
        if not texts:
            return []

        self._load_model()
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()
