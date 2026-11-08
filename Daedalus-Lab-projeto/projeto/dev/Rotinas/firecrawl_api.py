"""Firecrawl para Daedalus: busca na web, busca de fichas técnicas e leitura de páginas/PDFs.

Instalação: python -m pip install requests
Chave: variável de ambiente FIRECRAWL_API_KEY. Sem chave, a API aceita busca e
leitura em modo keyless, com limite diário por IP (use apenas para testes).
Limite opcional: FIRECRAWL_LIMITE_CREDITOS_PROJETO (créditos por projeto).

Exemplos (PowerShell, na pasta dev):
  python -m Rotinas.firecrawl_api buscar "17-4PH heat treatment"
  python -m Rotinas.firecrawl_api fichas "duplex 2205" --fabricantes Outokumpu Alleima
  python -m Rotinas.firecrawl_api ler "https://www.alleima.com/en/technical-center/material-datasheets/..."

Custos (documentação Firecrawl): busca = 2 créditos a cada 10 resultados;
leitura de página = 1 crédito; PDF = 1 crédito por página lida.
Páginas lidas ficam no cache (tabela fonte_consultada): reler a mesma URL não gasta créditos.
Resultados de busca são fontes ENCONTRADAS; somente ler_pagina devolve documento LIDO.
"""
######################### BIBLIOTECAS ###################################
import argparse
import hashlib
import json
import os
import time
from datetime import datetime, timezone

import requests

from Rotinas.cache_fontes import buscar_fonte, contexto_atual, creditos_utilizados, registrar_consulta, salvar_fonte
from Rotinas.fontes_firecrawl import (
    classificar_fonte,
    dominio_bloqueado,
    dominios_bloqueados_busca,
    dominios_fabricantes,
    nome_fabricante,
    normalizar_url,
    obter_dominio,
)
#########################################################################

BASE_URL = "https://api.firecrawl.dev/v2"
SERVICO = "firecrawl"
MAX_PAGINAS_PDF = 50
MAX_CARACTERES = 100_000


class ErroFirecrawl(RuntimeError):
    """Erro devolvido pela API do Firecrawl."""


def _texto(valor: str, nome: str) -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"{nome} deve ser um texto não vazio.")
    return valor.strip()


def _limitar(valor: int, minimo: int, maximo: int) -> int:
    return max(minimo, min(int(valor), maximo))


def _verificar_limite(creditos_previstos: int) -> None:
    limite = os.getenv("FIRECRAWL_LIMITE_CREDITOS_PROJETO", "").strip()
    id_projeto, _ = contexto_atual()
    if not limite or id_projeto is None:
        return
    usados = creditos_utilizados(id_projeto)
    if usados is not None and usados + creditos_previstos > int(limite):
        raise ErroFirecrawl(
            f"Limite de créditos do projeto atingido ({usados}/{limite}). "
            "Use as fontes já lidas (ler_pagina usa o cache sem custo)."
        )


def _requisitar(caminho: str, corpo: dict, *, timeout: int = 120) -> dict:
    cabecalhos = {"Content-Type": "application/json"}
    chave = os.getenv("FIRECRAWL_API_KEY", "").strip()
    if chave:
        cabecalhos["Authorization"] = f"Bearer {chave}"

    for tentativa in range(2):
        try:
            resposta = requests.post(BASE_URL + caminho, headers=cabecalhos, json=corpo, timeout=(10, timeout))
        except requests.RequestException as erro:
            raise ErroFirecrawl(f"Falha de conexão com o Firecrawl: {erro.__class__.__name__}.") from None

        if resposta.status_code == 429 and tentativa == 0:
            espera = resposta.headers.get("Retry-After", "")
            time.sleep(min(int(espera), 30) if espera.isdigit() else 10)
            continue
        break

    try:
        dados = resposta.json()
    except ValueError:
        dados = {}
    if resposta.status_code >= 400 or not dados.get("success", False):
        detalhe = dados.get("error") or dados.get("message") or resposta.text[:300]
        raise ErroFirecrawl(f"Firecrawl HTTP {resposta.status_code}: {detalhe}")
    return dados


def _retorno(consulta: str, parametros: dict, dados, **extras) -> dict:
    return {
        "fonte": "Firecrawl",
        "consulta": consulta,
        "parametros": parametros,
        "consultado_em_utc": datetime.now(timezone.utc).isoformat(),
        **extras,
        "dados": dados,
    }


