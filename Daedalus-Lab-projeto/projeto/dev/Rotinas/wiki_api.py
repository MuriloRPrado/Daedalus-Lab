"""Wikipedia e Wikidata pelas APIs oficiais da Wikimedia (gratuitas, sem chave e sem gastar créditos do Firecrawl).

Wikipedia: texto de referência sobre materiais (licença CC BY-SA 4.0).
Wikidata: dados estruturados de ligas e materiais, como composição (faixas em %), densidade,
ponto de fusão, designações (UNS, Werkstoff) e links para fichas técnicas (licença CC0).
São fontes de referência aberta e complementar: confirme os valores nas fichas dos fabricantes.

Instalação: python -m pip install requests
Exemplos (na pasta dev):
  python -m Rotinas.wiki_api wikipedia "aço inoxidável duplex"
  python -m Rotinas.wiki_api ler "Aço inoxidável"
  python -m Rotinas.wiki_api wikidata "Inconel 625"
  python -m Rotinas.wiki_api item Q25045309
"""
######################### BIBLIOTECAS ###################################
import argparse
import html
import json
import re
from datetime import datetime, timezone

import requests

import Rotinas.configuracao  # noqa: F401
from Rotinas.cache_fontes import registrar_consulta
from Rotinas.configuracao import user_agent
from Rotinas.fontes_firecrawl import NIVEL_REFERENCIA_ABERTA
#########################################################################

URL_WIKIDATA = "https://www.wikidata.org/w/api.php"
_IDIOMAS = {"pt", "en", "es", "de", "fr"}
_ID_ITEM = re.compile(r"Q\d+")
_TIPOS_IGNORADOS = {"external-id", "commonsMedia", "wikibase-lexeme", "wikibase-form", "wikibase-sense"}


def _texto(valor: str, nome: str) -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"{nome} deve ser um texto não vazio.")
    return valor.strip()


def _idioma(idioma: str) -> str:
    if idioma not in _IDIOMAS:
        raise ValueError(f"Idioma não suportado: {idioma}. Opções: {', '.join(sorted(_IDIOMAS))}.")
    return idioma


def _api(servico: str, url: str, parametros: dict, consulta: str, operacao: str = "busca") -> dict:
    parametros = {**parametros, "format": "json", "formatversion": 2}
    try:
        resposta = requests.get(url, params=parametros, headers={"User-Agent": user_agent()}, timeout=(10, 60))
        resposta.raise_for_status()
        corpo = resposta.json()
        if "error" in corpo:
            raise ValueError(f"{corpo['error'].get('code')}: {corpo['error'].get('info')}")
    except (requests.RequestException, ValueError) as erro:
        registrar_consulta(servico, operacao, consulta, ds_erro=str(erro)[:500])
        raise RuntimeError(f"Não foi possível consultar {servico}: {erro}"[:400]) from erro
    registrar_consulta(servico, operacao, consulta)
    return corpo


def _retorno(fonte: str, consulta: str, dados, **parametros) -> dict:
    return {
        "fonte": fonte,
        "consulta": consulta,
        "parametros": parametros,
        "consultado_em_utc": datetime.now(timezone.utc).isoformat(),
        "nivel_fonte": NIVEL_REFERENCIA_ABERTA,
        "dados": dados,
    }


######################### WIKIPEDIA #####################################

def buscar_wikipedia(consulta: str, idioma: str = "pt", limite: int = 5) -> dict:
    """Busca artigos da Wikipedia sobre um material, liga ou conceito (gratuito, sem créditos).

    Args:
        consulta: Termo de busca. Ex.: "aço inoxidável duplex".
        idioma: Idioma da Wikipedia: pt, en, es, de ou fr. Padrão: pt.
        limite: Número de artigos, de 1 a 20.
    """
    consulta, idioma = _texto(consulta, "consulta"), _idioma(idioma)
    if not 1 <= limite <= 20:
        raise ValueError("limite deve estar entre 1 e 20.")
    url = f"https://{idioma}.wikipedia.org/w/api.php"
    corpo = _api("wikipedia", url, {"action": "query", "list": "search", "srsearch": consulta, "srlimit": limite}, consulta)
    artigos = [
        {
            "titulo": r.get("title"),
            "trecho": html.unescape(re.sub(r"<[^>]+>", "", r.get("snippet") or "")),
            "url": f"https://{idioma}.wikipedia.org/wiki/{(r.get('title') or '').replace(' ', '_')}",
            "atualizado_em": r.get("timestamp"),
            "tipo_acesso": "resultado_de_busca",
        }
        for r in (corpo.get("query") or {}).get("search") or []
    ]
    return _retorno("Wikipedia", consulta, artigos, idioma=idioma, limite=limite)


