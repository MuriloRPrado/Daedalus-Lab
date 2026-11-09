"""Relatório final da Calíope - Relatório.

As seções com dados gravados (projeto, requisitos, materiais, cobertura, composição,
propriedades, fases e referências) são montadas aqui, direto do banco, para que o relatório
corresponda exatamente ao que foi gravado. O agente escreve só as seções de análise
(resumo, comparação, lacunas e conclusão), devolvidas em RelatorioCaliope.
"""
######################### BIBLIOTECAS ###################################
from collections import defaultdict

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import (
    ComposicaoFonte, ComposicaoMaterial, EstrutCristalinaFontes, EstruturaCristalina, Fontes, MateriaisEstadosFonte,
    MateriaisFonte, Propriedade, ValorPropriedades, ValorPropriedadesFonte, engine,
)
from Rotinas.caracterizacao_estruturada import _celula, _tabela
from Rotinas.dados_prompt import dados_projeto, propriedades_cadastradas, requisitos_projeto, restricoes_projeto
from Rotinas.registro_materiais import listar_materiais_projeto
#########################################################################


class LacunaRelatorio(BaseModel):
    material: str = Field(description="Material e condição a que a lacuna se refere (ou \"Todos\").")
    dado_faltante: str = Field(description="Dado que não foi localizado ou ficou inconclusivo.")
    motivo: str = Field(description="Por que o dado não foi obtido, conforme os retornos das etapas.")
    impacto: str = Field(description="O que a lacuna impede de concluir (ex.: requisito obrigatório sem verificação).")
    como_obter: str = Field(description="Ação concreta para o usuário obter o dado (norma, fabricante, ensaio, base de dados).")


class RelatorioCaliope(BaseModel):
    resumo_executivo: str = Field(description="Seção \"Resumo executivo\", em Markdown, sem o título.")
    comparacao_consolidada: str = Field(description="Seção \"Comparação com requisitos e restrições\", em Markdown, sem o título.")
    lacunas: list[LacunaRelatorio] = Field(description="Uma entrada por lacuna relevante que restou.")
    conclusao: str = Field(description="Seção \"Conclusão\", em Markdown, sem o título.")
    proximos_passos: list[str] = Field(description="Ações específicas e priorizadas para resolver as lacunas.")


def secoes_banco(id_projeto: int) -> dict[str, str]:
    """Seções do relatório montadas a partir do banco, por chave."""
    projeto = dados_projeto(id_projeto)
    materiais = listar_materiais_projeto(id_projeto)["materiais"]
    estados = [(m, e) for m in materiais for e in m["estados"]]
    ids_materiais = [m["id_material"] for m in materiais]
    ids_estados = [e["id_mat_estado"] for _, e in estados]
    cadastradas = propriedades_cadastradas()

    with Session(engine) as session:
        composicao = session.execute(
            select(ComposicaoMaterial).where(ComposicaoMaterial.id_material.in_(ids_materiais))
            .order_by(ComposicaoMaterial.id_material, ComposicaoMaterial.id_composicao)
        ).scalars().all()
        valores = session.execute(
            select(ValorPropriedades, Propriedade).join(Propriedade, Propriedade.id_propriedade == ValorPropriedades.id_propriedade)
            .where(ValorPropriedades.id_mat_estado.in_(ids_estados))
            .order_by(ValorPropriedades.id_mat_estado, Propriedade.nm_categoria_prop, Propriedade.id_propriedade, ValorPropriedades.id_vl_prop)
        ).all()
        fases = session.execute(
            select(EstruturaCristalina).where(EstruturaCristalina.id_mat_estado.in_(ids_estados))
            .order_by(EstruturaCristalina.id_mat_estado, EstruturaCristalina.id_fase)
        ).scalars().all()
        fontes_comp = _fontes_por(session, ComposicaoFonte.id_composicao, ComposicaoFonte.id_fonte,
                                  ComposicaoFonte.id_material.in_(ids_materiais))
        fontes_vlp = _fontes_por(session, ValorPropriedadesFonte.id_vl_prop, ValorPropriedadesFonte.id_fonte,
                                 ValorPropriedadesFonte.id_mat_estado.in_(ids_estados))
        fontes_fase = _fontes_por(session, EstrutCristalinaFontes.id_fase, EstrutCristalinaFontes.id_fonte,
                                  EstrutCristalinaFontes.id_mat_estado.in_(ids_estados))
        fontes_mat = _fontes_por(session, MateriaisFonte.id_material, MateriaisFonte.id_fonte,
                                 MateriaisFonte.id_projeto == id_projeto)
        fontes_est = _fontes_por(session, MateriaisEstadosFonte.id_mat_estado, MateriaisEstadosFonte.id_fonte,
                                 MateriaisEstadosFonte.id_mat_estado.in_(ids_estados))
        ids_fontes = sorted({f for grupo in (fontes_comp, fontes_vlp, fontes_fase, fontes_mat, fontes_est)
                             for lista in grupo.values() for f in lista})
        fontes = session.execute(
            select(Fontes).where(Fontes.id_fonte.in_(ids_fontes)).order_by(Fontes.id_fonte)
        ).scalars().all()

    comp_por_material = defaultdict(list)
    for c in composicao:
        comp_por_material[c.id_material].append(c)
    valores_por_estado = defaultdict(list)
    for v, p in valores:
        valores_por_estado[v.id_mat_estado].append((v, p))
    fases_por_estado = defaultdict(list)
    for f in fases:
        fases_por_estado[f.id_mat_estado].append(f)

    return {
        "identificacao": _identificacao(projeto),
        "requisitos": _requisitos(requisitos_projeto(id_projeto), restricoes_projeto(id_projeto)),
        "materiais": _materiais(materiais, fontes_mat, fontes_est),
        "cobertura": _cobertura(estados, comp_por_material, valores_por_estado, fases_por_estado, len(cadastradas)),
        "composicao": _composicao(materiais, comp_por_material, fontes_comp),
        "propriedades": _propriedades(estados, valores_por_estado, fontes_vlp, cadastradas),
        "fases": _fases(estados, fases_por_estado, fontes_fase),
        "referencias": _referencias(fontes),
    }