def _buscar(consulta: str, parametros: dict, *, tipo: str, dominios: list[str] | None, limite: int) -> dict:
    corpo = {"query": consulta, "limit": limite, "sources": [{"type": "web"}], "ignoreInvalidURLs": True}
    if tipo == "pdf":
        corpo["categories"] = ["pdf"]
    if dominios:
        corpo["includeDomains"] = dominios
    else:
        corpo["excludeDomains"] = dominios_bloqueados_busca()

    _verificar_limite(2 * ((limite + 9) // 10))
    try:
        resposta = _requisitar("/search", corpo)
    except ErroFirecrawl as erro:
        registrar_consulta(SERVICO, "busca", consulta, ds_erro=str(erro))
        raise
    creditos = int(resposta.get("creditsUsed") or 0)
    registrar_consulta(SERVICO, "busca", consulta, vl_creditos=creditos)

    resultados, removidos = [], 0
    for item in (resposta.get("data") or {}).get("web") or []:
        url = item.get("url") or ""
        if not url or dominio_bloqueado(url):
            removidos += 1
            continue
        resultados.append({
            "titulo": item.get("title"),
            "url": url,
            "descricao": item.get("description"),
            "dominio": obter_dominio(url),
            "nivel_fonte": classificar_fonte(url),
            "fabricante": nome_fabricante(url),
            "tipo_acesso": "resultado_de_busca",
        })

    return _retorno(
        consulta, parametros, resultados,
        creditos_utilizados=creditos,
        resultados_bloqueados_removidos=removidos,
        observacao="Resultados de busca: título e descrição não equivalem a documento lido. Use ler_pagina para conferir o conteúdo.",
    )


def buscar_web(consulta: str, tipo: str = "web", dominios: list[str] | None = None, limite: int = 10) -> dict:
    """Busca na web e devolve títulos, URLs e descrições, sem ler as páginas.

    Exclui automaticamente as fontes bloqueadas pelo projeto. Cada resultado traz o
    nível da fonte (fabricante, referencia_aberta, complementar, indice_norma ou
    nao_classificada). Custa 2 créditos a cada 10 resultados.

    Args:
        consulta: termos da busca, de preferência em inglês (ex.: "Inconel 718 aging heat treatment").
        tipo: "web" para qualquer página ou "pdf" para priorizar documentos PDF.
        dominios: opcional; restringe a busca a esses domínios (ex.: ["outokumpu.com"]).
        limite: número de resultados (1 a 20).
    """
    consulta = _texto(consulta, "consulta")
    if tipo not in ("web", "pdf"):
        raise ValueError('tipo deve ser "web" ou "pdf".')
    limite = _limitar(limite, 1, 20)
    if dominios:
        dominios = [obter_dominio(d if "://" in d else f"https://{d}") for d in dominios if d and d.strip()]
        bloqueados = [d for d in dominios if dominio_bloqueado(f"https://{d}/")]
        if bloqueados:
            raise ValueError(f"Domínios bloqueados pelo projeto: {', '.join(bloqueados)}.")
    parametros = {"tipo": tipo, "dominios": dominios, "limite": limite}
    return _buscar(consulta, parametros, tipo=tipo, dominios=dominios or None, limite=limite)


def buscar_fichas_tecnicas(material: str, fabricantes: list[str] | None = None, limite: int = 10) -> dict:
    """Busca fichas técnicas (datasheets) do material somente nos sites de fabricantes.

    Fabricantes cobertos: Outokumpu, Alleima (antiga Sandvik), Aperam, Villares Metals,
    Gerdau, Carpenter Technology, ATI, Haynes International, Special Metals,
    Böhler/voestalpine e Aalco. Devolve apenas os links; use ler_pagina para ler a ficha.
    Custa 2 créditos a cada 10 resultados.

    Args:
        material: designação do material (ex.: "duplex 2205", "17-4PH", "Inconel 625", "AISI 4140").
        fabricantes: opcional; nomes dos fabricantes para restringir (ex.: ["Outokumpu", "Villares"]).
        limite: número de resultados (1 a 20).
    """
    material = _texto(material, "material")
    limite = _limitar(limite, 1, 20)
    dominios = dominios_fabricantes(fabricantes)
    consulta = f"{material} datasheet chemical composition mechanical properties"
    parametros = {"material": material, "fabricantes": fabricantes, "limite": limite}
    return _buscar(consulta, parametros, tipo="web", dominios=dominios, limite=limite)


def _recorte(conteudo: str, inicio: int, max_caracteres: int) -> tuple[str, int | None]:
    fim = inicio + max_caracteres
    return conteudo[inicio:fim], (fim if fim < len(conteudo) else None)


def _dados_leitura(fonte: dict, *, url: str, inicio: int, max_caracteres: int, veio_do_cache: bool,
                   nivel_fonte: str | None, creditos: int) -> dict:
    conteudo = fonte.get("ds_conteudo") or ""
    trecho, proximo = _recorte(conteudo, inicio, max_caracteres)
    dt_consulta = fonte.get("dt_consulta")
    return {
        "url": url,
        "titulo": fonte.get("ds_titulo"),
        "dominio": fonte.get("nm_dominio"),
        "nivel_fonte": nivel_fonte or fonte.get("tp_nivel_fonte"),
        "fabricante": nome_fabricante(url),
        "tipo_conteudo": fonte.get("tp_conteudo"),
        "tipo_acesso": "documento_lido",
        "http_status": fonte.get("cd_http_status"),
        "paginas_pdf_total": fonte.get("nr_paginas_pdf"),
        "paginas_pdf_lidas": fonte.get("nr_paginas_lidas"),
        "pdf_truncado": bool(fonte.get("fl_pdf_truncado")),
        "doi": fonte.get("ds_doi"),
        "id_fonte": fonte.get("id_fonte"),
        "hash_conteudo_sha256": fonte.get("ds_hash_conteudo"),
        "lido_em_utc": dt_consulta.isoformat() if hasattr(dt_consulta, "isoformat") else dt_consulta,
        "veio_do_cache": veio_do_cache,
        "creditos_utilizados": creditos,
        "caracteres_total": len(conteudo),
        "inicio": inicio,
        "proximo_inicio": proximo,
        "conteudo": trecho,
    }


def ler_documento(url: str, *, max_paginas_pdf: int = 10, inicio: int = 0, max_caracteres: int = 30000,
                  doi: str | None = None, nivel_fonte: str | None = None) -> dict:
    """Lê a URL (HTML ou PDF) pelo Firecrawl, usando o cache quando possível. Uso interno das rotinas."""
    url = _texto(url, "url")
    if not url.lower().startswith(("http://", "https://")):
        raise ValueError("Informe uma URL completa, começando com http:// ou https://.")
    if dominio_bloqueado(url):
        raise ValueError(f"Fonte bloqueada pelo projeto: {obter_dominio(url)}. Procure outra fonte.")
    max_paginas_pdf = _limitar(max_paginas_pdf, 1, MAX_PAGINAS_PDF)
    max_caracteres = _limitar(max_caracteres, 2000, MAX_CARACTERES)
    inicio = max(0, int(inicio))
    url_normalizada = normalizar_url(url)
    parametros = {"max_paginas_pdf": max_paginas_pdf, "inicio": inicio, "max_caracteres": max_caracteres}

    fonte = buscar_fonte(url_normalizada)
    cache_suficiente = fonte and (not fonte.get("fl_pdf_truncado") or (fonte.get("nr_paginas_lidas") or 0) >= max_paginas_pdf)
    if cache_suficiente:
        registrar_consulta(SERVICO, "leitura", url, id_fonte=fonte.get("id_fonte"), fl_cache=True)
        dados = _dados_leitura(fonte, url=url, inicio=inicio, max_caracteres=max_caracteres,
                               veio_do_cache=True, nivel_fonte=nivel_fonte, creditos=0)
        return _retorno(url, parametros, dados)

    _verificar_limite(max_paginas_pdf)
    corpo = {
        "url": url,
        "formats": ["markdown"],
        "onlyMainContent": True,
        "parsers": [{"type": "pdf", "maxPages": max_paginas_pdf}],
        "timeout": 90000,
    }
    try:
        resposta = _requisitar("/scrape", corpo)
    except ErroFirecrawl as erro:
        registrar_consulta(SERVICO, "leitura", url, ds_erro=str(erro))
        raise

    dados_api = resposta.get("data") or {}
    metadados = dados_api.get("metadata") or {}
    conteudo = dados_api.get("markdown") or ""
    url_final = metadados.get("url") or url
    if dominio_bloqueado(url_final):
        mensagem = f"A URL redirecionou para uma fonte bloqueada: {obter_dominio(url_final)}. Procure outra fonte."
        registrar_consulta(SERVICO, "leitura", url, vl_creditos=int(metadados.get("creditsUsed") or 1), ds_erro=mensagem)
        raise ValueError(mensagem)
    eh_pdf = "pdf" in str(metadados.get("contentType") or "").lower() or metadados.get("numPages") is not None
    paginas_lidas = metadados.get("numPages") if eh_pdf else None
    paginas_total = metadados.get("totalPages", paginas_lidas) if eh_pdf else None
    truncado = bool(eh_pdf and paginas_total and paginas_lidas and paginas_total > paginas_lidas)
    creditos = metadados.get("creditsUsed")
    if creditos is None:
        creditos = max(1, paginas_lidas or 1)
    titulo = metadados.get("title") or metadados.get("ogTitle")
    if isinstance(titulo, list):
        titulo = titulo[0] if titulo else None

    fonte = {
        "ds_url": url,
        "ds_url_normalizada": url_normalizada,
        "nm_dominio": obter_dominio(url_final),
        "tp_conteudo": "pdf" if eh_pdf else "html",
        "tp_nivel_fonte": nivel_fonte or classificar_fonte(url_final),
        "ds_titulo": titulo,
        "ds_conteudo": conteudo,
        "nr_paginas_pdf": paginas_total,
        "nr_paginas_lidas": paginas_lidas,
        "fl_pdf_truncado": truncado,
        "cd_http_status": metadados.get("statusCode"),
        "ds_hash_conteudo": hashlib.sha256(conteudo.encode("utf-8")).hexdigest(),
        "ds_doi": doi,
    }
    id_fonte = salvar_fonte(**fonte)
    registrar_consulta(SERVICO, "leitura", url, id_fonte=id_fonte, vl_creditos=int(creditos))
    fonte.update(id_fonte=id_fonte, dt_consulta=datetime.now(timezone.utc))
    dados = _dados_leitura(fonte, url=url, inicio=inicio, max_caracteres=max_caracteres,
                           veio_do_cache=False, nivel_fonte=nivel_fonte, creditos=int(creditos))
    return _retorno(url, parametros, dados, url_final=url_final)


def ler_pagina(url: str, max_paginas_pdf: int = 10, inicio: int = 0) -> dict:
    """Abre e lê uma página ou PDF e devolve o conteúdo em markdown (tabelas incluídas).

    Use para conferir composição química, propriedades e tratamentos térmicos na fonte
    original. Páginas já lidas por qualquer agente vêm do cache, sem custo. Custa 1 crédito
    por página HTML ou 1 crédito por página de PDF lida. Fontes bloqueadas são recusadas.
    O conteúdo vem em trechos de até 30.000 caracteres: se "proximo_inicio" não for nulo,
    chame de novo com inicio=proximo_inicio para ler a continuação (sem custo).

    Args:
        url: endereço completo da página ou do PDF.
        max_paginas_pdf: máximo de páginas do PDF a ler (1 a 50). Se "pdf_truncado" vier
            verdadeiro e faltar informação, leia de novo com um valor maior.
        inicio: posição (em caracteres) a partir da qual o conteúdo é devolvido.
    """
    return ler_documento(url, max_paginas_pdf=max_paginas_pdf, inicio=inicio)


def _main() -> None:
    analisador = argparse.ArgumentParser(description="Consultas Firecrawl do Daedalus Lab.")
    sub = analisador.add_subparsers(dest="comando", required=True)
    p = sub.add_parser("buscar")
    p.add_argument("consulta")
    p.add_argument("--tipo", default="web", choices=["web", "pdf"])
    p.add_argument("--dominios", nargs="*")
    p.add_argument("--limite", type=int, default=10)
    p = sub.add_parser("fichas")
    p.add_argument("material")
    p.add_argument("--fabricantes", nargs="*")
    p.add_argument("--limite", type=int, default=10)
    p = sub.add_parser("ler")
    p.add_argument("url")
    p.add_argument("--max-paginas-pdf", type=int, default=10)
    p.add_argument("--inicio", type=int, default=0)
    argumentos = analisador.parse_args()

    if argumentos.comando == "buscar":
        resultado = buscar_web(argumentos.consulta, argumentos.tipo, argumentos.dominios, argumentos.limite)
    elif argumentos.comando == "fichas":
        resultado = buscar_fichas_tecnicas(argumentos.material, argumentos.fabricantes, argumentos.limite)
    else:
        resultado = ler_pagina(argumentos.url, argumentos.max_paginas_pdf, argumentos.inicio)
    print(json.dumps(resultado, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    _main()
