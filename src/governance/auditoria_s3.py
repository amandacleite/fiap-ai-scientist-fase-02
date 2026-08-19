"""Auditoria somente leitura dos controles de governança do bucket S3."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from src.config.settings import settings


def _consultar(cliente, operacao: str, **kwargs):
    """Executa uma consulta AWS e devolve resultado ou código do erro."""

    try:
        return getattr(cliente, operacao)(**kwargs), None
    except ClientError as erro:
        codigo = erro.response.get("Error", {}).get("Code", "ClientError")
        if codigo in {"ExpiredToken", "InvalidToken", "InvalidClientTokenId"}:
            raise
        return None, codigo


def auditar_bucket(bucket: str, regiao: str) -> dict:
    """Verifica quatro controles sem realizar mudanças no bucket."""

    s3 = boto3.client("s3", region_name=regiao)
    criptografia, erro_criptografia = _consultar(
        s3, "get_bucket_encryption", Bucket=bucket
    )
    acesso_publico, erro_acesso = _consultar(
        s3, "get_public_access_block", Bucket=bucket
    )
    versionamento, erro_versionamento = _consultar(
        s3, "get_bucket_versioning", Bucket=bucket
    )
    lifecycle, erro_lifecycle = _consultar(
        s3, "get_bucket_lifecycle_configuration", Bucket=bucket
    )
    
    bloqueios = (acesso_publico or {}).get("PublicAccessBlockConfiguration", {})
    acesso_bloqueado = bool(bloqueios) and all(bloqueios.values())
    versao = (versionamento or {}).get("Status", "Disabled")

    # lifecycle é None se não houver configuração, ou dicionário com chave "Rules" se houver
    controles = [
        {
            "controle": "criptografia_em_repouso",
            "status": "CONFORME" if criptografia else "ATENCAO",
            "detalhe": erro_criptografia or "Configuração encontrada",
        },
        {
            "controle": "bloqueio_acesso_publico",
            "status": "CONFORME" if acesso_bloqueado else "ATENCAO",
            "detalhe": erro_acesso or f"Todos os bloqueios ativos: {acesso_bloqueado}",
        },
        {
            "controle": "versionamento",
            "status": "CONFORME" if versao == "Enabled" else "INFORMATIVO",
            "detalhe": erro_versionamento or versao,
        },
        {
            "controle": "lifecycle_finops",
            "status": "CONFORME" if lifecycle else "ATENCAO",
            "detalhe": erro_lifecycle
            or f"{len(lifecycle.get('Rules', []))} regra(s) encontrada(s)",
        },
    ]
    return {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "bucket": bucket,
        "regiao": regiao,
        "resultado": controles,
    }

# Função principal que processa argumentos de linha de comando para gerar relatórios de auditoria de governança do S3
def main() -> None:
    parser = argparse.ArgumentParser(description="Auditoria de governança do S3")
    parser.add_argument("--bucket", default=settings.AWS_BUCKET)
    parser.add_argument("--regiao", default=settings.AWS_REGION or "us-east-1")
    args = parser.parse_args()
    if not args.bucket:
        parser.error("AWS_BUCKET não configurado no .env")

    try:
        relatorio = auditar_bucket(args.bucket, args.regiao)
    except ClientError as erro:
        codigo = erro.response.get("Error", {}).get("Code", "ClientError")
        print(f"ERRO: não foi possível auditar o bucket ({codigo}).")
        raise SystemExit(1) from None
    except NoCredentialsError:
        print("ERRO: credenciais AWS não encontradas. Atualize o Learner Lab.")
        raise SystemExit(1) from None
    destino = Path("reports/governance/auditoria-s3.json")
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(relatorio, indent=2), encoding="utf-8")
    for item in relatorio["resultado"]:
        print(f"[{item['status']}] {item['controle']}: {item['detalhe']}")
    print(f"Relatório: {destino}")


if __name__ == "__main__":
    main()
