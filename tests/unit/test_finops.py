import pytest

from src.finops.analise_s3 import (
    BYTES_POR_GIB,
    camada_da_chave,
    combinar_regras_lifecycle,
    configuracao_lifecycle,
    estimar_armazenamento_usd,
    inventariar,
)


class PaginadorFalso:
    def paginate(self, **_kwargs):
        return [
            {
                "Contents": [
                    {"Key": "bronze/a.parquet", "Size": 100},
                    {"Key": "bronze/b.parquet", "Size": 200, "StorageClass": "STANDARD_IA"},
                ]
            }
        ]


class S3Falso:
    def get_paginator(self, _operacao):
        return PaginadorFalso()


def test_estimar_um_gib_standard():
    assert estimar_armazenamento_usd(BYTES_POR_GIB, 0.023) == 0.023


def test_identificar_camada():
    assert camada_da_chave("bronze/municipios/arquivo.parquet") == "bronze"


def test_lifecycle_exige_ordem_de_dias():
    with pytest.raises(ValueError):
        configuracao_lifecycle("bronze/", 90, 30)


def test_lifecycle_nao_move_objetos_pequenos():
    regra = configuracao_lifecycle("bronze/", 30, 90)["Rules"][0]
    assert regra["Filter"]["And"]["ObjectSizeGreaterThan"] == 131072


def test_inventario_soma_objetos_e_bytes_sem_baixar_arquivos():
    resultado = inventariar(S3Falso(), "bucket-teste", "bronze/")
    assert resultado["total_objetos"] == 2
    assert resultado["total_bytes"] == 300


def test_lifecycle_preserva_regra_de_terceiro():
    regra_colega = {"ID": "regra-do-colega", "Status": "Enabled"}
    regras_finops = configuracao_lifecycle("bronze/", 30, 90)["Rules"]
    resultado = combinar_regras_lifecycle([regra_colega], regras_finops)
    assert regra_colega in resultado
    assert len(resultado) == 3


def test_lifecycle_atualiza_sem_duplicar_as_proprias_regras():
    regras_antigas = configuracao_lifecycle("bronze/", 30, 90)["Rules"]
    regras_novas = configuracao_lifecycle("bronze/", 45, 120)["Rules"]
    resultado = combinar_regras_lifecycle(regras_antigas, regras_novas)
    assert len(resultado) == 2
    assert resultado[0]["Transitions"][0]["Days"] == 45
