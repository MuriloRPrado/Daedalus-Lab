"""Artigos científicos para Daedalus: OpenAlex (descoberta), Unpaywall (PDF aberto) e Firecrawl (leitura).

Instalação: python -m pip install requests
Variáveis de ambiente:
  OPENALEX_API_KEY        chave gratuita do OpenAlex (sem ela, o limite diário é compartilhado por IP)
  DAEDALUS_EMAIL_CONTATO  e-mail de contato do projeto, exigido pelo Unpaywall
  FIRECRAWL_API_KEY       usada na leitura do PDF (ver Rotinas/firecrawl_api.py)

Exemplos (PowerShell, na pasta dev):
  python -m Rotinas.consulta_artigos buscar "7075 T6 stress corrosion cracking"
  python -m Rotinas.consulta_artigos pdf 10.3390/met9020224
  python -m Rotinas.consulta_artigos ler 10.3390/met9020224

Somente artigos de acesso aberto são lidos. O resumo do OpenAlex não equivale a
leitura do artigo: use ler_artigo para abrir o texto completo.
"""
######################### BIBLIOTECAS ###################################
import argparse
import json
import os
import re
from datetime import datetime, timezone
from urllib.parse import quote

import requests

from Rotinas.cache_fontes import registrar_consulta
from Rotinas.fontes_firecrawl import NIVEL_ARTIGO, dominio_bloqueado
from Rotinas.firecrawl_api import ler_documento
#########################################################################

OPENALEX_URL = "https://api.openalex.org/works"
UNPAYWALL_URL = "https://api.unpaywall.org/v2/"
MAX_RESUMO = 1500
_CAMPOS_OPENALEX = ",".join([
    "id", "doi", "title", "publication_year", "type", "cited_by_count", "authorships",
    "primary_location", "open_access", "best_oa_location", "abstract_inverted_index",
])


class ErroArtigos(RuntimeError):
    """Erro devolvido pelo OpenAlex ou pelo Unpaywall."""


def _texto(valor: str, nome: str) -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"{nome} deve ser um texto não vazio.")
    return valor.strip()


def _normalizar_doi(doi: str) -> str:
    doi = _texto(doi, "doi").lower()
    doi = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:)", "", doi)
    if not re.fullmatch(r"10\.\d{4,9}/\S+", doi):
        raise ValueError("DOI inválido. Exemplo de formato: 10.3390/met9020224.")
    return doi


def _email() -> str:
    email = os.getenv("DAEDALUS_EMAIL_CONTATO", "").strip()
    if not email:
        raise ValueError("Defina DAEDALUS_EMAIL_CONTATO no ambiente (exigido pelo Unpaywall).")
    return email


def _get(servico: str, url: str, parametros: dict, consulta: str) -> dict:
    try:
        resposta = requests.get(url, params=parametros, timeout=(10, 60))
    except requests.RequestException as erro:
        mensagem = f"Falha de conexão com {servico}: {erro.__class__.__name__}."
        registrar_consulta(servico, "busca", consulta, ds_erro=mensagem)
        raise ErroArtigos(mensagem) from None
    if resposta.status_code == 404:
        registrar_consulta(servico, "busca", consulta, ds_erro="HTTP 404")
        return {}
    if resposta.status_code >= 400:
        mensagem = f"{servico} HTTP {resposta.status_code}: {resposta.text[:300]}"
        registrar_consulta(servico, "busca", consulta, ds_erro=mensagem)
        raise ErroArtigos(mensagem)
    registrar_consulta(servico, "busca", consulta)
    return resposta.json()


def _resumo(indice: dict | None) -> str | None:
    if not indice:
        return None
    posicoes = {posicao: palavra for palavra, lista in indice.items() for posicao in lista}
    texto = " ".join(posicoes[i] for i in sorted(posicoes))
    return texto if len(texto) <= MAX_RESUMO else texto[:MAX_RESUMO] + "..."


