from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]

load_dotenv(BASE_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    GCP_PROJECT_ID: str = os.getenv("GCP_PROJECT_ID", "")
    GCP_DATASET: str = os.getenv("GCP_DATASET", "")

    AWS_REGION: str = os.getenv("AWS_REGION", "")
    AWS_BUCKET: str = os.getenv("AWS_BUCKET", "")

    PIPELINE_ENV: str = os.getenv("PIPELINE_ENV", "dev")

    FINOPS_PREFIX: str = os.getenv("FINOPS_PREFIX", "bronze/")

    FINOPS_TRANSICAO_IA_DIAS: int = int(
        os.getenv("FINOPS_TRANSICAO_IA_DIAS", "30")
    )

    FINOPS_TRANSICAO_GLACIER_DIAS: int = int(
        os.getenv("FINOPS_TRANSICAO_GLACIER_DIAS", "90")
    )


settings = Settings()