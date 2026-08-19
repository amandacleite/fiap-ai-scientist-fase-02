"""
Validação de qualidade da camada Bronze usando Great Expectations.

Cobre as quatro dimensões exigidas pelo desafio:
- duplicidade               -> ExpectColumnValuesToBeUnique
- valores ausentes          -> ExpectColumnValuesToNotBeNull
- chaves de relacionamento  -> ExpectColumnValuesToBeInSet (contra a PK da tabela pai)
- consistência entre tabelas -> ExpectColumnValuesToBeBetween

Fonte dos dados: o S3 é a fonte "oficial" (é pra lá que src/main.py sobe
a Bronze depois de extrair do BigQuery). O script tenta o S3 primeiro,
pra qualquer pessoa do grupo com acesso ao bucket rodar isso sem precisar
ter rodado a extração na própria máquina. Só cai pro disco local ou pro
dado sintético se o S3 estiver inacessível ou vazio.

Uso:
    python -m quality.run_quality_checks
"""
import io
import json
import os
import random
from datetime import datetime, timezone
from pathlib import Path

import boto3
import pandas as pd
import great_expectations as gx
import great_expectations.expectations as gxe
from botocore.exceptions import ClientError, NoCredentialsError
from dotenv import load_dotenv
from great_expectations.core.expectation_suite import ExpectationSuite

load_dotenv()

AWS_BUCKET = os.getenv("AWS_BUCKET", "fiap-postech-challenge-fase2")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BRONZE_PREFIX = "bronze"  # ver src/cloud/s3.py: upload_file remove o prefixo "data/"

BRONZE_PATH = Path("data/bronze")  # fallback local, se o S3 não estiver acessível
EXPECTATIONS_PATH = Path("quality/expectations")
VALIDATIONS_PATH = Path("quality/validations")
REPORTS_PATH = Path("quality/reports")

# Fallback: municípios reais (código IBGE), usado apenas se nem o S3 nem
# o disco local tiverem a Bronze disponível. Mantém a lógica testável
# desde já, sem depender de credencial nenhuma.
MUNICIPIOS_FALLBACK = [
    ("3550308", "São Paulo", "SP"),
    ("3304557", "Rio de Janeiro", "RJ"),
    ("2927408", "Salvador", "BA"),
    ("2304400", "Fortaleza", "CE"),
    ("3106200", "Belo Horizonte", "MG"),
    ("1302603", "Manaus", "AM"),
    ("4106902", "Curitiba", "PR"),
    ("4314902", "Porto Alegre", "RS"),
    ("5300108", "Brasília", "DF"),
    ("2611606", "Recife", "PE"),
]


def gerar_municipios_fallback() -> pd.DataFrame:
    linhas = []
    for id_municipio, _, _ in MUNICIPIOS_FALLBACK:
        for ano in (2024, 2025):
            linhas.append({
                "id_municipio": id_municipio,
                "ano": ano,
                "serie": "2",
                "rede": "Municipal",
                "taxa_alfabetizacao": round(random.uniform(55.0, 95.0), 1),
            })
    return pd.DataFrame(linhas)


def gerar_metas_municipios_fallback() -> pd.DataFrame:
    linhas = []
    for id_municipio, _, _ in MUNICIPIOS_FALLBACK:
        for ano in (2024, 2025):
            linha = {
                "id_municipio": id_municipio,
                "ano": ano,
                "rede": "Municipal",
                "taxa_alfabetizacao": round(random.uniform(55.0, 95.0), 1),
            }
            for ano_meta in range(2024, 2031):
                linha[f"meta_alfabetizacao_{ano_meta}"] = round(random.uniform(55.0, 90.0), 1)
            linhas.append(linha)
    return pd.DataFrame(linhas)


def gerar_alunos_fallback() -> pd.DataFrame:
    linhas = []
    for id_municipio, _, _ in MUNICIPIOS_FALLBACK:
        for _ in range(20):
            linhas.append({
                "id_municipio": id_municipio,
                "id_aluno": f"{id_municipio}-{random.randint(1000, 9999)}",
                "proficiencia": round(random.uniform(500.0, 900.0), 1),
                "ano": random.choice([2024, 2025]),
            })
    return pd.DataFrame(linhas)


GERADORES_FALLBACK = {
    "municipios": gerar_municipios_fallback,
    "metas_municipios": gerar_metas_municipios_fallback,
    "alunos": gerar_alunos_fallback,
}


def carregar_tabela_do_s3(nome_tabela: str) -> pd.DataFrame | None:
    """
    Lê todos os .parquet sob bronze/{nome_tabela}/ no S3.
    Devolve None (em vez de lançar exceção) se não conseguir —
    quem chama decide qual é o próximo fallback.
    """
    prefixo = f"{S3_BRONZE_PREFIX}/{nome_tabela}/"

    try:
        cliente = boto3.client("s3", region_name=AWS_REGION)
        resposta = cliente.list_objects_v2(Bucket=AWS_BUCKET, Prefix=prefixo)
    except (NoCredentialsError, ClientError) as erro:
        print(f"[aviso] não foi possível acessar o S3 ({erro}). Tentando outra fonte.")
        return None

    chaves_parquet = [
        obj["Key"] for obj in resposta.get("Contents", []) if obj["Key"].endswith(".parquet")
    ]
    if not chaves_parquet:
        print(f"[aviso] nenhum parquet em s3://{AWS_BUCKET}/{prefixo}. Tentando outra fonte.")
        return None

    dataframes = []
    for chave in chaves_parquet:
        objeto = cliente.get_object(Bucket=AWS_BUCKET, Key=chave)
        dataframes.append(pd.read_parquet(io.BytesIO(objeto["Body"].read())))

    print(f"[info] {nome_tabela}: lido do S3 (s3://{AWS_BUCKET}/{prefixo})")
    return pd.concat(dataframes, ignore_index=True)


