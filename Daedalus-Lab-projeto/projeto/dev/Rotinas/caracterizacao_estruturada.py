"""Saída estruturada das etapas intermediárias da Calíope e conferência de cobertura.

Cada etapa (Composição, Propriedades e Estrutura Cristalina) devolve, para cada material
ou estado, o que foi gravado e as lacunas justificadas. pendencias_*() compara essa saída
com o que está gravado no banco: itens sem dado e sem justificativa voltam para uma
segunda execução, restrita a eles. em_markdown() monta o texto gravado em retorno_cientistas.
"""
######################### BIBLIOTECAS ###################################
from typing import ClassVar, Literal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import ValorPropriedades, engine
from Rotinas.dados_prompt import propriedades_cadastradas
from Rotinas.registro_materiais import listar_materiais_projeto
#########################################################################

Situacao = Literal["Gravado", "Não localizado"]


class Lacuna(BaseModel):
    dado: str = Field(description="Dado não localizado (ex.: \"Composição química\", \"Fase secundária\", nome da propriedade).")
    motivo: str = Field(description="Por que o dado não foi gravado (ex.: fonte aplicável não localizada, só havia dado de outra condição).")
    buscas_realizadas: list[str] = Field(description="Buscas e leituras feitas para o dado (consulta, ferramenta, URL ou DOI).")
    sugestao: str = Field(description="O que o usuário pode fazer para obter o dado (ex.: norma a adquirir, ensaio, fabricante a consultar).")


class _Item(BaseModel):
    nm_material: str = Field(description="Designação do material, como registrada.")
    situacao: Situacao = Field(description="\"Gravado\" quando há dado gravado no banco; \"Não localizado\" quando nada foi gravado.")
    lacunas: list[Lacuna] = Field(description="Dados que faltaram, com motivo, buscas e sugestão. Obrigatório quando situacao for \"Não localizado\".")
    observacao: str = Field(description="Observações (divergências entre fontes, dados calculados, falhas de gravação). Vazio se não houver.")


class ItemComposicao(_Item):
    id_material: int = Field(description="id_material do material.")


class ItemEstado(_Item):
    id_mat_estado: int = Field(description="id_mat_estado do estado do material.")


class PropriedadeNaoLocalizada(Lacuna):
    id_propriedade: int = Field(description="id_propriedade da propriedade não localizada.")


class ItemPropriedades(BaseModel):
    id_mat_estado: int = Field(description="id_mat_estado do estado do material.")
    nm_material: str = Field(description="Designação do material, como registrada.")
    propriedades_nao_localizadas: list[PropriedadeNaoLocalizada] = Field(
        description="Uma entrada por propriedade cadastrada que não foi gravada para o estado, com motivo, buscas e sugestão.")
    observacao: str = Field(description="Observações (divergências entre fontes, dados calculados, falhas de gravação). Vazio se não houver.")


class _Cobertura(BaseModel):
    observacoes_gerais: str = Field(description="Limites operacionais (ex.: créditos), falhas e observações gerais da etapa. Vazio se não houver.")

    TITULO: ClassVar[str] = ""

    def em_markdown(self) -> str:
        partes = [f"# {self.TITULO}", self._tabela()]
        lacunas = self._lacunas()
        if lacunas:
            partes += ["## Lacunas", _tabela(("ID", "Material", "Dado", "Motivo", "Buscas realizadas", "Sugestão"), lacunas)]
        if self.observacoes_gerais.strip():
            partes += ["## Observações gerais", self.observacoes_gerais.strip()]
        return "\n\n".join(partes)


class CoberturaComposicao(_Cobertura):
    TITULO: ClassVar[str] = "Calíope - Composição: cobertura por material"
    itens: list[ItemComposicao] = Field(description="Uma entrada por material pesquisado.")

    def _tabela(self):
        return _tabela(("id_material", "Material", "Situação", "Observação"),
                       [(i.id_material, i.nm_material, i.situacao, i.observacao) for i in self.itens])

    def _lacunas(self):
        return [(i.id_material, i.nm_material, *_lacuna(lac)) for i in self.itens for lac in i.lacunas]


class CoberturaEstrutura(_Cobertura):
    TITULO: ClassVar[str] = "Calíope - Estrutura Cristalina: cobertura por estado"
    itens: list[ItemEstado] = Field(description="Uma entrada por estado de material pesquisado.")

    def _tabela(self):
        return _tabela(("id_mat_estado", "Material", "Situação", "Observação"),
                       [(i.id_mat_estado, i.nm_material, i.situacao, i.observacao) for i in self.itens])

    def _lacunas(self):
        return [(i.id_mat_estado, i.nm_material, *_lacuna(lac)) for i in self.itens for lac in i.lacunas]


class CoberturaPropriedades(_Cobertura):
    TITULO: ClassVar[str] = "Calíope - Propriedades: cobertura por estado"
    itens: list[ItemPropriedades] = Field(description="Uma entrada por estado de material pesquisado.")

    def _tabela(self):
        return _tabela(("id_mat_estado", "Material", "Propriedades não localizadas", "Observação"),
                       [(i.id_mat_estado, i.nm_material, len(i.propriedades_nao_localizadas), i.observacao) for i in self.itens])

    def _lacunas(self):
        return [(i.id_mat_estado, i.nm_material, *_lacuna(p, f"{p.dado} (id_propriedade {p.id_propriedade})"))
                for i in self.itens for p in i.propriedades_nao_localizadas]


######################### CONFERÊNCIA DE COBERTURA ###################################