def _artigo(obra: dict) -> dict:
    local = obra.get("primary_location") or {}
    aberto = obra.get("open_access") or {}
    melhor = obra.get("best_oa_location") or {}
    doi = obra.get("doi")
    return {
        "id_openalex": obra.get("id"),
        "doi": re.sub(r"^https?://doi\.org/", "", doi) if doi else None,
        "titulo": obra.get("title"),
        "ano": obra.get("publication_year"),
        "tipo": obra.get("type"),
        "autores": [
            (a.get("author") or {}).get("display_name")
            for a in (obra.get("authorships") or [])[:5]
        ],
        "periodico": (local.get("source") or {}).get("display_name"),
        "citacoes": obra.get("cited_by_count"),
        "acesso_aberto": aberto.get("is_oa"),
        "status_acesso": aberto.get("oa_status"),
        "url_acesso_aberto": aberto.get("oa_url"),
        "url_pdf": melhor.get("pdf_url"),
        "licenca": melhor.get("license"),
        "resumo": _resumo(obra.get("abstract_inverted_index")),
        "tipo_acesso": "resultado_de_busca",
    }


def buscar_artigos_openalex(consulta: str, quantidade: int = 10, somente_acesso_aberto: bool = True,
                            ano_inicial: int | None = None) -> dict:
    """Busca artigos científicos no OpenAlex e devolve título, DOI, autores, ano, citações, resumo e link do PDF aberto.

    O resumo não equivale a leitura do artigo. Para ler o texto completo de um artigo de
    acesso aberto, use ler_artigo com o DOI.

    Args:
        consulta: termos da busca, de preferência em inglês (ex.: "7075 T6 stress corrosion cracking").
        quantidade: número de artigos (1 a 25).
        somente_acesso_aberto: se verdadeiro, devolve apenas artigos com texto completo aberto.
        ano_inicial: opcional; ano mínimo de publicação (ex.: 2015).
    """
    consulta = _texto(consulta, "consulta")
    quantidade = max(1, min(int(quantidade), 25))
    filtros = []
    if somente_acesso_aberto:
        filtros.append("open_access.is_oa:true")
    if ano_inicial:
        filtros.append(f"from_publication_date:{int(ano_inicial)}-01-01")
    parametros = {"search": consulta, "per_page": quantidade, "select": _CAMPOS_OPENALEX}
    if filtros:
        parametros["filter"] = ",".join(filtros)
    chave = os.getenv("OPENALEX_API_KEY", "").strip()
    if chave:
        parametros["api_key"] = chave
    email = os.getenv("DAEDALUS_EMAIL_CONTATO", "").strip()
    if email:
        parametros["mailto"] = email

    resposta = _get("openalex", OPENALEX_URL, parametros, consulta)
    artigos = [_artigo(obra) for obra in resposta.get("results") or []]
    return {
        "fonte": "OpenAlex",
        "consulta": consulta,
        "parametros": {"quantidade": quantidade, "somente_acesso_aberto": somente_acesso_aberto, "ano_inicial": ano_inicial},
        "consultado_em_utc": datetime.now(timezone.utc).isoformat(),
        "total_encontrado": (resposta.get("meta") or {}).get("count"),
        "dados": artigos,
    }


def localizar_pdf_aberto(doi: str) -> dict:
    """Consulta o Unpaywall e devolve os links legais de acesso aberto (PDF e página) de um artigo pelo DOI.

    Args:
        doi: DOI do artigo (ex.: "10.3390/met9020224").
    """
    doi = _normalizar_doi(doi)
    resposta = _get("unpaywall", UNPAYWALL_URL + quote(doi, safe="/"), {"email": _email()}, doi)
    locais = []
    for local in resposta.get("oa_locations") or []:
        locais.append({
            "url_pdf": local.get("url_for_pdf"),
            "url_pagina": local.get("url_for_landing_page") or local.get("url"),
            "hospedagem": local.get("host_type"),
            "versao": local.get("version"),
            "licenca": local.get("license"),
            "melhor_opcao": local.get("is_best", False),
        })
    melhor = resposta.get("best_oa_location") or {}
    return {
        "fonte": "Unpaywall",
        "consulta": doi,
        "parametros": {},
        "consultado_em_utc": datetime.now(timezone.utc).isoformat(),
        "dados": {
            "doi": doi,
            "encontrado": bool(resposta),
            "titulo": resposta.get("title"),
            "ano": resposta.get("year"),
            "periodico": resposta.get("journal_name"),
            "acesso_aberto": resposta.get("is_oa", False),
            "status_acesso": resposta.get("oa_status"),
            "url_pdf": melhor.get("url_for_pdf"),
            "url_pagina": melhor.get("url_for_landing_page") or melhor.get("url"),
            "licenca": melhor.get("license"),
            "versao": melhor.get("version"),
            "locais_acesso_aberto": locais,
        },
    }