def ler_wikipedia(titulo: str, idioma: str = "pt", inicio: int = 0, max_caracteres: int = 20000) -> dict:
    """Lê o texto de um artigo da Wikipedia, com link permanente da revisão lida (gratuito, sem créditos).

    Args:
        titulo: Título do artigo, como devolvido por buscar_wikipedia. Ex.: "Aço inoxidável".
        idioma: Idioma da Wikipedia: pt, en, es, de ou fr. Padrão: pt.
        inicio: Posição do texto a partir da qual ler, para continuar artigos longos. Padrão: 0.
        max_caracteres: Tamanho máximo do trecho devolvido, de 1000 a 50000.
    """
    titulo, idioma = _texto(titulo, "titulo"), _idioma(idioma)
    if inicio < 0 or not 1000 <= max_caracteres <= 50000:
        raise ValueError("inicio deve ser >= 0 e max_caracteres entre 1000 e 50000.")
    url = f"https://{idioma}.wikipedia.org/w/api.php"
    corpo = _api("wikipedia", url, {
        "action": "query", "titles": titulo, "redirects": 1,
        "prop": "extracts|info|pageprops|revisions", "explaintext": 1, "inprop": "url",
        "ppprop": "wikibase_item", "rvprop": "ids|timestamp",
    }, titulo, "leitura")
    paginas = (corpo.get("query") or {}).get("pages") or []
    pagina = paginas[0] if paginas else {}
    if not pagina or pagina.get("missing") or pagina.get("invalid"):
        return _retorno("Wikipedia", titulo, None, idioma=idioma, erro=f"Artigo não encontrado: {titulo}")
    texto = pagina.get("extract") or ""
    revisao = (pagina.get("revisions") or [{}])[0]
    fim = inicio + max_caracteres
    dados = {
        "titulo": pagina.get("title"),
        "url": pagina.get("fullurl"),
        "url_revisao": f"https://{idioma}.wikipedia.org/w/index.php?oldid={revisao.get('revid')}" if revisao.get("revid") else None,
        "revisao_em": revisao.get("timestamp"),
        "id_wikidata": (pagina.get("pageprops") or {}).get("wikibase_item"),
        "licenca": "CC BY-SA 4.0",
        "total_caracteres": len(texto),
        "texto": texto[inicio:fim],
        "proximo_inicio": fim if fim < len(texto) else None,
        "tipo_acesso": "documento_lido",
    }
    return _retorno("Wikipedia", titulo, dados, idioma=idioma, inicio=inicio, max_caracteres=max_caracteres)


######################### WIKIDATA ######################################

def buscar_material_wikidata(nome: str, idioma: str = "pt", limite: int = 5) -> dict:
    """Busca itens do Wikidata pelo nome de um material ou liga (ex.: "Inconel 625", "316L").

    Devolve os IDs (Qxxx) para usar em consultar_material_wikidata.

    Args:
        nome: Nome do material ou liga.
        idioma: Idioma dos rótulos e da busca (também busca em inglês): pt, en, es, de ou fr.
        limite: Número de itens, de 1 a 20.
    """
    nome, idioma = _texto(nome, "nome"), _idioma(idioma)
    if not 1 <= limite <= 20:
        raise ValueError("limite deve estar entre 1 e 20.")
    itens: dict[str, dict] = {}
    for lingua in dict.fromkeys([idioma, "en"]):
        corpo = _api("wikidata", URL_WIKIDATA, {
            "action": "wbsearchentities", "search": nome, "language": lingua, "uselang": idioma,
            "type": "item", "limit": limite,
        }, nome)
        for r in corpo.get("search") or []:
            itens.setdefault(r["id"], {
                "id": r["id"],
                "rotulo": r.get("label"),
                "descricao": r.get("description"),
                "url": f"https://www.wikidata.org/wiki/{r['id']}",
                "tipo_acesso": "resultado_de_busca",
            })
    return _retorno("Wikidata", nome, list(itens.values())[:limite], idioma=idioma, limite=limite)


def _entidades(ids: set[str], props: str, idioma: str) -> dict:
    entidades, ids = {}, sorted(ids)
    for i in range(0, len(ids), 50):
        corpo = _api("wikidata", URL_WIKIDATA, {
            "action": "wbgetentities", "ids": "|".join(ids[i:i + 50]), "props": props,
            "languages": f"{idioma}|en", "languagefallback": 1,
        }, "|".join(ids[i:i + 50]), "leitura")
        entidades.update(corpo.get("entities") or {})
    return entidades


def _ids_referenciados(snak: dict) -> set[str]:
    ids = {snak.get("property")} if snak.get("property") else set()
    valor = (snak.get("datavalue") or {}).get("value")
    if isinstance(valor, dict):
        if valor.get("id"):
            ids.add(valor["id"])
        unidade = str(valor.get("unit") or "").rsplit("/", 1)[-1]
        if _ID_ITEM.fullmatch(unidade):
            ids.add(unidade)
    return ids


