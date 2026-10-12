# Pacotes públicos para validação externa

Os pacotes consolidam os materiais originais da pesquisa em um snapshot
reproduzível. Não houve publicação on-line, commit, push ou troca de branch.

| Destino | Pasta pronta para publicação | Arquivo para transferência |
|---|---|---|
| GitHub | `github/` | `packages/github-research-release-v1.zip` |
| Kaggle | `kaggle/` | `packages/kaggle-research-release-v1.zip` |

Incluem o artigo congelado de sete páginas e sete figuras, atlas de 68 mercados,
classificações por gravação, códigos categóricos, vínculos derivados com os charts,
painéis país/ano, séries de busca, contexto social, oito sensibilidades globais,
30 modelos, notebook, métodos, taxonomia, fontes e hashes SHA-256.

**Licenças escolhidas:** CC BY 4.0 para contribuições originais em dados e
documentos; MIT para código original. Fontes de terceiros conservam seus termos
e atribuições. Letras completas, dumps brutos de provedores, credenciais, banco
e backups não fazem parte destes arquivos públicos.

## Validação

Ambos os pacotes passaram pela verificação de integridade, unicidade e
denominadores e pela reprodução offline usando somente os arquivos públicos.
Foram reproduzidos 68 mercados, 386 pares país/ano, 26 dimensões, 1.690 células
de cruzamentos sociais, oito painéis de sensibilidade e 30 modelos de buscas.
Os quatro gráficos adicionais de tendências também foram regenerados com o
código portátil. O PDF e os gráficos foram revisados visualmente.

`VALIDATION_REPORT.json`, `RELEASE_MANIFEST.json` e `SHA256SUMS.txt` em cada
pacote registram os resultados e a integridade. O notebook é
`notebooks/external_validation.ipynb`.

## Envio

- GitHub: publicar a pasta curada `github/`, em vez de enviar todo o repositório
  operacional, que contém materiais privados de pesquisa.
- Kaggle: preencher o usuário/organização em `kaggle/dataset-metadata.json`
  antes do envio. O campo atual é um marcador, não uma conta selecionada.

## Limpeza

A exclusão solicitada foi bloqueada pela revisão automática de política, inclusive
para um instalador temporário com caminho absoluto conferido. **Nenhum arquivo
foi apagado.** Os candidatos descartáveis estão em `CLEANUP_REVIEW.csv` e a
situação está em `CLEANUP_REPORT.json`. Eles estão fora dos pacotes públicos.

Históricos de auditoria, versões científicas anteriores, respostas originais e
backups foram preservados porque contêm evidência única, não lixo comprovado.
O pacote público reúne a versão relevante para revisão sem destruir essa evidência.

Novas análises em desenvolvimento no workspace não alteram estes ZIPs congelados.
Uma versão futura pode ser preparada com o construtor de publicação e verificada
novamente antes da divulgação.
