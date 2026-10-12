"""Testes da leitura MinIO assinada sem depender de serviços externos."""

from racestream.infrastructure.minio_medallion import MinioRaceMedallion


class FakeResponse:
    """Resposta de objeto em memória."""

    def read(self) -> bytes:
        """Devolva um JSON de classificação pequeno."""
        return b'{"race_id":"race-1","classification":[]}'

    def close(self) -> None:
        """Implemente o fechamento do corpo HTTP."""

    def release_conn(self) -> None:
        """Implemente a liberação da conexão usada pelo SDK."""


class FakeMinioClient:
    """Cliente MinIO falso que registra o objeto consultado."""

    def __init__(self) -> None:
        self.object_name = ""

    def get_object(self, bucket: str, object_name: str) -> FakeResponse:
        """Retorne o resumo solicitado do bucket de teste."""
        assert bucket == "racestream"
        self.object_name = object_name
        return FakeResponse()


def test_leitura_ouro_valida_corrida_e_monta_o_prefixo_minio() -> None:
    """O adapter lê o objeto esperado e confere a identidade da corrida."""
    client = FakeMinioClient()
    adapter = MinioRaceMedallion(client)
    resultado = adapter.get_gold_results("race-1")

    assert resultado == {"race_id": "race-1", "classification": []}
    assert client.object_name == "corridas/race-1/ouro/resumo.json"


def test_identificador_de_corrida_nao_pode_mudar_o_prefixo_minio() -> None:
    """O endpoint não aceita separadores de caminho como ID de corrida."""
    assert MinioRaceMedallion().get_gold_results("../outro-bucket") is None
