"""Cria as tabelas do módulo Otimizacao e carrega elemento_referencia.

Uso (dentro de Otimizacao/): python criar_tabelas.py
"""
from database import criar_tabelas, obter_sessao
from Rotinas.elementos import popular_tabela

if __name__ == "__main__":
    criar_tabelas()
    with obter_sessao() as sessao:
        total = popular_tabela(sessao)
    print(f"Tabelas criadas; {total} elementos em elemento_referencia.")