def montar_relatorio(id_projeto: int, analise: RelatorioCaliope, secoes: dict[str, str] | None = None) -> str:
    """Relatório final em Markdown: seções do banco + seções de análise do agente."""
    s = secoes or secoes_banco(id_projeto)
    nome = dados_projeto(id_projeto).get("nm_projeto") or f"ID {id_projeto}"
    lacunas = _tabela(
        ("Material", "Dado faltante", "Motivo", "Impacto", "Como obter"),
        [(lac.material, lac.dado_faltante, lac.motivo, lac.impacto, lac.como_obter) for lac in analise.lacunas],
    ) if analise.lacunas else "Nenhuma lacuna relevante restou."
    passos = "\n".join(f"{n}. {p.strip()}" for n, p in enumerate(analise.proximos_passos, 1)) or "Nenhum."
    partes = [
        f"# Relatório de seleção de materiais — Projeto {nome}",
        "## 1. Identificação e escopo", s["identificacao"],
        "## 2. Resumo executivo", analise.resumo_executivo.strip(),
        "## 3. Requisitos e restrições", s["requisitos"],
        "## 4. Materiais selecionados", s["materiais"],
        "## 5. Cobertura da caracterização", s["cobertura"],
        "## 6. Composição química", s["composicao"],
        "## 7. Propriedades", s["propriedades"],
        "## 8. Estrutura cristalina e fases", s["fases"],
        "## 9. Comparação com requisitos e restrições", analise.comparacao_consolidada.strip(),
        "## 10. Lacunas e como obter os dados", lacunas,
        "## 11. Conclusão e próximos passos", analise.conclusao.strip(), "**Próximos passos:**", passos,
        "## 12. Referências", s["referencias"],
    ]
    return "\n\n".join(partes)


def _fontes_por(session, chave, id_fonte, filtro) -> dict[int, list[int]]:
    resultado = defaultdict(list)
    for k, f in session.execute(select(chave, id_fonte).where(filtro).order_by(chave, id_fonte)).all():
        if f not in resultado[k]:
            resultado[k].append(f)
    return resultado


def _ids(fontes: list[int]) -> str:
    return ", ".join(f"[{f}]" for f in fontes) or "—"


def _num(valor) -> str:
    if valor is None:
        return ""
    return f"{float(valor):g}"


