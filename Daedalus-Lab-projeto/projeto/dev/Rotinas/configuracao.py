"""Carrega as variáveis de ambiente do projeto a partir de arquivos locais.

Ordem de leitura (a primeira definição vence; variáveis já definidas no sistema não são sobrescritas):
  1. projeto/dev/.env        chaves de API e configurações (modelo em projeto/dev/.env.exemplo)
  2. projeto/container/env   variáveis do Postgres usadas pelo Docker Compose

Instalação: python -m pip install python-dotenv
"""
import logging
from pathlib import Path

_PASTA_DEV = Path(__file__).resolve().parents[1]
ARQUIVOS_ENV = [_PASTA_DEV / ".env", _PASTA_DEV.parent / "container" / "env"]

logger = logging.getLogger(__name__)


def carregar_variaveis() -> list[str]:
    """Carrega os arquivos de ARQUIVOS_ENV que existirem e devolve os caminhos lidos."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        logger.warning("python-dotenv não instalado; usando só as variáveis do sistema.")
        return []
    lidos = []
    for arquivo in ARQUIVOS_ENV:
        if arquivo.is_file():
            load_dotenv(arquivo, override=False)
            lidos.append(str(arquivo))
    return lidos


carregar_variaveis()
