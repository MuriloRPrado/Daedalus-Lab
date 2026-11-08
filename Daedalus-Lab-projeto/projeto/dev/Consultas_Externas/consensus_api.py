"""Consensus para Daedalus — Python 3.10+, requests.

Instalação: python -m pip install requests
Chave: variável de ambiente CONSENSUS_API_KEY (não carrega .env).

Exemplos (PowerShell, na pasta deste arquivo):
  python consensus_api_completo.py buscar "7075 T6 corrosion"
  python consensus_api_completo.py perguntar "Como T6 afeta a corrosão de 7075?"
  python consensus_api_completo.py aprofundar "Compare T6 e T73 em 7075. Cite evidências."
  python consensus_api_completo.py consultar THREAD_ID --interacao INTERACTION_ID

Importar este módulo NÃO realiza consultas. Não há gravação em banco.
JSON local somente quando solicitado por --salvar ou salvar_resultados().
As pesquisas Threads ficam no serviço Consensus. Pro/deep consomem a franquia
conforme o trabalho do agente: uma pesquisa NÃO equivale a uma chamada simples.
Não altera cobrança/excedentes. Não baixa PDFs nem garante leitura integral.
Fontes de busca são ENCONTRADAS; citations de Threads são referências CITADAS,
não um inventário completo de todo documento internamente consultado.

Contrato consultado em 17/10/2026: https://docs.consensus.app/openapi.json
https://docs.consensus.app/api-plans-and-access
https://docs.consensus.app/api-full-text
"""
import argparse
import json
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

BASE_URL = "https://api.consensus.app/v1"
_lock = threading.Lock()
_ultima_chamada = 0.0


class ErroConsensus(RuntimeError):
    """Erro da API; não há repetição automática de requisições."""


def _texto(valor: str, nome: str) -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"{nome} deve ser um texto não vazio.")
    return valor.strip()


def _id(valor: str) -> str:
    valor = _texto(valor, "ID")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", valor):
        raise ValueError("ID inválido: use o identificador retornado pela API.")
    return valor


def _requisitar(metodo: str, caminho: str, *, parametros=None, corpo=None) -> dict:
    chave = os.getenv("CONSENSUS_API_KEY", "").strip()
    if not chave:
        raise ValueError("Defina CONSENSUS_API_KEY no ambiente deste Python.")
    global _ultima_chamada
    with _lock:
        pausa = 1.05 - (time.monotonic() - _ultima_chamada)
        if pausa > 0:
            time.sleep(pausa)
        _ultima_chamada = time.monotonic()
        try:
            resposta = requests.request(
                metodo, BASE_URL + caminho,
                headers={"x-api-key": chave, "Accept": "application/json"},
                params=parametros, json=corpo, timeout=(10, 60),
                allow_redirects=False,
            )
        except requests.RequestException:
            raise ErroConsensus(
                "Falha de conexão/timeout. Não houve repetição automática. "
                "Se era uma criação de pesquisa, ela pode ter sido iniciada: "
                "confira o painel ou listar_pesquisas() antes de reenviar."
            ) from None
    mensagens = {
        401: "Chave inválida ou revogada.",
        402: "Pendência de cobrança na conta.",
        403: "Recurso não autorizado para a conta/plano.",
        404: "Pesquisa ou recurso não encontrado.",
        409: "A pesquisa anterior ainda está em andamento.",
        422: "Parâmetros rejeitados pela API; confira os valores enviados.",
        429: "Franquia ou limite de frequência atingido; confira o painel e aguarde.",
    }
    if not 200 <= resposta.status_code < 300:
        mensagem = mensagens.get(resposta.status_code, "Falha no serviço Consensus.")
        if metodo == "POST" and resposta.status_code >= 500:
            mensagem += " A operação pode ter ocorrido; confira o histórico antes de repetir."
        raise ErroConsensus(f"HTTP {resposta.status_code}: {mensagem}")
    try:
        dados = resposta.json()
    except ValueError:
        raise ErroConsensus("Resposta não é JSON válido. Em POST, confira o histórico antes de repetir.") from None
    if not isinstance(dados, dict):
        raise ErroConsensus("Formato de resposta inesperado.")
    return dados


def _pacote(tipo: str, consulta: str | None, resposta: dict, fontes: list, **extras) -> dict:
    return {
        "tipo": tipo, "consulta": consulta,
        "consultado_em": datetime.now(timezone.utc).isoformat(),
        "fontes": fontes, "resposta": resposta, **extras,
    }