def _faixa(minimo, maximo, pontual=None) -> str:
    if pontual is not None:
        return _num(pontual)
    if minimo is not None and maximo is not None:
        return f"{_num(minimo)} – {_num(maximo)}"
    if minimo is not None:
        return f"≥ {_num(minimo)}"
    if maximo is not None:
        return f"≤ {_num(maximo)}"
    return "—"


def _identificacao(projeto: dict) -> str:
    campos = (
        ("Projeto", "nm_projeto"), ("ID do projeto", "id_projeto"), ("Solicitante", "nm_usuario_solicitante"),
        ("Aplicação", "ds_aplicacao"), ("Ambiente", "ds_ambiente"), ("Material de referência", "nm_material_ref"),
        ("Rota de fabricação", "ds_rota_fabricacao"), ("Disponibilidade", "ds_disponibilidade"),
        ("Custo", "ds_custo"), ("Observações", "ds_observacao"),
    )
    return _tabela(("Campo", "Valor"), [(rotulo, projeto.get(chave) or "Não informado") for rotulo, chave in campos])


def _requisitos(requisitos: list[dict], restricoes: list[dict]) -> str:
    partes = ["### Requisitos de propriedades"]
    partes.append(_tabela(
        ("Propriedade", "Operador", "Alvo", "Mínimo", "Máximo", "Unidade", "Obrigatório", "Observação"),
        [(r["nm_propriedade"], r["ds_operador"], _num(r["vl_alvo"]), _num(r["vl_min"]), _num(r["vl_max"]),
          r["ds_unidade"], "Sim" if r["fl_obrigatorio"] else "Não", r["ds_observacao"]) for r in requisitos],
    ) if requisitos else "Não há requisitos de propriedades registrados.")
    partes.append("### Restrições químicas")
    partes.append(_tabela(
        ("Elemento", "Tipo de restrição", "Limite", "Observação"),
        [(r["nm_sigla_elemento"], r["tp_restricao"], r["ds_limite"], r["ds_observacao"]) for r in restricoes],
    ) if restricoes else "Não há restrições químicas registradas.")
    return "\n\n".join(partes)


def _materiais(materiais: list[dict], fontes_mat: dict, fontes_est: dict) -> str:
    if not materiais:
        return "Nenhum material foi registrado por Têmis para este projeto."
    linhas = []
    for m in materiais:
        for e in m["estados"] or [{"id_mat_estado": None, "ds_condicao": None}]:
            fontes = fontes_mat.get(m["id_material"], []) + [
                f for f in fontes_est.get(e["id_mat_estado"], []) if f not in fontes_mat.get(m["id_material"], [])]
            linhas.append((m["nm_material"], m["nm_resultado"] or "Não informado", m["nm_grupo"], m["nm_sub_grupo"],
                           m["nm_norma_designacao"], e["ds_condicao"], m["ds_observacao"], _ids(fontes)))
    return _tabela(("Material", "Resultado de Têmis", "Grupo", "Subgrupo", "Norma", "Condição", "Observações", "Fontes"), linhas)


def _cobertura(estados, comp_por_material, valores_por_estado, fases_por_estado, total_propriedades: int) -> str:
    if not estados:
        return "Sem materiais registrados: nada foi caracterizado."
    linhas = []
    for m, e in estados:
        qtd_comp = len(comp_por_material.get(m["id_material"], []))
        qtd_prop = len({p.id_propriedade for _, p in valores_por_estado.get(e["id_mat_estado"], [])})
        qtd_fases = len(fases_por_estado.get(e["id_mat_estado"], []))
        linhas.append((
            m["nm_material"], e["ds_condicao"],
            f"{qtd_comp} elemento(s)" if qtd_comp else "Não localizada",
            f"{qtd_prop} de {total_propriedades}",
            f"{qtd_fases} fase(s)" if qtd_fases else "Não localizada",
        ))
    return _tabela(("Material", "Condição", "Composição", "Propriedades com valor", "Fases"), linhas)


def _composicao(materiais, comp_por_material, fontes_comp) -> str:
    if not materiais:
        return "Sem materiais registrados."
    partes = []
    for m in materiais:
        partes.append(f"### {m['nm_material']}")
        itens = comp_por_material.get(m["id_material"], [])
        if not itens:
            partes.append("Sem composição gravada (ver seção 10).")
            continue
        partes.append(_tabela(
            ("Elemento", "Mínimo (%)", "Máximo ou valor único (%)", "Base", "Balanço", "Observações", "Fontes"),
            [(c.nm_sigla, _num(c.pe_min), _num(c.pe_max), c.nm_base_comp, "Sim" if c.fl_elem_balanco else "Não",
              c.ds_observacao, _ids(fontes_comp.get(c.id_composicao, []))) for c in itens],
        ))
    return "\n\n".join(partes)


