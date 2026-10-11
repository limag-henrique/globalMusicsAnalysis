# Avaliação automatizada e derivados locais — 10/10/2026

O usuário definiu que não haverá avaliação humana e confirmou limpeza, extração,
testes nas interfaces públicas e derivados versionados, sem reanálise semântica
paga nesta etapa. Confiança é critério operacional, não acurácia calibrada.

Saída final: `data/derived/research_quality/automated-quality-20261010-final/`.
Relatório: `report.md`. Tratamento: `lyrics-text-quality-v2`.
Snapshot: 12:02:37 BRT. Foram verificados 159.111 documentos, produzidos 26.541
derivados corrigidos e removidos 26.539 rodapés. Nenhum resíduo reconhecido restou
nos derivados. 78.123 resultados passam pelo filtro operacional (confiança >=0,80,
ajustável). 193 testes/Ruff/mypy passaram; custo adicional de API R$0.

Reprodução em diretório novo:

```powershell
.\.venv\Scripts\python.exe scripts/correct_lyrics_quality.py --output-dir data/derived/research_quality/NOVO_DIRETORIO
```

A CLI exige destino inexistente, PostgreSQL 16 em 127.0.0.1:56433 e transação
somente leitura. `--input-jsonl` permite fixtures locais sem banco. Manter letras
apenas nos artefatos locais autorizados; não fazer upload dos derivados.

Originais, snapshots, quarentena, checkpoint e entradas dos jobs vivos não foram
alterados. Resultados antigos não classificam textos com hash novo. Divergências,
possíveis fragmentos e identidades não verificadas ficam registrados; nenhum
trecho ou escore semântico foi inventado. A elegibilidade científica estrita e a
ausência de ligação confirmada aos rankings permanecem explícitas. O controlador
exclusivo continua com a política BRL vigente.

Os diretórios intermediários permanecem como evidências de diagnóstico; utilizar
a pasta final. `artifact-validation.json` e `reproducibility/` conferem hashes
dos derivados, resultados selecionados, manifesto e implementação usada.
