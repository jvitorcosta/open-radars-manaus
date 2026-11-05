# Listas transcritas de anúncios

Cada arquivo `immu-AAAA-MM.csv` transcreve à mão um anúncio de novos equipamentos de fiscalização, com o
mês de início de operação no nome. As colunas são `kind,street,cross,district,sentido,limit,note`:

| Coluna | Conteúdo |
|--------|----------|
| `kind` | `speed`, `bump` ou `redlight`, como em `data/radars.csv` |
| `street` | via onde fica o equipamento, com a grafia publicada |
| `cross` | via transversal, quando o anúncio dá um cruzamento; vazio caso contrário |
| `district` | bairro |
| `sentido` | sentido como publicado (`Norte`, `Leste`, `Sul`, `Oeste` ou texto livre) |
| `limit` | limite em km/h quando o anúncio informa; vazio caso contrário |
| `note` | número, referência ou divergência de grafia entre fontes |

Itens já presentes em outra fonte (os pontos da Av. do Turismo, que vêm dos Levantamentos Técnicos) e
itens fora do escopo (detectores de eixo) não são transcritos. As linhas daqui são endereços, não
posições: viram candidatos no mapa de revisão (ver [docs/methodology.md](../../docs/methodology.md)).

## Fontes

| Arquivo | Início de operação | Fontes |
|---------|--------------------|--------|
| `immu-2026-02.csv` | 1º fev. 2026 | Prefeitura de Manaus, [2 jan. 2026](https://www.manaus.am.gov.br/noticia/transito/prefeitura-immu-fiscalizacaoeletronica/) e [30 jan. 2026](https://www.manaus.am.gov.br/noticia/fiscalizacao/prefeitura-immu-novosradares/); [Amazonas Atual, 2 fev. 2026](https://amazonasatual.com.br/manaus-tem-mais-34-novos-radares-de-fiscalizacao-eletronica-saiba-os-locais/) |
| `immu-2026-07.csv` | 13 jul. 2026 | [Em Tempo, 13 jul. 2026](https://emtempo.com.br/479092/amazonas/novos-radares-comecam-a-multar-em-manaus-veja-os-17-locais-de-fiscalizacao/); [Fato Amazônico, 13 jul. 2026](https://fatoamazonico.com.br/immu-instala-17-novos-radares-em-vias-de-manaus-confira-os-locais-de-fiscalizacao/) |

Um anúncio novo vira um arquivo novo aqui, com uma linha nesta tabela, e o nome do arquivo entra em
`LISTS` em `tools/sources.py`.

---

**English.** Each `immu-YYYY-MM.csv` is a hand transcription of one announcement of new enforcement
devices, named after the month they started operating. Columns as in the table above; spelling is kept
as published. Items already in another source and out-of-scope items (axle detectors) are left out. The
rows are addresses, not positions: they become candidates on the review map. The table above lists each
file's sources; a new announcement gets a new file, a row there, and an entry in `LISTS` in
`tools/sources.py`.
