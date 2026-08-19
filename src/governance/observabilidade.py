"""Registro estruturado e auditável das execuções da pipeline."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path


class FormatadorJson(logging.Formatter):
    """Transforma mensagens de log em JSON, adequado ao CloudWatch."""

    def format(self, record: logging.LogRecord) -> str:
        # Um log estruturado pode ser pesquisado por campo no CloudWatch.
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "nivel": record.levelname,
            "logger": record.name,
            "mensagem": record.getMessage(),
        }
        return json.dumps(payload, ensure_ascii=False)


def configurar_logger() -> logging.Logger:
    """Cria um único logger para evitar mensagens duplicadas."""

    logger = logging.getLogger("pipeline.alfabetizacao")
    if logger.handlers:
        return logger
    handler = logging.StreamHandler()
    handler.setFormatter(FormatadorJson())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


class MonitorExecucao:
    """Mantém manifesto com duração, volumes, status e erro da execução."""

    def __init__(self, etapa: str, diretorio: Path | str = "reports/governance"):
        self.id_execucao = str(uuid.uuid4())
        self.etapa = etapa
        self.inicio = datetime.now(timezone.utc)
        self.diretorio = Path(diretorio)
        self.tabelas: list[dict] = []
        self.logger = configurar_logger()
        self.logger.info("execucao_iniciada id=%s etapa=%s", self.id_execucao, etapa)

    def registrar_tabela(self, tabela: str, linhas: int, bytes_arquivo: int) -> None:
        """Acumula métricas de uma tabela que terminou de ser processada."""

        self.tabelas.append(
            {"tabela": tabela, "linhas": linhas, "bytes": bytes_arquivo}
        )
        self.logger.info(
            "tabela_processada id=%s tabela=%s linhas=%s bytes=%s",
            self.id_execucao,
            tabela,
            linhas,
            bytes_arquivo,
        )

    def finalizar(self, sucesso: bool, erro: str | None = None) -> Path:
        """Fecha a execução e salva sua evidência em JSON."""

        fim = datetime.now(timezone.utc)
        payload = {
            "id_execucao": self.id_execucao,
            "etapa": self.etapa,
            "status": "SUCESSO" if sucesso else "FALHA",
            "inicio_utc": self.inicio.isoformat(),
            "fim_utc": fim.isoformat(),
            "duracao_segundos": round((fim - self.inicio).total_seconds(), 3),
            "total_tabelas": len(self.tabelas),
            "total_linhas": sum(item["linhas"] for item in self.tabelas),
            "total_bytes": sum(item["bytes"] for item in self.tabelas),
            "tabelas": self.tabelas,
            "erro": erro,
        }
        self.diretorio.mkdir(parents=True, exist_ok=True)
        caminho = self.diretorio / f"execucao-{self.id_execucao}.json"
        caminho.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self.logger.log(
            logging.INFO if sucesso else logging.ERROR,
            "execucao_finalizada id=%s status=%s relatorio=%s",
            self.id_execucao,
            payload["status"],
            caminho,
        )
        return caminho