def _propriedades(estados, valores_por_estado, fontes_vlp, cadastradas) -> str:
    if not estados:
        return "Sem materiais registrados."
    partes = []
    for m, e in estados:
        partes.append(f"### {m['nm_material']} — {e['ds_condicao'] or 'condição não informada'}")
        itens = valores_por_estado.get(e["id_mat_estado"], [])
        por_categoria = defaultdict(list)
        for v, p in itens:
            por_categoria[p.nm_categoria_prop or "Sem categoria"].append((v, p))
        for categoria, lista in por_categoria.items():
            partes.append(f"**{categoria}**")
            partes.append(_tabela(
                ("Propriedade", "Valor ou faixa", "Unidade", "Natureza e condição", "Fontes"),
                [(p.nm_propriedade, _faixa(v.vl_min_prop, v.vl_max_prop, v.vl_prop), p.ds_unidade, v.tp_valor,
                  _ids(fontes_vlp.get(v.id_vl_prop, []))) for v, p in lista],
            ))
        gravadas = {p.id_propriedade for _, p in itens}
        faltantes = [p["nm_propriedade"] for p in cadastradas if p["id_propriedade"] not in gravadas]
        if not itens:
            partes.append("Nenhum valor de propriedade gravado.")
        if faltantes:
            partes.append("Sem valor gravado (ver seção 10): " + "; ".join(_celula(f) for f in faltantes) + ".")
    return "\n\n".join(partes)


def _fases(estados, fases_por_estado, fontes_fase) -> str:
    if not estados:
        return "Sem materiais registrados."
    partes = []
    for m, e in estados:
        partes.append(f"### {m['nm_material']} — {e['ds_condicao'] or 'condição não informada'}")
        itens = fases_por_estado.get(e["id_mat_estado"], [])
        if not itens:
            partes.append("Sem fase gravada (ver seção 10).")
            continue
        partes.append(_tabela(
            ("Fase", "Estrutura", "Grupo espacial", "Fração (base)", "a, b, c (Å)", "α, β, γ (°)",
             "Massa específica (kg/m³)", "T (K) / P (Pa)", "Fontes"),
            [(f.nm_fase, f.nm_estrut_cristalina, f.ds_grupo_espacial,
              f"{f.vl_fracao_fase} ({f.nm_base_fracao})" if f.vl_fracao_fase and f.nm_base_fracao else f.vl_fracao_fase,
              _trio(f.vl_parametro_a_ang, f.vl_parametro_b_ang, f.vl_parametro_c_ang),
              _trio(f.vl_angulo_alfa_graus, f.vl_angulo_beta_graus, f.vl_angulo_gama_graus),
              _num(f.vl_massa_especifica_kgm3), _trio(f.vl_temperatura_k, f.vl_pressao_pa, sep=" / "),
              _ids(fontes_fase.get(f.id_fase, []))) for f in itens],
        ))
    return "\n\n".join(partes)


def _trio(*valores, sep=", ") -> str:
    if all(v is None for v in valores):
        return "—"
    return sep.join(_num(v) or "—" for v in valores)


def _referencias(fontes) -> str:
    if not fontes:
        return "Nenhuma fonte vinculada aos dados gravados."
    linhas = []
    for f in fontes:
        detalhes = [x for x in (
            f.nm_autores, f.nm_instituicao_publicadora, str(f.nr_ano_publicacao) if f.nr_ano_publicacao else None,
            f"DOI: {f.cd_doi}" if f.cd_doi else None, f.nm_url, f"ID externo: {f.cd_identificador_externo}" if f.cd_identificador_externo else None,
            f"Versão: {f.ds_versao}" if f.ds_versao else None, f"Acesso em {f.dt_acesso}" if f.dt_acesso else None,
            f.ds_observacoes,
        ) if x]
        linhas.append(f"- [{f.id_fonte}] {f.tp_fonte}: {f.nm_titulo}" + (". " + ". ".join(detalhes) if detalhes else ""))
    return "\n".join(linhas)