def buscar_artigos(consulta: str, quantidade: int = 10, *,
                   incluir_trechos: bool = True, pagina: int = 0,
                   ano_min: int | None = None, ano_max: int | None = None,
                   somente_abertos: bool = False) -> dict[str, Any]:
    """Uma página por chamada; trechos ligados à consulta habilitados para Pro.

    Mantém resposta['results'] para compatibilidade com seu código anterior.
    'fontes' contém os registros completos encontrados, sem inventar metadados.
    Quantidade até 300 (Pro); o servidor pode aplicar limite menor conforme conta.
    """
    consulta = _texto(consulta, "consulta")
    if type(quantidade) is not int or not 1 <= quantidade <= 300:
        raise ValueError("quantidade deve estar entre 1 e 300.")
    if type(pagina) is not int or not 0 <= pagina <= 49 or (pagina + 1) * quantidade > 1000:
        raise ValueError("Página inválida ou ultrapassa a janela de 1.000 resultados.")
    if type(incluir_trechos) is not bool or type(somente_abertos) is not bool:
        raise ValueError("Os parâmetros booleanos devem ser True ou False.")
    for ano in (ano_min, ano_max):
        if ano is not None and (type(ano) is not int or ano < 1):
            raise ValueError("Os anos devem ser inteiros positivos.")
    if ano_min is not None and ano_max is not None and ano_min > ano_max:
        raise ValueError("ano_min não pode ser maior que ano_max.")
    params = {"query": consulta, "page_size": quantidade, "page": pagina,
              "include_full_text_chunks": str(incluir_trechos).lower()}
    if somente_abertos:
        params["open_access"] = "true"
    if ano_min is not None:
        params["year_min"] = ano_min
    if ano_max is not None:
        params["year_max"] = ano_max
    dados = _requisitar("GET", "/search", parametros=params)
    artigos = dados.get("results")
    if not isinstance(artigos, list) or not all(isinstance(a, dict) for a in artigos):
        raise ErroConsensus("Resposta de busca sem lista válida 'results'.")
    return _pacote("busca", consulta, dados, artigos, parametros=params,
                   significado_fontes="Artigos encontrados; não implica leitura integral.")


def iniciar_pesquisa(pergunta: str, *, modo: str = "pro",
                     ids_artigos: list[str] | None = None) -> dict:
    """Inicia pesquisa no agente Consensus e retorna IDs sem esperar.

    ids_artigos: IDs internos paper_id do Consensus (até 50), NÃO DOIs.
    Para um DOI, inclua-o na pergunta. A disponibilidade do conteúdo varia.
    """
    pergunta = _texto(pergunta, "pergunta")
    if len(pergunta) > 10000:
        raise ValueError("pergunta excede 10.000 caracteres.")
    if modo not in ("pro", "deep"):
        raise ValueError("modo deve ser pro ou deep.")
    corpo = {"input_message": pergunta, "mode": modo}
    if ids_artigos is not None:
        if (not isinstance(ids_artigos, list) or not 1 <= len(ids_artigos) <= 50
                or not all(isinstance(i, str) and i.strip() for i in ids_artigos)):
            raise ValueError("Forneça de 1 a 50 IDs internos de artigos.")
        corpo["attachments"] = {"paper_ids": ids_artigos}
    dados = _requisitar("POST", "/threads", corpo=corpo)
    if not dados.get("thread_id") or not dados.get("interaction_id"):
        raise ErroConsensus("Criação sem IDs esperados. Confira o histórico antes de repetir.")
    return dados


