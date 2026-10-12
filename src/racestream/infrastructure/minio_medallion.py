"""Acesso aos resultados ouro de corrida armazenados no MinIO local."""

import json
import os
import re
from importlib import import_module
from typing import Any


class MinioRaceMedallion:
    """Leia o resumo JSON que acompanha a tabela ouro de uma corrida."""

    def __init__(self, client: Any | None = None) -> None:
        self._client = client
        self._endpoint = os.environ.get("MINIO_ENDPOINT", "http://minio:9000")
        self._access_key = os.environ.get("MINIO_ROOT_USER", "racestream")
        self._secret_key = os.environ.get(
            "MINIO_ROOT_PASSWORD", "racestream-local-only"
        )
        self._bucket = os.environ.get("MINIO_BUCKET", "racestream")

    def get_gold_results(self, race_id: str) -> dict[str, Any] | None:
        """Leia o resultado ouro, retornando ``None`` enquanto ele não existe."""
        if not re.fullmatch(r"[A-Za-z0-9_-]+", race_id):
            return None
        client = self._get_client()
        object_name = f"corridas/{race_id}/ouro/resumo.json"
        try:
            response = client.get_object(self._bucket, object_name)
            try:
                payload = json.loads(response.read())
            finally:
                response.close()
                response.release_conn()
        except Exception as error:
            if getattr(error, "code", None) in {
                "NoSuchKey",
                "NoSuchObject",
                "NoSuchBucket",
            }:
                return None
            raise
        if not isinstance(payload, dict) or payload.get("race_id") != race_id:
            return None
        return payload

    def _get_client(self) -> Any:
        """Crie o cliente S3 apenas quando uma rota consultar o resultado."""
        if self._client is None:
            from urllib.parse import urlsplit

            endpoint = urlsplit(self._endpoint)
            if not endpoint.netloc:
                raise ValueError("MINIO_ENDPOINT precisa conter um host")
            minio = import_module("minio")
            self._client = minio.Minio(
                endpoint.netloc,
                access_key=self._access_key,
                secret_key=self._secret_key,
                secure=endpoint.scheme == "https",
            )
        return self._client
