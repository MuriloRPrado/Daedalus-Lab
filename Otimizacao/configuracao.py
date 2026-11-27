"""Caminhos e variáveis de ambiente do módulo Otimizacao.

As variáveis são lidas de Otimizacao/.env (modelo em .env.exemplo); variáveis já definidas
no sistema não são sobrescritas.
"""
import logging
from pathlib import Path

PASTA_OTIMIZACAO = Path(__file__).resolve().parent
ARQUIVO_ENV = PASTA_OTIMIZACAO / ".env"
PASTA_DADOS = PASTA_OTIMIZACAO / "dados"
PASTA_CACHE = PASTA_DADOS / "cache"
PASTA_MODELOS = PASTA_OTIMIZACAO / "modelos"

logger = logging.getLogger(__name__)


def carregar_variaveis() -> bool:
    try:
        from dotenv import load_dotenv
    except ImportError:
        logger.warning("python-dotenv não instalado; usando só as variáveis do sistema.")
        return False
    return bool(ARQUIVO_ENV.is_file() and load_dotenv(ARQUIVO_ENV, override=False))


carregar_variaveis()
