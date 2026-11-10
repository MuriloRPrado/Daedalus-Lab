"""Treina e valida o modelo composição → propriedades e registra as métricas em modelo_ml.

Uso (dentro de Otimizacao/): python treinar_modelo.py [--sem-banco]
Sem DATABASE_URL (ou com --sem-banco) o modelo é salvo em modelos/ sem registro no banco.
"""
import argparse
import os

from Rotinas.modelo_composicao import ARQUIVO_MODELO, treinar


def registrar(artefato: dict) -> list[int]:
    from database import ModeloML, obter_sessao

    with obter_sessao() as sessao:
        registros = []
        for alvo, dados in artefato["alvos"].items():
            metricas = dados["metricas"]
            registro = ModeloML(
                nm_modelo=artefato["nome"], nm_versao=artefato["versao"], nm_tipo=artefato["tipo"],
                nm_propriedade=alvo, ds_unidade=dados["unidade"], nm_dataset=artefato["dataset"],
                nr_amostras=dados["nr_amostras"], vl_mae=metricas["mae"], vl_rmse=metricas["rmse"],
                vl_r2=metricas["r2"], ds_metricas=metricas | {"hiperparametros": artefato["hiperparametros"]},
                ds_dominio=artefato["dominio"], ds_caminho_artefato=str(ARQUIVO_MODELO),
            )
            sessao.add(registro)
            registros.append(registro)
        sessao.commit()
        return [r.id_modelo for r in registros]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sem-banco", action="store_true", help="não registra em modelo_ml")
    args = parser.parse_args()

    artefato = treinar()
    print(f"Modelo {artefato['nome']} v{artefato['versao']} ({artefato['nr_amostras']} aços) salvo em {ARQUIVO_MODELO}")
    print(f"{'propriedade':<20}{'MAE':>9}{'RMSE':>9}{'R²':>7}{'cob. ens.':>10}{'fator σ':>9}{'MAE média':>11}")
    for alvo, dados in artefato["alvos"].items():
        m = dados["metricas"]
        print(f"{alvo:<20}{m['mae']:>9.1f}{m['rmse']:>9.1f}{m['r2']:>7.2f}{m['cobertura_ensemble_1_96']:>10.0%}{m['fator_calibracao']:>9.2f}"
              f"{m['mae_palpite_media']:>11.1f}  ({dados['unidade']}, {dados['nr_amostras']} aços)")

    if args.sem_banco or not os.getenv("DATABASE_URL"):
        print("Sem registro em modelo_ml (DATABASE_URL não configurada ou --sem-banco).")
    else:
        print(f"Registrado em modelo_ml: ids {registrar(artefato)}")
