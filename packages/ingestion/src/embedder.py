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

    @property
    def provider(self) -> str:
        return "local-sentence-transformers"

    @property
    def model_id(self) -> str:
        return self.model_name

    @property
    def model_version(self) -> str:
        return self.revision

    @property
    def config_hash(self) -> str:
        import hashlib
        import json

        config = {"model": self.model_name, "revision": self.revision, "dimension": self.dimension}
        return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()

    async def embed(self, text: str) -> list[float]:
        import asyncio

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: self.embed_texts([text])[0])

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generates embeddings for a list of texts."""
        if not texts:
            return []

        self._load_model()
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()
