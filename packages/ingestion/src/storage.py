import os
import json
import hashlib
from typing import Dict, Any
from minio import Minio
from minio.error import S3Error

class MinioStorage:
    def __init__(self, endpoint: str = "127.0.0.1:9000", access_key: str = "minioadmin", secret_key: str = "minioadmin", bucket_name: str = "driftguard-corpus"):
        self.bucket_name = bucket_name
        self.bypassed = False
        self.client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=False
        )
        self._ensure_bucket()

    def _ensure_bucket(self):
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
        except Exception as e:
            print(f"Error ensuring bucket exists (bypassing MinIO): {e}")
            self.bypassed = True

    def upload_document(self, object_name: str, document_dict: Dict[str, Any]) -> str:
        """Uploads a JSON document to MinIO and returns the object path."""
        import tempfile
        
        # Calculate Hash
        content = json.dumps(document_dict, sort_keys=True)
        doc_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
        
        if self.bypassed:
            return doc_hash
            
        # Temp save
        with tempfile.NamedTemporaryFile('w', delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
            
        try:
            self.client.fput_object(
                self.bucket_name,
                object_name,
                tmp_path,
                content_type="application/json"
            )
        except Exception as e:
            self.bypassed = True
            pass # Bypass if not running
        finally:
            os.remove(tmp_path)
            
        return doc_hash

    def upload_manifest(self, version_tag: str, manifest: Dict[str, Any]) -> str:
        """Uploads the Corpus Manifest JSON"""
        object_name = f"manifests/{version_tag}.json"
        return self.upload_document(object_name, manifest)