def _valor(snak: dict, rotulos: dict) -> object:
    if snak.get("snaktype") != "value":
        return "sem valor" if snak.get("snaktype") == "novalue" else "desconhecido"
    dado = snak.get("datavalue") or {}
    valor, tipo = dado.get("value"), dado.get("type")
    if tipo == "wikibase-entityid":
        return rotulos.get(valor.get("id"), valor.get("id"))
    if tipo == "quantity":
        unidade = str(valor.get("unit") or "1").rsplit("/", 1)[-1]
        quantidade = {"valor": float(valor["amount"]), "unidade": None if unidade == "1" else rotulos.get(unidade, unidade)}
        if "lowerBound" in valor:
            quantidade.update(minimo=float(valor["lowerBound"]), maximo=float(valor["upperBound"]))
        return quantidade
    if tipo == "monolingualtext":
        return valor.get("text")
    if tipo == "time":
        return valor.get("time")
    return valor


def consultar_material_wikidata(id_item: str, idioma: str = "pt") -> dict:
    """Consulta os dados estruturados de um material no Wikidata: composição, propriedades,
    designações e links para fichas técnicas, com as referências de cada valor.

    Na composição, os qualificadores "lower limit"/"upper limit" são as faixas em % (massa).
    Fonte de referência aberta: confirme os valores nas fichas dos fabricantes.

    Args:
        id_item: ID do item no Wikidata, como devolvido por buscar_material_wikidata. Ex.: "Q25045309".
        idioma: Idioma dos rótulos: pt, en, es, de ou fr. Padrão: pt.
    """
    id_item, idioma = _texto(id_item, "id_item").upper(), _idioma(idioma)
    if not _ID_ITEM.fullmatch(id_item):
        raise ValueError("id_item inválido. Formato esperado: Q25045309.")
    item = _entidades({id_item}, "labels|descriptions|claims|sitelinks/urls", idioma).get(id_item) or {}
    if not item or "missing" in item:
        return _retorno("Wikidata", id_item, None, idioma=idioma, erro=f"Item não encontrado: {id_item}")

    declaracoes = [
        (p, d) for p, lista in (item.get("claims") or {}).items() for d in lista
        if d["mainsnak"].get("datatype") not in _TIPOS_IGNORADOS and d.get("rank") != "deprecated"
    ]
    snaks = [s for _, d in declaracoes for s in [d["mainsnak"], *[q for qs in (d.get("qualifiers") or {}).values() for q in qs],
             *[r for ref in d.get("references") or [] for rs in ref["snaks"].values() for r in rs]]]
    ids = set().union(*(_ids_referenciados(s) for s in snaks)) if snaks else set()
    rotulos = {
        k: ((e.get("labels") or {}).get(idioma) or (e.get("labels") or {}).get("en") or {}).get("value", k)
        for k, e in _entidades(ids, "labels", idioma).items()
    }

    propriedades: dict[str, list] = {}
    for propriedade, declaracao in declaracoes:
        registro = {"valor": _valor(declaracao["mainsnak"], rotulos)}
        qualificadores = {
            rotulos.get(p, p): [_valor(q, rotulos) for q in qs] for p, qs in (declaracao.get("qualifiers") or {}).items()
        }
        if qualificadores:
            registro["qualificadores"] = qualificadores
        referencias = [
            {rotulos.get(p, p): [_valor(r, rotulos) for r in rs] for p, rs in ref["snaks"].items()}
            for ref in declaracao.get("references") or []
        ]
        if referencias:
            registro["referencias"] = referencias
        propriedades.setdefault(f"{rotulos.get(propriedade, propriedade)} ({propriedade})", []).append(registro)

    rotulo = lambda campo: ((item.get(campo) or {}).get(idioma) or (item.get(campo) or {}).get("en") or {}).get("value")
    dados = {
        "id": id_item,
        "rotulo": rotulo("labels"),
        "descricao": rotulo("descriptions"),
        "url": f"https://www.wikidata.org/wiki/{id_item}",
        "id_revisao": item.get("lastrevid"),
        "artigos_wikipedia": {s: v.get("url") for s, v in (item.get("sitelinks") or {}).items() if v.get("url")},
        "licenca": "CC0",
        "propriedades": propriedades,
        "tipo_acesso": "documento_lido",
    }
    return _retorno("Wikidata", id_item, dados, idioma=idioma)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("comando", choices=["wikipedia", "ler", "wikidata", "item"])
    parser.add_argument("termo")
    parser.add_argument("--idioma", default="pt")
    args = parser.parse_args()
    funcoes = {"wikipedia": buscar_wikipedia, "ler": ler_wikipedia, "wikidata": buscar_material_wikidata, "item": consultar_material_wikidata}
    print(json.dumps(funcoes[args.comando](args.termo, idioma=args.idioma), ensure_ascii=False, indent=2))
