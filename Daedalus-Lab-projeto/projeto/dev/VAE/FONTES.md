# Fontes da base de composições

Todas as composições de `dados/base_composicoes.csv` vêm das bases públicas abaixo. Os arquivos originais estão em `dados/brutos/`, e `python construir_base.py` refaz a base a partir deles. Nenhuma composição foi digitada ou estimada à mão.

Os títulos, autores, anos e licenças foram conferidos nos metadados oficiais dos DOIs (DataCite) e na API do GitHub.

| Pasta em `dados/brutos/` | Família | Dataset (autores, ano) | DOI / origem | Licença | Unidade original | Ligas na base |
|---|---|---|---|---|---|---|
| `aluminio_pfeiffer2022` | Alumínio | *Aluminum alloy compositions and properties extracted from a corpus of scientific manuscripts and US patents*. Pfeiffer, O. P.; Liu, H.; Montanelli, L.; Latypov, M. I.; Sen, F. G.; Hegadekatte, V. et al. (2022, Materials Cloud) | 10.24435/materialscloud:ac-c2 | CC BY 4.0 | % massa | 4 896 |
| `mpea_borg2020` | Ligas multiprincipais / alta entropia | *Expanded dataset of mechanical properties and observed phases of multi-principal element alloys*. Borg et al. (2020). Cada linha traz o DOI do artigo original | github.com/CitrineInformatics/MPEA_dataset | Apache‑2.0 | fórmula molar → convertida | 630 |
| `superligas_cambridge2022` | Superligas Ni/Co | *Superalloy database: strength and microstructure*. Taylor, P. (2022, Univ. of Cambridge Apollo) | 10.17863/CAM.92063 | CC BY 4.0 | % massa | 559 |
| `corrosao_nyby2021` | Inox, Ni‑Cr‑Mo e outras ligas resistentes à corrosão | *Electrochemical Metrics for Corrosion Resistant Alloys*. Nyby, C.; Saal, J. E. et al. (2020, figshare) | 10.6084/m9.figshare.13038257.v2 | CC BY 4.0 | % massa | 554 |
| `acos_citrine` | Aços (sobretudo de alta resistência/maraging) | `steel_strength` do matminer, originalmente Citrine Informatics, dataset 153092 | citrination.com/datasets/153092 | não identificada no metadata | % massa, Fe como balanço | 312 |
| `titanio_scidata2022` | Titânio | *A compilation of experimental data on the mechanical properties and microstructural features of Ti-alloys*. Salvador, C. A. F. et al. (2022, Zenodo) | 10.5281/zenodo.6089749 | CC BY 4.0 | fórmula molar → convertida | 253 |
| `cobre_scidata2023` | Ligas de cobre de alto desempenho | *Dataset of mechanical properties and electrical conductivity of copper-based alloys*. Gorsse, S.; Gouné, M.; Lin, W.‑C.; Girard, L. (2023, figshare) | 10.6084/m9.figshare.23735373.v1 | CC0 | % massa | 114 |
| `magnesio_ghorbani2025` | Magnésio | *Magnesium Alloy Mechanical Property Database*. Ghorbani, M.; Birbilis, N. (Mendeley Data, v2) | 10.17632/2fjhmdg5nt.2 | CC BY 4.0 | % massa | 619 |
| `magnesio_atwakyire2024` | Magnésio (Mg‑Zn‑Y‑Zr‑Nd‑Gd) | *Accelerated optimal design of high-performance Mg alloys through integration of Bayesian optimization with active machine learning* (Mendeley Data) | 10.17632/gswj9rcv7d.1 | CC BY 4.0 | % massa | 157 |
| `magnesio_nandal2025` | Magnésio diluído (biomédico) | *Accelerating the Design of Resorbable Magnesium Alloys* — arquivo bruto `Extracted_data_Raw.csv` (Zenodo). Cada linha traz o DOI do artigo original | 10.5281/zenodo.17672235 | CC BY 4.0 | % massa, Mg como balanço | 149 |
| `ferro_fundido_hcci_muller2024` | Ferro fundido branco alto cromo | *HCCI CVF Composition Database* (Zenodo, 2024). Cada linha traz a referência/DOI do artigo original | 10.5281/zenodo.10654150 | CC BY 4.0 | % massa, Fe como balanço | 307 |
| `acos_literatura_taniushkina2026` | Aços (carbono, baixa liga, inox, TRIP/TWIP etc.) | *Steel process–property dataset v1*, extraído de 945 artigos CC BY (Zenodo, 2026). Cada linha traz o DOI do artigo | 10.5281/zenodo.24231683 | CC BY 4.0 | % massa, Fe como balanço | 216 |
| `acos_nims_steelbench2026` | Aços carbono e baixa liga (C, Cr‑Mo, Ni‑Cr‑Mo) | *SteelBench v1.0*, só o tier `nims_measured` (dados medidos do NIMS, Japão) | 10.5281/zenodo.18530558 | CC BY 4.0 | % massa, Fe como balanço | 120 |
| `cobre_cunisi_kolev2024` | Cu‑Ni‑Si | *Cu-Ni-Si alloys* (Mendeley Data). Lido, mas as 37 linhas já estavam na fonte `cobre_scidata2023` e saem como duplicatas | 10.17632/7tdd6vngzm.1 | CC BY 4.0 | % massa | 0 |

