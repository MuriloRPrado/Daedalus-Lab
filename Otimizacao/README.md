# Otimizacao (Daedalus Lab)

Módulo independente do fluxo de agentes em `Daedalus-Lab-projeto/`. Sugere composições de aço que
atingem metas de propriedades mecânicas com menor custo, menor pegada de CO₂ e menos elementos
críticos. Etapas planejadas: otimização de composição → tratamento térmico → descoberta de materiais.

Esta primeira entrega contém as tabelas, os dados de referência por elemento e o modelo substituto
composição → propriedades. O otimizador, o tratamento térmico e o chat entram nas próximas.

## Estrutura

| Caminho | Conteúdo |
|---|---|
| `database.py` | Tabelas: `modelo_ml`, `elemento_referencia`, `otimizacao`, `candidato_composicao`, `candidato_previsao`, `rota_tratamento`, `previsao_tratamento`, `candidato_estrutura` |
| `dados/elementos_referencia.csv` | Preço, CO₂ e HHI de 14 elementos (fontes abaixo) |
| `Rotinas/elementos.py` | Custo, CO₂ e HHI de uma composição; carga de `elemento_referencia` |
| `Rotinas/dados_acos.py` | Download e leitura do dataset de aços |
| `Rotinas/modelo_composicao.py` | Treino, validação e previsão do modelo |
| `criar_tabelas.py` | Cria as tabelas e carrega `elemento_referencia` |
| `treinar_modelo.py` | Treina, mostra as métricas e registra em `modelo_ml` |

## Como rodar (Python 3.11, dentro de `Otimizacao/`)

```bash
python -m pip install -r requirements.txt
cp .env.exemplo .env          # preencha DATABASE_URL (pode ser o mesmo Postgres do projeto)
python criar_tabelas.py
python treinar_modelo.py      # ~15 s em CPU; --sem-banco para não registrar em modelo_ml
```

Previsão em Python:

```python
from Rotinas.modelo_composicao import ModeloComposicao
from Rotinas.elementos import indicadores_composicao

liga = {"C": 0.01, "Ni": 18.0, "Co": 9.0, "Mo": 5.0, "Ti": 0.6, "Al": 0.1}   # % em massa, Fe por balanço
ModeloComposicao().prever(liga)      # propriedades com incerteza e aviso de domínio
indicadores_composicao(liga)         # custo USD/kg, kg CO2-eq/kg, HHI, elementos críticos
```

## Modelo composição → propriedades

- **Dados:** `steel_strength` do matminer ("Mechanical properties of some steels", Citrine Informatics,
  citrination.com/datasets/153092): 312 aços, 13 elementos de liga em % em massa, limites de
  escoamento e de resistência (MPa) e alongamento (%).
- **Domínio:** aços de alta resistência, com limite de escoamento de 1006 a 2510 MPa. Composições com algum
  elemento acima do teor máximo do treino são previstas, mas marcadas como fora do domínio.
- **Modelo:** ensemble de 10 XGBoost em amostras bootstrap por propriedade. A previsão é a média; a
  incerteza é o desvio entre membros × fator de calibração da validação cruzada (~95% dentro de ±1,96σ).
- **Validação cruzada (5 dobras):**

| Propriedade | MAE | RMSE | R² | MAE chutando a média |
|---|---|---|---|---|
| Limite de escoamento | 89,6 MPa | 126,4 MPa | 0,82 | 229,6 MPa |
| Limite de resistência | 90,6 MPa | 126,2 MPa | 0,87 | 294,2 MPa |
| Alongamento | 2,4 % | 3,6 % | 0,50 | 3,9 % |

O dataset não informa o tratamento térmico de cada aço; o modelo aprende o efeito médio da
composição na condição em que cada aço foi ensaiado. As previsões são sugestões para ensaio, não
especificação.

## Dados de referência por elemento

| Dado | Fonte |
|---|---|
| Preço (USD/kg, elemento puro) | `costdb_elements.csv` do pymatgen (Wolfram Alpha / Wikipedia, set/2013) |
| CO₂ (kg CO₂-eq/kg, GWP 100a) | Nuss & Eckelman (2014), *PLoS ONE* 9(7): e101298, Supporting Information S1, linha "TOTAL" (média ponderada pela produção global, inclui ferroligas) |
| HHI de produção e reservas | Gaultois et al. (2013), *Chem. Mater.* 25, 2911 (`hhi_data.csv` do pymatgen) |

Elemento crítico: HHI de produção acima de 2500 (mercado altamente concentrado): Si, Cr, V, Co, Nb, W.
C, Si e N não constam em Nuss & Eckelman; o CO₂ da liga é calculado sem eles e a função informa quais
ficaram de fora. Os preços são de 2013 e o do Fe (0,03 USD/kg) está abaixo do preço do ferro-gusa,
então o custo serve para comparar ligas entre si, não como orçamento.
