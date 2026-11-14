from sqlalchemy import inspect
import database

insp = inspect(database.engine)
for tabela in database.Base.metadata.sorted_tables:
    if not insp.has_table(tabela.name):
        print(f"FALTA A TABELA {tabela.name}")
        continue
    reais = {c["name"] for c in insp.get_columns(tabela.name)}
    for coluna in tabela.columns:
        if coluna.name not in reais:
            print(f"{tabela.name}.{coluna.name} não existe no banco; colunas sem par: {sorted(reais - set(tabela.columns.keys()))}")
print("verificação concluída")