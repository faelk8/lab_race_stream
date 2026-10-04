"""Atualize o índice local do RaceStream no Jota sem expor credenciais."""

import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

from dotenv import load_dotenv


def main() -> None:
    """Envie somente o caminho do projeto ao indexador local autenticado."""
    load_dotenv(Path.home() / "Documentos/github/j-ai/.env")
    root = Path(__file__).resolve().parents[1]
    headers = {"Content-Type": "application/json"}
    token = os.environ.get("JOTA_API_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(
        "http://127.0.0.1:8765/v1/projects/index",
        data=json.dumps({"path": str(root), "client_id": "codex-racestream"}).encode(),
        headers=headers,
        method="POST",
    )
    with urlopen(request, timeout=120) as response:
        result = json.load(response)
    if not result.get("project_id"):
        raise RuntimeError("O Jota não confirmou o projeto indexado")
    context = root / "docs/jota-contexto.md"
    if context.exists():
        knowledge = Request(
            "http://127.0.0.1:8765/v1/knowledge",
            data=json.dumps(
                {
                    "project_id": result["project_id"],
                    "problem": "RaceStream: regras, decisões e estado da implementação",
                    "solution": context.read_text(),
                    "source": str(context),
                    "scope": "projeto",
                    "state": "proposto",
                }
            ).encode(),
            headers=headers,
            method="POST",
        )
        with urlopen(knowledge, timeout=30) as response:
            result["contexto"] = json.load(response)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
