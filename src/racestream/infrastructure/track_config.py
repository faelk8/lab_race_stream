"""Leitura da configuração versionada de pista."""

import json
import os
from pathlib import Path

from racestream.domain.track import Track


def load_track() -> Track:
    """Carregue a geometria física selecionada para a sessão."""
    path = Path(os.environ.get("RACE_TRACK_CONFIG", "config/interlagos-v1.json"))
    return Track(**json.loads(path.read_text()))
