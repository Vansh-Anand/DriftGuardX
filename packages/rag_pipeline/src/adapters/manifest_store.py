from packages.ingestion.src.storage import MinioStorage


class ManifestStore:
    def __init__(self, bucket_name: str = "manifests"):
        self.storage = MinioStorage(bucket_name=bucket_name)

    async def save_manifest(self, manifest_hash: str, payload_json: str) -> None:
        """Saves the canonical JSON representation of the manifest to MinIO."""
        # Convert the string to bytes
        data = payload_json.encode("utf-8")
        # MinioStorage uses sync upload
        self.storage.upload_bytes(f"{manifest_hash}.json", data, content_type="application/json")

    def get_manifest(self, manifest_hash: str) -> str:
        """Retrieves the manifest from MinIO."""
        return self.storage.download_string(f"{manifest_hash}.json")