Total: **8 886 composições únicas**, 59 elementos com ocorrência e soma = 100 % em todas as linhas (desvio máximo de 6·10⁻¹⁴). Contagens por fonte, família e elemento estão em `dados/resumo_base.json`.

> A licença do dataset de aços não foi encontrada no metadata do matminer. Se a base for redistribuída fora do uso interno, confirme a licença antes ou treine sem essa fonte (`--fontes` sem `Citrine_acos`).

## Tratamento aplicado (`construir_base.py`)

1. **Alumínio:** entram só as linhas com `source` = `named` (ligas registradas na Aluminum Association) e `table` (tabelas de artigos, com o DOI do artigo na coluna `referencia`). As linhas `full text` e `patent` ficam de fora porque foram extraídas de texto corrido e de patentes.
2. **Superligas:** entram só as linhas de liga inteira, sem as linhas de fases isoladas (γ, γ'), com a composição da coluna "wt. %".
3. **Corrosão:** todas as abas, menos `References`. As linhas com valor na coluna agregada `Nb+Ta` são descartadas porque não dá para separar os dois elementos.
4. **MPEA e Ti:** a fórmula molar é convertida para % em massa com as massas atômicas padrão do `pymatgen`.
5. **Aços, ferro fundido e Mg (Nandal):** o elemento-base (Fe ou Mg) = 100 − soma dos demais, que é como as fontes definem o balanço.
6. **Critérios das fontes novas:**
   - *SteelBench:* só o tier `nims_measured`. Os tiers `emk_spec_verified` (mínimos de norma) e `kaggle_measured` (proveniência incerta) ficam de fora.
   - *Taniushkina:* só estados com `composition_type` = `measured` ou `certificate` e `specimen_type` = `base`. Ficam de fora composições nominais, de norma (faixa), "unclear" e de solda/HAZ/AM, além de linhas com faixa `a-b` ou `<x`.
   - *Nandal:* usa o arquivo bruto, e não o `DatasetMg_imputed` (aumentado artificialmente). Linhas com a coluna `RE` (terras-raras sem elemento definido) são descartadas.
   - *HCCI:* linhas com célula ilegível (ex.: `0. 11`) são descartadas, sem corrigir o valor.
7. **Descartes:**
   - linhas com H, O ou F (137 linhas: óxidos, hidretos ou impurezas medidas, incluindo aços com O analisado);
   - linhas de alumínio com N > 0,5 % (3 linhas, compósitos Al‑AlN);
   - linhas em % massa com soma original fora de 99–101 %.
8. **Normalização:** as linhas aceitas são renormalizadas para 100 %. A soma original fica na coluna `soma_original`, e o resíduo de arredondamento vai para o elemento majoritário.
9. **Duplicatas:** composições idênticas são removidas (6 198). As fontes repetem a mesma liga com tratamentos térmicos ou ensaios diferentes.

## Lacunas de cobertura (importante)

Ainda **sem fonte confiável** (não encontrei dataset público com DOI, licença e composições medidas/normatizadas):
- latões e bronzes (Cu‑Zn, Cu‑Sn);
- ligas de zinco;
- ligas de chumbo.

Cobertura **parcial**:
- ferros fundidos: só branco alto cromo (sem cinzento, nodular ou vermicular);
- aços carbono/baixa liga: 336 composições novas (NIMS e literatura), ainda poucas perto da variedade de graus comerciais.

Para essas famílias o modelo **extrapola**, e o `gerar.py` avisa quando a composição fica longe de qualquer liga da base.

A base também é desbalanceada: o alumínio é cerca de 55 % das linhas. O treino repondera as famílias por 1/√(tamanho da família), e isso pode ser desligado com `--sem-balanceamento`.
