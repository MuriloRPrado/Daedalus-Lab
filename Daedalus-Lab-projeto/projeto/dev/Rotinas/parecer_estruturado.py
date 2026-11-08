######################### BIBLIOTECAS ###################################
from typing import ClassVar, Literal
from pydantic import BaseModel, Field
#########################################################################

"""Saída estruturada dos pareceres de Atena e Argos.

O agente devolve a classificação por material em campos validados e o restante
do relatório em Markdown; em_markdown() monta o relatório completo gravado em
retorno_cientistas, com a tabela "Classificação por material" lida por Têmis.
"""

Classificacao = Literal["Atende", "Parcial", "Inconclusivo", "Não atende"]


class ClassificacaoMaterial(BaseModel):
    id: str = Field(description="ID do candidato/variante recebido de Prometeu (ou ID local, com a correspondência).")
    candidato_variante: str = Field(description="Designação do candidato ou variante, com condição/têmpera/produto quando houver.")
    classificacao: Classificacao = Field(description="Classificação final do candidato/variante, conforme a regra das instruções.")
    atendidos: list[str] = Field(description="Critérios com resultado Atende.")
    nao_atendidos: list[str] = Field(description="Critérios com resultado Não atende.")
    inconclusivos: list[str] = Field(description="Critérios com resultado Inconclusivo.")
    justificativa: str = Field(description="Justificativa da classificação pelos resultados por critério.")


class ParecerAvaliacao(BaseModel):
    COLUNAS_CRITERIOS: ClassVar[tuple[str, str, str]] = (
        "Critérios atendidos", "Critérios não atendidos", "Critérios inconclusivos")
    SEM_CRITERIOS: ClassVar[str] = "Sem critérios registrados"

    secao_decisao_resumida: str = Field(description="Seção 1 do relatório, em Markdown, com o título da seção.")
    sem_criterios: bool = Field(description="true somente quando o projeto não tem critérios registrados para este agente.")
    classificacao_por_material: list[ClassificacaoMaterial] = Field(
        description="Seção 2: uma entrada por candidato e por variante avaliados. Vazia quando sem_criterios for true."
    )
    secoes_seguintes: str = Field(description="Seções 3 em diante do relatório, em Markdown, com os títulos das seções.")

    def tabela_classificacao(self) -> str:
        atendidos, nao_atendidos, inconclusivos = self.COLUNAS_CRITERIOS
        linhas = [
            "### 2. Classificação por material",
            f"| ID | Candidato/variante | Classificação | {atendidos} | {nao_atendidos} | {inconclusivos} | Justificativa |",
            "|---|---|---|---|---|---|---|",
        ]
        if self.sem_criterios or not self.classificacao_por_material:
            texto = self.SEM_CRITERIOS if self.sem_criterios else "Nenhum candidato classificado"
            linhas.append(f"| — | {texto} | — | — | — | — | — |")
        for item in self.classificacao_por_material:
            celulas = (
                item.id, item.candidato_variante, item.classificacao,
                _lista(item.atendidos), _lista(item.nao_atendidos), _lista(item.inconclusivos),
                item.justificativa,
            )
            linhas.append("| " + " | ".join(_celula(c) for c in celulas) + " |")
        return "\n".join(linhas)

    def em_markdown(self) -> str:
        partes = (self.secao_decisao_resumida.strip(), self.tabela_classificacao(), self.secoes_seguintes.strip())
        return "\n\n".join(parte for parte in partes if parte)


class ParecerAtena(ParecerAvaliacao):
    COLUNAS_CRITERIOS: ClassVar[tuple[str, str, str]] = (
        "Requisitos atendidos", "Requisitos não atendidos", "Requisitos inconclusivos")
    SEM_CRITERIOS: ClassVar[str] = "Sem requisitos de propriedades registrados"


class ParecerArgos(ParecerAvaliacao):
    COLUNAS_CRITERIOS: ClassVar[tuple[str, str, str]] = (
        "Restrições atendidas", "Restrições não atendidas", "Restrições inconclusivas")
    SEM_CRITERIOS: ClassVar[str] = "Sem restrições químicas registradas"


def _lista(itens: list[str]) -> str:
    return "; ".join(item.strip() for item in itens if item.strip()) or "—"


def _celula(texto: str) -> str:
    return " ".join(str(texto).split()).replace("|", "\\|") or "—"
