# Dicionário de Dados

**Projeto:** Pipeline Híbrido para Análise da Alfabetização no Brasil (Tech Challenge — Fase 2)
**Escopo deste documento:** camada **Bronze** (dados extraídos da Base dos Dados / INEP,
sem transformação). As tabelas de **Silver** e **Gold** ainda estão em construção pelo
grupo — quando existirem, este documento será estendido com as colunas derivadas
(ex: `sigla_uf`, `regiao`, `fato_indicador_municipio`).

> **Fonte oficial:** [Indicador Criança Alfabetizada — Base dos Dados](https://basedosdados.org/dataset/073a39d4-89cf-4068-b1e8-34ed0d9c0b72)
> Tabela `dicionario` (extraída junto às demais, 27 registros) é a fonte primária e
> oficial dos significados de código — este documento organiza e complementa o que
> ela traz, mas em caso de divergência **a tabela `dicionario` prevalece**.

## Legenda de classificação de dado (LGPD)

| Classificação | Significado |
|---|---|
| 🟢 Público | Dado agregado/estatístico, sem risco de identificação individual |
| 🟡 Pseudonimizado | Identificador que não é PII direto (nome/CPF), mas não deve ser exposto além da Bronze sem necessidade |
| 🔴 Sensível | Dado que, combinado a outros, poderia identificar uma criança — tratar com cautela extra |

---

## Tabela: `municipio`

**Origem:** `basedosdados.br_inep_avaliacao_alfabetizacao.municipio`
**Caminho na Bronze:** `s3://fiap-postech-challenge-fase2/bronze/municipios/`
**Granularidade:** 1 linha por município + ano + série + rede

Indicador de alfabetização agregado por município (**não é uma dimensão de nome de
cidade** — só existe o código IBGE, sem nome do município nesta tabela).

| Coluna | Tipo | Descrição | Classificação |
|---|---|---|---|
| `ano` | INT | Ano de referência da medição | 🟢 Público |
| `id_municipio` | STRING (7 dígitos) | Código IBGE do município | 🟢 Público |
| `serie` | STRING | Série/ano escolar avaliado (2º ano do Ensino Fundamental, conforme o recorte do Indicador Criança Alfabetizada) | 🟢 Público |
| `rede` | STRING | Rede de ensino (`Municipal`, `Estadual`, `Federal`, `Privada` ou agregado — ⚠️ confirmar valores exatos em `dicionario.parquet`) | 🟢 Público |
| `taxa_alfabetizacao` | FLOAT (0–100) | Percentual de estudantes que atingiram o ponto de corte de 743 pontos na escala Saeb | 🟢 Público |
| `media_portugues` | FLOAT | Proficiência média em Língua Portuguesa no município/ano/rede | 🟢 Público |
| `proporcao_aluno_nivel_0` a `proporcao_aluno_nivel_8` | FLOAT (0–100) | Distribuição percentual dos alunos pelos 9 níveis de proficiência da escala Saeb | 🟢 Público |

---

## Tabela: `alunos`

**Origem:** `basedosdados.br_inep_avaliacao_alfabetizacao.alunos`
**Caminho na Bronze:** `s3://fiap-postech-challenge-fase2/bronze/alunos/`
**Granularidade:** 1 linha por aluno avaliado

Microdados individuais da avaliação — é a tabela com maior sensibilidade do projeto.

| Coluna | Tipo | Descrição | Classificação |
|---|---|---|---|
| `ano` | INT | Ano de referência da avaliação | 🟢 Público |
| `id_municipio` | STRING (7 dígitos) | Código IBGE do município do aluno | 🟢 Público |
| `id_escola` | STRING | Código INEP da escola | 🟡 Pseudonimizado |
| `id_aluno` | STRING | Identificador sintético do aluno na avaliação (não é CPF/nome) | 🟡 Pseudonimizado |
| `caderno` | STRING/INT | Identificador do caderno de prova aplicado (controle de rotação de itens do teste) | 🟢 Público |
| `serie` | STRING | Série/ano escolar do aluno | 🟢 Público |
| `rede` | STRING | Rede de ensino da escola do aluno | 🟢 Público |
| `presenca` | STRING/BOOL | Indica se o aluno esteve presente no dia da prova (⚠️ confirmar codificação exata) | 🔴 Sensível |
| `preenchimento_caderno` | STRING/BOOL | Indica se o caderno de respostas foi preenchido de forma válida | 🟢 Público |
| `alfabetizado` | STRING/BOOL (`0`/`1`) | Flag calculada: `1` se `proficiencia >= 743`, `0` caso contrário | 🔴 Sensível |
| `proficiencia` | FLOAT | Pontuação do aluno na escala Saeb (referência: corte de alfabetização = 743) | 🔴 Sensível |
| `peso_aluno` | FLOAT | Peso amostral usado para estimativas agregadas (não identifica o aluno) | 🟢 Público |

**Nota de governança (LGPD):** apesar de não conter nome, CPF ou outro identificador
direto, esta tabela é tratada como sensível por permitir, em combinação com
`id_escola` + `ano` + `serie`, uma reidentificação em municípios pequenos com poucas
turmas. Por isso, **esta tabela não deve ultrapassar a camada Bronze** — a Silver e a
Gold devem trabalhar apenas com agregações (médias, percentuais, contagens),
nunca com o registro individual do aluno.

---

## Tabela: `meta_alfabetizacao_municipio`

**Origem:** `basedosdados.br_inep_avaliacao_alfabetizacao.meta_alfabetizacao_municipio`
**Caminho na Bronze:** `s3://fiap-postech-challenge-fase2/bronze/metas_municipios/`
**Granularidade:** 1 linha por município + ano + rede

| Coluna | Tipo | Descrição | Classificação |
|---|---|---|---|
| `ano` | INT | Ano de referência | 🟢 Público |
| `id_municipio` | STRING (7 dígitos) | Código IBGE do município | 🟢 Público |
| `rede` | STRING | Rede de ensino | 🟢 Público |
| `taxa_alfabetizacao` | FLOAT (0–100) | Taxa de alfabetização observada no ano de referência | 🟢 Público |
| `meta_alfabetizacao_2024` … `meta_alfabetizacao_2030` | FLOAT (0–100) | Meta pactuada de percentual de alfabetização para cada ano, dentro do Compromisso Nacional Criança Alfabetizada (meta final: 100% até 2030) | 🟢 Público |
| `nivel_alfabetizacao` | STRING | Classificação do nível de alfabetização atingido pelo município/rede (⚠️ confirmar categorias em `dicionario.parquet`) | 🟢 Público |
| `percentual_participacao` | FLOAT (0–100) | Percentual de adesão/participação do município na avaliação | 🟢 Público |

---

## Outras tabelas extraídas (Bronze)

| Tabela | Caminho na Bronze | Descrição resumida |
|---|---|---|
| `uf` | `bronze/alfabetizacao/` | Indicador agregado por Unidade Federativa |
| `meta_alfabetizacao_brasil` | `bronze/metas_brasil/` | Meta nacional agregada (3 registros — provavelmente por rede) |
| `meta_alfabetizacao_uf` | `bronze/metas_uf/` | Meta por UF |
| `dicionario` | `bronze/dicionario/` | Metadados oficiais da Base dos Dados — fonte primária deste documento |

---

## Pendências deste dicionário

- [ ] Confirmar os valores exatos de `rede`, `serie`, `alfabetizado` e `presenca`
      lendo o conteúdo de `dicionario.parquet` (comando abaixo)
- [ ] Estender este documento quando as tabelas de Silver e Gold existirem
      (`fato_indicador_municipio`, `dim_territorio`, `meta_vs_resultado`, conforme
      citado em `qualidade_silver.py`)

Para conferir os valores reais e completar as pendências acima:

```bash
python -c "import pandas as pd; df = pd.read_parquet('data/bronze/dicionario/dicionario.parquet'); print(df.to_string())"
```