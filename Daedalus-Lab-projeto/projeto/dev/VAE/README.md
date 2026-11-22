# VAE de composições

Modelo VAE condicional (cerca de 30 mil parâmetros) que gera composições em % em massa, com soma exata de 100 %, usando somente os elementos informados.

- `modelo_vae.pt`: checkpoint em uso. Para trocar, substitua o arquivo; os elementos e a arquitetura são lidos dele.
- `dados/base_composicoes.csv`: base de ligas reais usada no treino. A Calíope também a usa para comparação. As fontes e licenças estão em `FONTES.md`.
- `gerador.py`: geração (`gerar_composicoes`) e busca das ligas mais próximas (`ligas_mais_proximas`).

O treino e a reconstrução da base ficam no pacote `vae_composicoes` (`treinar.py`, `construir_base.py`). Use a mesma base deste diretório.