def pendencias_composicao(id_projeto: int, saida: CoberturaComposicao | None) -> list[dict]:
    """Materiais sem composição gravada e sem lacuna justificada na saída."""
    justificados = {i.id_material for i in (saida.itens if saida else []) if i.situacao == "Não localizado" and i.lacunas}
    return [
        {"id_material": m["id_material"], "nm_material": m["nm_material"]}
        for m in listar_materiais_projeto(id_projeto)["materiais"]
        if m["qtd_elementos_composicao"] == 0 and m["id_material"] not in justificados
    ]


def pendencias_estrutura(id_projeto: int, saida: CoberturaEstrutura | None) -> list[dict]:
    """Estados sem fase gravada e sem lacuna justificada na saída."""
    justificados = {i.id_mat_estado for i in (saida.itens if saida else []) if i.situacao == "Não localizado" and i.lacunas}
    return [
        {"id_mat_estado": e["id_mat_estado"], "nm_material": m["nm_material"], "ds_condicao": e["ds_condicao"]}
        for m in listar_materiais_projeto(id_projeto)["materiais"] for e in m["estados"]
        if e["qtd_fases"] == 0 and e["id_mat_estado"] not in justificados
    ]


def pendencias_propriedades(id_projeto: int, saida: CoberturaPropriedades | None) -> list[dict]:
    """Por estado, as propriedades cadastradas sem valor gravado e sem lacuna justificada na saída."""
    cadastradas = {p["id_propriedade"]: p["nm_propriedade"] for p in propriedades_cadastradas()}
    justificadas = {
        (i.id_mat_estado, p.id_propriedade)
        for i in (saida.itens if saida else []) for p in i.propriedades_nao_localizadas
    }
    pendentes = []
    for m in listar_materiais_projeto(id_projeto)["materiais"]:
        for e in m["estados"]:
            gravadas = _propriedades_gravadas(e["id_mat_estado"])
            faltantes = [
                {"id_propriedade": id_prop, "nm_propriedade": nome}
                for id_prop, nome in cadastradas.items()
                if id_prop not in gravadas and (e["id_mat_estado"], id_prop) not in justificadas
            ]
            if faltantes:
                pendentes.append({
                    "id_mat_estado": e["id_mat_estado"], "nm_material": m["nm_material"],
                    "ds_condicao": e["ds_condicao"], "propriedades": faltantes,
                })
    return pendentes


def combinar(primeira: _Cobertura | None, segunda: _Cobertura | None, chave: str) -> _Cobertura | None:
    """Junta a saída da segunda execução à da primeira; para o mesmo ID, prevalece a segunda."""
    if primeira is None or segunda is None:
        return segunda or primeira
    novos = {getattr(i, chave): i for i in segunda.itens}
    if chave == "id_mat_estado" and isinstance(primeira, CoberturaPropriedades):
        # Na segunda execução de propriedades só entram as pendentes: soma as lacunas das duas.
        for i in primeira.itens:
            novo = novos.get(i.id_mat_estado)
            if novo is not None:
                ids_novos = {p.id_propriedade for p in novo.propriedades_nao_localizadas}
                novo.propriedades_nao_localizadas = [
                    p for p in i.propriedades_nao_localizadas if p.id_propriedade not in ids_novos
                ] + novo.propriedades_nao_localizadas
    itens = [novos.pop(getattr(i, chave), i) for i in primeira.itens] + list(novos.values())
    observacoes = "\n\n".join(t.strip() for t in (primeira.observacoes_gerais, segunda.observacoes_gerais) if t.strip())
    return type(primeira)(itens=itens, observacoes_gerais=observacoes)


def markdown_pendencias(pendencias: list[dict], descricao: str) -> str:
    """Seção acrescentada ao retorno quando sobram itens sem dado e sem justificativa após a segunda execução."""
    if not pendencias:
        return ""
    linhas = [f"## Pendências sem justificativa do agente ({descricao})",
              "Itens que continuaram sem dado gravado e sem lacuna justificada após a segunda execução."]
    for p in pendencias:
        identificador = f"id_material {p['id_material']}" if "id_material" in p else f"id_mat_estado {p['id_mat_estado']}"
        extra = ""
        if "propriedades" in p:
            extra = ": " + "; ".join(f"{x['nm_propriedade']} (id_propriedade {x['id_propriedade']})" for x in p["propriedades"])
        linhas.append(f"- {identificador}, {p['nm_material']}{extra}")
    return "\n".join(linhas)


def _propriedades_gravadas(id_mat_estado: int) -> set[int]:
    with Session(engine) as session:
        return set(session.execute(
            select(ValorPropriedades.id_propriedade).where(ValorPropriedades.id_mat_estado == id_mat_estado).distinct()
        ).scalars())


def _lacuna(lacuna: Lacuna, dado: str | None = None) -> tuple:
    return (dado or lacuna.dado, lacuna.motivo, "; ".join(lacuna.buscas_realizadas) or "—", lacuna.sugestao)


def _tabela(colunas: tuple, linhas: list[tuple]) -> str:
    saida = ["| " + " | ".join(colunas) + " |", "|" + "---|" * len(colunas)]
    if not linhas:
        saida.append("| " + " | ".join(["—"] * len(colunas)) + " |")
    for linha in linhas:
        saida.append("| " + " | ".join(_celula(c) for c in linha) + " |")
    return "\n".join(saida)


def _celula(valor) -> str:
    texto = "" if valor is None else str(valor)
    return " ".join(texto.split()).replace("|", "\\|") or "—"