def consultar_pesquisa(thread_id: str, *, interaction_id: str | None = None,
                       incluir_rastro: bool = True) -> dict:
    """Recupera um turno exato (ou o último); mantém citações e marcadores originais."""
    params = {"include_trace": str(incluir_rastro).lower()}
    if interaction_id is not None:
        params["interaction_id"] = _id(interaction_id)
    dados = _requisitar("GET", f"/threads/{_id(thread_id)}", parametros=params)
    interacoes = dados.get("interactions")
    if not isinstance(interacoes, list) or not all(isinstance(i, dict) for i in interacoes):
        raise ErroConsensus("Pesquisa retornou interações em formato inesperado.")
    if interaction_id:
        alvo = next((i for i in interacoes if i.get("interaction_id") == interaction_id), None)
    else:
        alvo = interacoes[-1] if interacoes else None
    if alvo is None:
        raise ErroConsensus("Interação solicitada não apareceu no retorno; consulte novamente pelos IDs.")
    status = alvo.get("status")
    if status not in ("running", "idle", "failed"):
        raise ErroConsensus("Status de interação desconhecido.")
    fontes = alvo.get("citations") or []
    if not isinstance(fontes, list) or not all(isinstance(f, dict) for f in fontes):
        raise ErroConsensus("Citações retornadas em formato inesperado.")
    return _pacote(
        "pesquisa", alvo.get("input_message"), dados, fontes,
        thread_id=dados.get("thread_id", thread_id), interaction_id=alvo.get("interaction_id"),
        status=status, modo=alvo.get("mode"), url=dados.get("url"),
        resposta_texto=alvo.get("response"), rastro=alvo.get("agent_trace"),
        estatisticas=alvo.get("stats"),
        significado_fontes="Referências citadas na resposta; não é lista completa de consultas internas.",
    )


def aguardar_pesquisa(thread_id: str, interaction_id: str, *,
                      tempo_limite: float = 660, intervalo: float = 30,
                      progresso=None) -> dict:
    """Acompanha uma pesquisa existente. Timeout local NÃO cancela o trabalho remoto.

    Em timeout retorna status='running', espera_esgotada=True e IDs para retomar.
    Falha remota retorna status='failed', preservando resposta e fontes disponíveis.
    """
    if tempo_limite <= 0 or intervalo < 30:
        raise ValueError("tempo_limite deve ser positivo e intervalo >= 30 segundos.")
    fim = time.monotonic() + tempo_limite
    while True:
        try:
            resultado = consultar_pesquisa(thread_id, interaction_id=interaction_id)
        except ErroConsensus as erro:
            raise ErroConsensus(
                f"{erro} Retome com thread_id={thread_id}, interaction_id={interaction_id}; "
                "não crie uma nova pesquisa para continuar esta."
            ) from None
        if progresso:
            progresso(f"Status: {resultado['status']} | thread_id={thread_id} | interaction_id={interaction_id}")
        if resultado["status"] != "running":
            return resultado
        restante = fim - time.monotonic()
        if restante <= 0:
            resultado["espera_esgotada"] = True
            return resultado
        if restante < intervalo:
            resultado["espera_esgotada"] = True
            return resultado
        time.sleep(intervalo)


def _pesquisar(pergunta: str, modo: str, *, ids_artigos=None,
               tempo_limite: float | None = None, progresso=None) -> dict:
    if tempo_limite is not None and tempo_limite <= 0:
        raise ValueError("tempo_limite deve ser positivo.")
    inicio = iniciar_pesquisa(pergunta, modo=modo, ids_artigos=ids_artigos)
    if progresso:
        progresso(f"Pesquisa iniciada: {inicio['thread_id']} | interação: {inicio['interaction_id']}")
    try:
        return aguardar_pesquisa(
            inicio["thread_id"], inicio["interaction_id"],
            tempo_limite=tempo_limite or (240 if modo == "pro" else 660),
            intervalo=max(30, inicio.get("poll_after_seconds", 30)), progresso=progresso,
        )
    except KeyboardInterrupt:
        raise ErroConsensus(
            f"Espera interrompida; a pesquisa pode continuar no servidor. "
            f"thread_id={inicio['thread_id']}, interaction_id={inicio['interaction_id']}"
        ) from None


def perguntar_estudos(pergunta: str, *, ids_artigos=None, tempo_limite=None, progresso=None) -> dict:
    """Pergunta respondida pelo agente Consensus em modo pro, com citações."""
    return _pesquisar(pergunta, "pro", ids_artigos=ids_artigos,
                      tempo_limite=tempo_limite, progresso=progresso)


def pesquisa_aprofundada(pergunta: str, *, ids_artigos=None, tempo_limite=None, progresso=None) -> dict:
    """Pesquisa do agente Consensus em modo deep; pode consumir mais franquia."""
    return _pesquisar(pergunta, "deep", ids_artigos=ids_artigos,
                      tempo_limite=tempo_limite, progresso=progresso)


