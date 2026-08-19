# Linhagem de Dados (Data Lineage)

> ⚠️ **STATUS: RASCUNHO** — A linhagem em nível de camada (Bronze → Silver → Gold)
> está confirmada pelo código já existente (`src/ingestion/extract.py`,
> `qualidade_silver.py`). Já a linhagem em nível de **tabela** dentro da Silver
> (quais colunas de `municipio`/`alunos`/`meta_alfabetizacao_municipio` viram
> quais colunas de `fato_indicador_municipio`/`dim_territorio`/`meta_vs_resultado`)
> foi **inferida** a partir das queries do `qualidade_silver.py` — precisa ser
> confirmada com quem escreveu `src/transformation/silver.py`, que é a fonte real
> dessa transformação.

Este documento atende dois requisitos ao mesmo tempo:
- o item de governança **"Mapeamento de Linhagem"** listado como pendência pelo grupo;
- o requisito do desafio de incluir **"diagrama da pipeline"** e **"fluxo de dados"** no README.

## 1. Visão geral por camada

```mermaid
flowchart LR
    BD["Base dos Dados<br/>(BigQuery público)"] -->|extract.py<br/>batch, SELECT + LIMIT| Bronze
    BD -.->|"producer/consumer<br/>(simulado)"| Bronze

    Bronze["🥉 Bronze<br/>S3 · Parquet<br/>dado bruto"] -->|qualidade_silver.py<br/>Q1–Q8, fail-fast| Silver
    Silver["🥈 Silver<br/>Glue/Spark · tratado<br/>e integrado"] --> Gold
    Gold["🥇 Gold<br/>a definir · analítico"] --> Consumo

    Consumo["Dashboards · Modelos de ML<br/>Análises estatísticas"]

    style Bronze fill:#cd7f32,color:#fff
    style Silver fill:#c0c0c0,color:#000
    style Gold fill:#ffd700,color:#000
```

**Gate de qualidade:** a promoção de Bronze → Silver só acontece se todas as regras
**bloqueantes** (Q1, Q2, Q3, Q4, Q5, Q8) do `qualidade_silver.py` passarem — é um
mecanismo *fail-fast*: dado ruim não avança, o Job falha e alerta antes de
contaminar a Silver. Regras de severidade *alerta* (Q6, Q7) não bloqueiam, só
registram no relatório.

## 2. Linhagem em nível de tabela

```mermaid
flowchart TB
    subgraph Fonte["Fonte — basedosdados.br_inep_avaliacao_alfabetizacao"]
        F_UF[("uf")]
        F_MUN[("municipio")]
        F_ALU[("alunos")]
        F_MB[("meta_alfabetizacao_brasil")]
        F_MUF[("meta_alfabetizacao_uf")]
        F_MM[("meta_alfabetizacao_municipio")]
        F_DIC[("dicionario")]
    end

    subgraph Bronze["Bronze — S3 (bronze/*)"]
        B_UF[("uf")]
        B_MUN[("municipio")]
        B_ALU[("alunos")]
        B_MB[("meta_alfabetizacao_brasil")]
        B_MUF[("meta_alfabetizacao_uf")]
        B_MM[("meta_alfabetizacao_municipio")]
        B_DIC[("dicionario")]
    end

    subgraph Silver["Silver — Glue Catalog"]
        S_TERR[("dim_territorio")]
        S_FATO[("fato_indicador_municipio")]
        S_META[("meta_vs_resultado")]
    end

    F_UF --> B_UF
    F_MUN --> B_MUN
    F_ALU --> B_ALU
    F_MB --> B_MB
    F_MUF --> B_MUF
    F_MM --> B_MM
    F_DIC --> B_DIC

    B_UF -->|"⚠️ inferido: enriquecida com<br/>sigla_uf/regiao (Q4)"| S_TERR
    B_MUN -->|"⚠️ inferido: base da fato<br/>(id_municipio+ano+serie+rede)"| S_FATO
    B_MM -->|"⚠️ inferido: junta meta<br/>com resultado real"| S_META
    S_FATO -->|"taxa_alfabetizacao observada"| S_META

    B_ALU -.->|"consultada apenas para<br/>validação cruzada (Q5) —<br/>nunca promovida fisicamente<br/>além da Bronze (ver LGPD)"| Silver
```

## 3. Notas de rastreabilidade por regra de qualidade

Cada regra bloqueante do `qualidade_silver.py` corresponde a uma aresta específica
desta linhagem — útil pra saber, quando uma regra falha, **qual transformação**
investigar:

| Regra | Aresta afetada |
|---|---|
| Q1 — Integridade referencial | `meta_vs_resultado` → `dim_territorio` |
| Q2 — Códigos como texto | `municipio` (Bronze) → `fato_indicador_municipio` (tipo da chave) |
| Q3 — Unicidade | dentro de `fato_indicador_municipio` |
| Q4 — Vínculo territorial | `uf` (Bronze) → `dim_territorio` |
| Q5 — Ponto de corte | `alunos` (Bronze) — validação cruzada, sem promoção física |
| Q8 — Conservação de volume | `municipio` (Bronze) → `fato_indicador_municipio` (contagem) |

## 4. LGPD e limite de propagação

Conforme detalhado no `DICIONARIO.md`, a tabela `alunos` contém a granularidade
mais sensível do projeto (registro por criança). A linha pontilhada no diagrama
acima é proposital: `alunos` é **consultada** pela Silver (para a checagem Q5),
mas **não é promovida** como tabela própria além da Bronze — a Silver e a Gold só
recebem agregados (`taxa_alfabetizacao`, contagens, percentuais).

## 5. Pendências

- [ ] Confirmar com quem escreveu `src/transformation/silver.py` se a linhagem
      inferida acima (setas com ⚠️) bate com a transformação real
- [ ] Confirmar se `meta_alfabetizacao_brasil` e `meta_alfabetizacao_uf` também
      alimentam `meta_vs_resultado`, ou se ficam restritas a análises futuras da Gold
- [ ] Atualizar este documento quando as tabelas de Gold forem definidas
      (`indicador_por_municipio`, `comparacao_meta_resultado`, `evolucao_temporal`
      — nomes sugeridos com base no PDF, ainda não implementados)