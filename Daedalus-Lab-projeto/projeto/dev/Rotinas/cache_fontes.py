######################### BIBLIOTECAS ###################################
import logging
import os
import time
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from sqlalchemy import text
from sqlalchemy.orm import Session
#########################################################################

"""Cache das páginas/PDFs lidos e log das consultas externas.

Usa as tabelas fonte_consultada e log_consulta_externa
(ver Rotinas/tabelas_fontes_consultadas.sql).
Se o banco não estiver acessível, as consultas seguem sem cache e sem log:
o erro é apenas registrado no logging, para não interromper o agente.
"""

logger = logging.getLogger(__name__)

DIAS_VALIDADE_CACHE = int(os.getenv("DAEDALUS_DIAS_VALIDADE_CACHE", "90"))
_SEGUNDOS_ESPERA_BANCO = 60

_id_projeto: ContextVar[int | None] = ContextVar("id_projeto", default=None)
_nm_agente: ContextVar[str | None] = ContextVar("nm_agente", default=None)
_banco_indisponivel_ate = 0.0
# Cópia em memória: evita pagar de novo pela mesma URL no mesmo processo quando o banco falha.
_cache_memoria: dict[str, dict] = {}


def definir_contexto(id_projeto: int | None, nm_agente: str | None) -> None:
    """Define o projeto e o agente que aparecem no log das próximas consultas."""
    _id_projeto.set(id_projeto)
    _nm_agente.set(nm_agente)


def contexto_atual() -> tuple[int | None, str | None]:
    return _id_projeto.get(), _nm_agente.get()


def _executar(comando, parametros: dict, *, buscar: str | None = None):
    """Executa SQL no banco do projeto. buscar: None, "um" ou "valor"."""
    global _banco_indisponivel_ate
    if time.monotonic() < _banco_indisponivel_ate:
        return None
    try:
        from database import engine

        with Session(engine) as session:
            with session.begin():
                resultado = session.execute(comando, parametros)
                if buscar == "um":
                    linha = resultado.mappings().first()
                    return dict(linha) if linha else None
                if buscar == "valor":
                    return resultado.scalar()
                return None
    except Exception as erro:
        _banco_indisponivel_ate = time.monotonic() + _SEGUNDOS_ESPERA_BANCO
        logger.warning("Cache/log indisponível, seguindo sem banco: %s", erro)
        return None


def buscar_fonte(ds_url_normalizada: str) -> dict | None:
    """Devolve a fonte em cache para a URL, se existir e não estiver expirada."""
    fonte = _executar(
        text("""
            SELECT *
            FROM fonte_consultada
            WHERE ds_url_normalizada = :ds_url_normalizada
              AND (dt_expiracao IS NULL OR dt_expiracao > now())
        """),
        {"ds_url_normalizada": ds_url_normalizada},
        buscar="um",
    )
    if fonte:
        return fonte
    fonte = _cache_memoria.get(ds_url_normalizada)
    if fonte and fonte["dt_expiracao"] > datetime.now(timezone.utc):
        return dict(fonte)
    return None