def listar_pesquisas(quantidade: int = 10) -> dict:
    """Ajuda a localizar uma pesquisa após perder a resposta de criação."""
    if type(quantidade) is not int or not 1 <= quantidade <= 100:
        raise ValueError("quantidade deve estar entre 1 e 100.")
    return _requisitar("GET", "/threads", parametros={"limit": quantidade})


def exibir_resultados(resultado: dict) -> None:
    if resultado["tipo"] == "pesquisa":
        print(f"Status: {resultado['status']}\nThread: {resultado['thread_id']}"
              f"\nInteração: {resultado['interaction_id']}\nURL: {resultado.get('url')}")
        print(resultado.get("resposta_texto") or "Sem resposta textual disponível neste momento.")
        if resultado.get("espera_esgotada"):
            print("Espera local encerrada. Use consultar com os IDs acima para recuperar depois.")
        if resultado.get("rastro"):
            print("\nEtapas informadas pelo Consensus:\n" + resultado["rastro"])
    print(f"\nFontes: {len(resultado['fontes'])}")
    print(resultado["significado_fontes"])
    for indice, fonte in enumerate(resultado["fontes"], 1):
        print(f"\n[{fonte.get('n', indice)}] {fonte.get('title') or 'Título não informado'}")
        for campo in ("paper_id", "authors", "publish_year", "year", "journal_name", "journal",
                      "doi", "url", "institutional_access_url", "abstract", "takeaway"):
            if fonte.get(campo) is not None:
                print(f"{campo}: {fonte[campo]}")
        for trecho in fonte.get("full_text_chunks") or []:
            print(f"Trecho: {trecho}")
        for citacao in fonte.get("snippets") or []:
            print(f"[{citacao.get('marker')}] {citacao.get('section')}: {citacao.get('quote')}")


def salvar_resultados(resultado: dict, caminho: str) -> Path:
    """JSON opcional em arquivo novo; não sobrescreve e não grava no banco."""
    destino = Path(caminho)
    with destino.open("x", encoding="utf-8") as arquivo:
        json.dump(resultado, arquivo, ensure_ascii=False, indent=2)
    return destino


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("acao", choices=["buscar", "perguntar", "aprofundar", "consultar", "listar"])
    parser.add_argument("texto", nargs="?", help="Consulta/pergunta, ou thread_id para consultar.")
    parser.add_argument("--quantidade", type=int, default=10)
    parser.add_argument("--sem-trechos", action="store_true")
    parser.add_argument("--pagina", type=int, default=0)
    parser.add_argument("--ano-min", type=int)
    parser.add_argument("--ano-max", type=int)
    parser.add_argument("--abertos", action="store_true")
    parser.add_argument("--artigo-id", action="append", help="ID interno do Consensus; repetível para perguntas.")
    parser.add_argument("--interacao", help="ID do turno para recuperar sua resposta exata.")
    parser.add_argument("--tempo-limite", type=float, default=None)
    parser.add_argument("--salvar", metavar="ARQUIVO.json")
    args = parser.parse_args()
    if args.acao != "listar" and not args.texto:
        parser.error("Informe a consulta/pergunta ou o ID depois da ação.")
    if args.salvar and Path(args.salvar).exists():
        parser.error("Arquivo de saída já existe. Escolha outro nome.")
    try:
        if args.acao == "buscar":
            resultado = buscar_artigos(args.texto, args.quantidade,
                incluir_trechos=not args.sem_trechos, pagina=args.pagina,
                ano_min=args.ano_min, ano_max=args.ano_max, somente_abertos=args.abertos)
        elif args.acao in ("perguntar", "aprofundar"):
            funcao = perguntar_estudos if args.acao == "perguntar" else pesquisa_aprofundada
            resultado = funcao(args.texto, ids_artigos=args.artigo_id,
                              tempo_limite=args.tempo_limite, progresso=print)
        elif args.acao == "consultar":
            resultado = consultar_pesquisa(args.texto, interaction_id=args.interacao)
        else:
            resultado = listar_pesquisas(args.quantidade)
        if args.acao == "listar":
            print(json.dumps(resultado, ensure_ascii=False, indent=2))
        else:
            exibir_resultados(resultado)
        if args.salvar:
            salvar_resultados(resultado, args.salvar)
        return 1 if resultado.get("status") == "failed" else 0
    except (ErroConsensus, ValueError, OSError) as erro:
        print(f"Erro: {erro}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())