def ler_artigo(doi: str, max_paginas_pdf: int = 15, inicio: int = 0) -> dict:
    """Localiza o PDF de acesso aberto do artigo (Unpaywall) e lê o texto completo pelo Firecrawl.

    Artigos sem versão aberta não são lidos: o retorno informa isso e traz a página do artigo.
    O texto lido fica no cache: reler o mesmo artigo não gasta créditos. O conteúdo vem em
    trechos; se "proximo_inicio" não for nulo, chame de novo com inicio=proximo_inicio.

    Args:
        doi: DOI do artigo (ex.: "10.3390/met9020224").
        max_paginas_pdf: máximo de páginas do PDF a ler (1 a 50). Cada página custa 1 crédito.
        inicio: posição (em caracteres) a partir da qual o conteúdo é devolvido.
    """
    localizacao = localizar_pdf_aberto(doi)["dados"]
    candidatos = [localizacao.get("url_pdf")] + [l["url_pdf"] for l in localizacao["locais_acesso_aberto"]]
    candidatos = [u for i, u in enumerate(candidatos) if u and u not in candidatos[:i] and not dominio_bloqueado(u)]
    if not candidatos and localizacao.get("url_pagina") and localizacao.get("acesso_aberto"):
        candidatos = [localizacao["url_pagina"]]

    if not candidatos:
        return {
            "fonte": "Unpaywall",
            "consulta": localizacao["doi"],
            "parametros": {},
            "consultado_em_utc": datetime.now(timezone.utc).isoformat(),
            "dados": {
                "doi": localizacao["doi"],
                "titulo": localizacao.get("titulo"),
                "lido": False,
                "motivo": "Nenhuma versão de acesso aberto encontrada. O artigo não foi lido.",
                "url_artigo": f"https://doi.org/{localizacao['doi']}",
            },
        }

    erros = []
    for url in candidatos[:3]:
        try:
            resultado = ler_documento(url, max_paginas_pdf=max_paginas_pdf, inicio=inicio,
                                      doi=localizacao["doi"], nivel_fonte=NIVEL_ARTIGO)
        except Exception as erro:
            erros.append(f"{url}: {erro}")
            continue
        resultado["dados"].update(
            doi=localizacao["doi"],
            titulo=resultado["dados"].get("titulo") or localizacao.get("titulo"),
            licenca=localizacao.get("licenca"),
            versao=localizacao.get("versao"),
            lido=True,
        )
        return resultado
    raise ErroArtigos("Não foi possível ler nenhuma versão aberta do artigo. " + " | ".join(erros))


def _main() -> None:
    analisador = argparse.ArgumentParser(description="Consulta de artigos do Daedalus Lab.")
    sub = analisador.add_subparsers(dest="comando", required=True)
    p = sub.add_parser("buscar")
    p.add_argument("consulta")
    p.add_argument("--quantidade", type=int, default=10)
    p.add_argument("--todos", action="store_true", help="inclui artigos sem acesso aberto")
    p.add_argument("--ano-inicial", type=int)
    p = sub.add_parser("pdf")
    p.add_argument("doi")
    p = sub.add_parser("ler")
    p.add_argument("doi")
    p.add_argument("--max-paginas-pdf", type=int, default=15)
    p.add_argument("--inicio", type=int, default=0)
    argumentos = analisador.parse_args()

    if argumentos.comando == "buscar":
        resultado = buscar_artigos_openalex(argumentos.consulta, argumentos.quantidade,
                                            not argumentos.todos, argumentos.ano_inicial)
    elif argumentos.comando == "pdf":
        resultado = localizar_pdf_aberto(argumentos.doi)
    else:
        resultado = ler_artigo(argumentos.doi, argumentos.max_paginas_pdf, argumentos.inicio)
    print(json.dumps(resultado, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    _main()