def salvar_fonte(
    *,
    ds_url: str,
    ds_url_normalizada: str,
    nm_dominio: str,
    tp_conteudo: str,
    tp_nivel_fonte: str | None,
    ds_titulo: str | None,
    ds_conteudo: str | None,
    nr_paginas_pdf: int | None,
    nr_paginas_lidas: int | None,
    fl_pdf_truncado: bool,
    cd_http_status: int | None,
    ds_hash_conteudo: str | None,
    ds_doi: str | None = None,
) -> int | None:
    """Grava (ou atualiza) a fonte lida e devolve o id_fonte."""
    agora = datetime.now(timezone.utc)
    parametros = {
        "ds_url": ds_url,
        "ds_url_normalizada": ds_url_normalizada,
        "nm_dominio": nm_dominio[:255],
        "tp_conteudo": tp_conteudo,
        "tp_nivel_fonte": tp_nivel_fonte,
        "ds_titulo": ds_titulo,
        "ds_conteudo": ds_conteudo,
        "nr_paginas_pdf": nr_paginas_pdf,
        "nr_paginas_lidas": nr_paginas_lidas,
        "fl_pdf_truncado": fl_pdf_truncado,
        "cd_http_status": cd_http_status,
        "ds_hash_conteudo": ds_hash_conteudo,
        "ds_doi": ds_doi[:255] if ds_doi else None,
        "dt_consulta": agora,
        "dt_expiracao": agora + timedelta(days=DIAS_VALIDADE_CACHE),
    }
    id_fonte = _executar(
        text("""
            INSERT INTO fonte_consultada (
                ds_url, ds_url_normalizada, nm_dominio, tp_conteudo, tp_nivel_fonte,
                ds_titulo, ds_conteudo, nr_paginas_pdf, nr_paginas_lidas, fl_pdf_truncado,
                cd_http_status, ds_hash_conteudo, ds_doi, dt_consulta, dt_expiracao
            )
            VALUES (
                :ds_url, :ds_url_normalizada, :nm_dominio, :tp_conteudo, :tp_nivel_fonte,
                :ds_titulo, :ds_conteudo, :nr_paginas_pdf, :nr_paginas_lidas, :fl_pdf_truncado,
                :cd_http_status, :ds_hash_conteudo, :ds_doi, :dt_consulta, :dt_expiracao
            )
            ON CONFLICT (ds_url_normalizada) DO UPDATE SET
                ds_url = EXCLUDED.ds_url,
                tp_conteudo = EXCLUDED.tp_conteudo,
                tp_nivel_fonte = EXCLUDED.tp_nivel_fonte,
                ds_titulo = EXCLUDED.ds_titulo,
                ds_conteudo = EXCLUDED.ds_conteudo,
                nr_paginas_pdf = EXCLUDED.nr_paginas_pdf,
                nr_paginas_lidas = EXCLUDED.nr_paginas_lidas,
                fl_pdf_truncado = EXCLUDED.fl_pdf_truncado,
                cd_http_status = EXCLUDED.cd_http_status,
                ds_hash_conteudo = EXCLUDED.ds_hash_conteudo,
                ds_doi = COALESCE(EXCLUDED.ds_doi, fonte_consultada.ds_doi),
                dt_consulta = EXCLUDED.dt_consulta,
                dt_expiracao = EXCLUDED.dt_expiracao
            RETURNING id_fonte
        """),
        parametros,
        buscar="valor",
    )
    _cache_memoria[ds_url_normalizada] = {**parametros, "id_fonte": id_fonte}
    return id_fonte


def registrar_consulta(
    nm_servico: str,
    tp_operacao: str,
    ds_consulta: str,
    *,
    id_fonte: int | None = None,
    fl_cache: bool = False,
    vl_creditos: int = 0,
    ds_erro: str | None = None,
) -> None:
    """Registra uma chamada de ferramenta externa no log (projeto, agente, créditos)."""
    id_projeto, nm_agente = contexto_atual()
    _executar(
        text("""
            INSERT INTO log_consulta_externa (
                id_projeto, nm_agente, nm_servico, tp_operacao, ds_consulta,
                id_fonte, fl_cache, vl_creditos, ds_erro
            )
            VALUES (
                :id_projeto, :nm_agente, :nm_servico, :tp_operacao, :ds_consulta,
                :id_fonte, :fl_cache, :vl_creditos, :ds_erro
            )
        """),
        {
            "id_projeto": id_projeto,
            "nm_agente": nm_agente[:100] if nm_agente else None,
            "nm_servico": nm_servico,
            "tp_operacao": tp_operacao,
            "ds_consulta": ds_consulta,
            "id_fonte": id_fonte,
            "fl_cache": fl_cache,
            "vl_creditos": int(vl_creditos or 0),
            "ds_erro": ds_erro,
        },
    )


def creditos_utilizados(id_projeto: int, nm_servico: str = "firecrawl") -> int | None:
    """Soma os créditos já gastos pelo projeto no serviço (None se o banco estiver indisponível)."""
    total = _executar(
        text("""
            SELECT COALESCE(SUM(vl_creditos), 0)
            FROM log_consulta_externa
            WHERE id_projeto = :id_projeto AND nm_servico = :nm_servico
        """),
        {"id_projeto": id_projeto, "nm_servico": nm_servico},
        buscar="valor",
    )
    return int(total) if total is not None else None
