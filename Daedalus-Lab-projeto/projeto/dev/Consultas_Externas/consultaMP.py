"""Mantido só para compatibilidade dos agentes: as consultas foram movidas para Rotinas/materials_project.py."""
from Rotinas.materials_project import *  # noqa: F401,F403
from Rotinas.materials_project import (  # noqa: F401
    buscar_materiais, buscar_materiais_por_elementos, consultar_material_por_id, consultar_estrutura_cristalina,
    consultar_estabilidade, consultar_elasticidade, consultar_proveniencia,
)