def carregar_tabela_do_disco(nome_tabela: str) -> pd.DataFrame | None:
    """Fallback local — útil só em desenvolvimento, sem acesso ao bucket."""
    pasta = BRONZE_PATH / nome_tabela
    arquivos = list(pasta.glob("*.parquet"))
    if not arquivos:
        return None

    print(f"[aviso] {nome_tabela}: lido do disco local ({pasta}), não do S3.")
    return pd.concat([pd.read_parquet(f) for f in arquivos], ignore_index=True)


def carregar_tabela(nome_tabela: str) -> pd.DataFrame:
    df = carregar_tabela_do_s3(nome_tabela)
    if df is not None:
        return df

    df = carregar_tabela_do_disco(nome_tabela)
    if df is not None:
        return df

    print(
        f"[aviso] {nome_tabela}: nem S3 nem disco local disponíveis — "
        "usando dado de exemplo (fallback) só para validar a lógica."
    )
    return GERADORES_FALLBACK[nome_tabela]()


def montar_suite_municipios() -> ExpectationSuite:
    """
    Tabela 'municipio' = indicador de alfabetização por município/ano/série/rede
    (não é uma dimensão de nome de cidade — só existe o código IBGE).
    """
    suite = ExpectationSuite(name="municipios_suite")
    suite.add_expectation(
        gxe.ExpectCompoundColumnsToBeUnique(column_list=["id_municipio", "ano", "serie", "rede"])
    )
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="id_municipio"))
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="ano"))
    suite.add_expectation(
        gxe.ExpectColumnValuesToBeBetween(column="taxa_alfabetizacao", min_value=0, max_value=100)
    )
    return suite


def montar_suite_metas_municipios(ids_municipios_validos: list[str]) -> ExpectationSuite:
    suite = ExpectationSuite(name="metas_municipios_suite")
    suite.add_expectation(
        gxe.ExpectCompoundColumnsToBeUnique(column_list=["id_municipio", "ano", "rede"])
    )
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="id_municipio"))
    suite.add_expectation(
        gxe.ExpectColumnValuesToBeInSet(column="id_municipio", value_set=ids_municipios_validos)
    )
    for ano_meta in range(2024, 2031):
        suite.add_expectation(
            gxe.ExpectColumnValuesToBeBetween(
                column=f"meta_alfabetizacao_{ano_meta}", min_value=0, max_value=100
            )
        )
    return suite


def montar_suite_alunos(ids_municipios_validos: list[str]) -> ExpectationSuite:
    suite = ExpectationSuite(name="alunos_suite")
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="id_municipio"))
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="id_aluno"))
    suite.add_expectation(
        gxe.ExpectColumnValuesToBeInSet(column="id_municipio", value_set=ids_municipios_validos)
    )
    # TODO: ajustar min/max de 'proficiencia' após confirmar a escala exata
    # no dicionario.parquet (o corte oficial do Saeb usado no indicador é 743).
    suite.add_expectation(
        gxe.ExpectColumnValuesToBeBetween(column="proficiencia", min_value=0, max_value=1000)
    )
    return suite


def validar_tabela(context, nome_tabela: str, df: pd.DataFrame, suite: ExpectationSuite) -> dict:
    context.suites.add(suite)

    data_source = context.data_sources.add_pandas(name=f"{nome_tabela}_datasource")
    data_asset = data_source.add_dataframe_asset(name=nome_tabela)
    batch_definition = data_asset.add_batch_definition_whole_dataframe(f"{nome_tabela}_batch")

    batch = batch_definition.get_batch(batch_parameters={"dataframe": df})
    resultado = batch.validate(suite)
    return resultado.describe_dict()


def salvar_json(caminho: Path, conteudo: dict) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(conteudo, f, ensure_ascii=False, indent=2, default=str)


def rodar_checks() -> list[dict]:
    context = gx.get_context(mode="ephemeral")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    resumo = []

    municipios = carregar_tabela("municipios")
    ids_validos = municipios["id_municipio"].astype(str).tolist()

    tabelas = {
        "municipios": (municipios, montar_suite_municipios()),
        "metas_municipios": (carregar_tabela("metas_municipios"), montar_suite_metas_municipios(ids_validos)),
        "alunos": (carregar_tabela("alunos"), montar_suite_alunos(ids_validos)),
    }

    for nome_tabela, (df, suite) in tabelas.items():
        salvar_json(EXPECTATIONS_PATH / f"{nome_tabela}_suite.json", suite.to_json_dict())

        resultado = validar_tabela(context, nome_tabela, df, suite)
        salvar_json(VALIDATIONS_PATH / f"{nome_tabela}_{timestamp}.json", resultado)

        passou = resultado.get("success", False)
        resumo.append({
            "tabela": nome_tabela,
            "passou": passou,
            "total_expectativas": len(resultado.get("expectations", [])),
        })

    return resumo


def salvar_relatorio(resumo: list[dict]) -> Path:
    REPORTS_PATH.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    caminho = REPORTS_PATH / f"relatorio_{timestamp}.json"

    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "tabelas_validadas": len(resumo),
        "tabelas_com_falha": sum(1 for r in resumo if not r["passou"]),
        "resumo": resumo,
    }
    salvar_json(caminho, payload)
    return caminho


def main() -> None:
    resumo = rodar_checks()
    caminho_relatorio = salvar_relatorio(resumo)

    print(f"\nRelatório de qualidade: {caminho_relatorio}\n")
    for r in resumo:
        status = "OK" if r["passou"] else "FALHOU"
        print(f"[{status}] {r['tabela']} — {r['total_expectativas']} expectativas checadas")


if __name__ == "__main__":
    main()