# Governança e FinOps

## Escopo entregue

Esta frente complementa a Governança já existente no projeto — dicionário de dados, linhagem e regras de qualidade Q1–Q8 — sem substituir essas implementações.

| Pilar           | Implementação                                           | Evidência                              |
| --------------- | ------------------------------------------------------- | -------------------------------------- |
| Data Quality    | Great Expectations na Bronze e regras Q1–Q8 na Silver   | `quality/` e `quality/reports/`        |
| Observabilidade | Logs estruturados em JSON e manifesto por execução      | `reports/governance/execucao-*.json`   |
| Segurança       | Auditoria somente leitura dos controles do S3           | `reports/governance/auditoria-s3.json` |
| Rastreabilidade | ID, horários, duração, volume, status e erro            | Manifesto JSON da execução             |
| FinOps          | Inventário real de objetos, classes e volume armazenado | `reports/finops/relatorio-finops.json` |
| Otimização      | Parquet/Snappy, particionamento e lifecycle             | `src/finops/analise_s3.py`             |

## Execução no PowerShell

Com a `.venv` ativa e as credenciais temporárias do AWS Academy válidas, execute:

```powershell
python -m src.governance.auditoria_s3
python -m quality.run_quality_checks
python -m src.finops.analise_s3 relatorio
python -m src.finops.analise_s3 verificar
```

Esses comandos consultam e validam o ambiente sem alterar os objetos armazenados no bucket. Durante a execução, podem ser criados relatórios locais nas pastas `quality/reports/`, `reports/governance/` e `reports/finops/`.

## Aplicação do lifecycle

A aplicação do lifecycle altera a configuração do bucket e, por isso, exige uma confirmação explícita:

```powershell
python -m src.finops.analise_s3 aplicar-lifecycle --aplicar
```

Antes de aplicar, é possível consultar as regras existentes:

```powershell
python -m src.finops.analise_s3 verificar
```

O código consulta as regras atuais, preserva configurações criadas por outras pessoas e atualiza somente as regras FinOps identificadas pelo prefixo `finops-`.

## Configuração do ambiente

O bucket e a região são obtidos do arquivo `.env`. Nenhum nome de bucket fica fixado no código.

Exemplo para um ambiente de desenvolvimento:

```ini
AWS_REGION=us-east-1
AWS_BUCKET=nome-do-bucket-de-desenvolvimento

FINOPS_PREFIX=bronze/
FINOPS_TRANSICAO_IA_DIAS=30
FINOPS_TRANSICAO_GLACIER_DIAS=90
```

Para executar no ambiente compartilhado, é necessário alterar somente `AWS_BUCKET`, desde que a credencial utilizada tenha permissão para consultar e modificar o bucket informado.

As credenciais do AWS Academy não devem ser colocadas no `.env`. Elas devem permanecer no arquivo local de credenciais da AWS CLI.

## Estratégia de otimização

O lifecycle implementa as seguintes regras para a camada Bronze:

| Regra                                    | Configuração                             |
| ---------------------------------------- | ---------------------------------------- |
| Transição para Standard-IA               | Objetos maiores que 128 KiB após 30 dias |
| Transição para Glacier Instant Retrieval | Objetos maiores que 128 KiB após 90 dias |
| Upload multipart incompleto              | Cancelamento após 7 dias                 |
| Regras preexistentes                     | Preservadas durante a atualização        |
| Regras FinOps duplicadas                 | Substituídas pela versão atual           |

Arquivos menores que 128 KiB permanecem na classe Standard porque, em volumes pequenos, as tarifas de transição e os valores mínimos cobrados podem superar a economia de armazenamento.

## Evidências da execução

A implementação foi validada em um bucket de desenvolvimento e apresentou:

```text
8 testes automatizados aprovados
7 objetos inventariados
628.415 bytes identificados na camada Bronze
2 regras de lifecycle ativas
```

A auditoria do bucket apresentou:

```text
[CONFORME] criptografia_em_repouso
[CONFORME] bloqueio_acesso_publico
[INFORMATIVO] versionamento: Disabled
[CONFORME] lifecycle_finops: 2 regras encontradas
```

O versionamento desativado foi classificado como informativo, e não como falha, pois sua ativação aumenta o volume armazenado e deve ser uma decisão conjunta de Governança e FinOps.

## Limites e decisões

* A estimativa de armazenamento é comparativa e não representa uma fatura oficial.
* O custo real deve ser confirmado no AWS Cost Explorer ou AWS Pricing Calculator.
* A estimativa não inclui requisições, recuperação de arquivos, permanência mínima, Athena, Glue, BigQuery ou streaming.
* O Glacier pode gerar custo de recuperação e exigir permanência mínima.
* A política de lifecycle não é aplicada automaticamente.
* O relatório não armazena credenciais, tokens ou conteúdo dos registros.
* As credenciais do AWS Academy são temporárias e nunca devem ser publicadas no Git.
