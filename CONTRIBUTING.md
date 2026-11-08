# Como contribuir

Contribuições são bem-vindas. A forma mais simples é abrir uma issue com um dos formulários
(*Informar um radar* ou *Algo errado*): o mantenedor verifica o relato e inclui o ponto. Para editar os
dados diretamente, siga este guia. O método completo está em [docs/methodology.md](docs/methodology.md).

## Regras

- Só equipamentos **fixos** em via pública: radar fixo, lombada eletrônica ou fiscalização de avanço de
  sinal. Blitz, barreira policial e radar móvel não entram.
- Sem dados pessoais: fotos sem placas nem rostos, e nenhum trajeto de GPS.
- Só pontos verificados. Se não tem certeza da posição ou do sentido, use o formulário
  *Informar um radar* em vez de editar o CSV.
- Coordenadas não podem ser copiadas de mapas ou imagens proprietários (Google Maps, Street View e
  similares): a licença deles é incompatível com a ODbL.

## Editar `data/radars.csv`

Só o CSV é editado à mão; o GeoJSON é gerado (veja "Conferir antes de enviar"). As colunas estão no
[README](README.md#formato-dos-dados).

1. **Ponto novo:** o `id` é o próximo número depois do maior existente, contando também os de
   `data/retired.txt` (se o maior é `mao-0007`, use `mao-0008`). Mantenha as linhas em ordem de `id`.
   Um ponto por sentido: um equipamento que fiscaliza os dois sentidos ocupa duas linhas, com `heading`
   opostos.
2. **Correção:** altere a linha e atualize `checked` para a data (AAAA-MM-DD) em que você verificou o
   ponto.
3. **Remoção:** apague a linha e acrescente o `id` em `data/retired.txt`, no formato
   `mao-0008,2026-11-04,motivo`. Um id removido nunca volta ao CSV.
4. Escreva `label` no estilo `Via · Bairro`, sem vírgulas nem aspas. Em `source`, use `community` para
   o que vem da sua própria observação.

## Conferir antes de enviar

Com Python 3.12 (só biblioteca padrão; `pytest` para os testes):

```
python tools/radars.py geojson
python tools/radars.py validate
python -m pytest -q
```

`geojson` refaz `data/radars.geojson`, que vai no mesmo commit. `validate` aplica as regras dos dados e
falha enquanto o GeoJSON estiver desatualizado, por isso vem depois. A integração contínua repete essa
verificação e também compara os ids com a branch `main`.

## Mapa de revisão

Com o repositório clonado, `python tools/radars.py place` posiciona os candidatos e abre o mapa de
revisão no navegador. Para cada candidato: arraste o marcador para a pista do sentido fiscalizado,
confira tipo, sentido, limite e rótulo, e confirme. O navegador salva `placed.json` (em Downloads), que
entra no CSV com:

```
python tools/radars.py place --apply caminho/para/placed.json
```

Origens dos candidatos (`--from`):

| Opção | Candidatos |
|-------|------------|
| `immu` (padrão) | Página do IMMU, Levantamentos Técnicos e anúncios transcritos em [`tools/lists/`](tools/lists/README.md) |
| `osm` | Nós `highway=speed_camera` do OpenStreetMap |
| `file --file itens.json` | Uma lista de itens em JSON |
| `marks --repo dono/nome` | Marcações feitas no carro com o CarDeck, guardadas como issues num repositório **privado** (nunca neste). Depois de aplicadas, `python tools/radars.py marks-close` fecha essas issues. O token vem de `GH_TOKEN`, `GITHUB_TOKEN` ou `gh auth token`. |
| `laps --file atividade.json` | Marcações feitas com o botão Lap de um relógio GNSS: cada volta, menos a última (que termina no Stop), vira um candidato. A atividade deve ser privada e o arquivo nunca entra no repositório. |

Candidatos só existem no mapa de revisão e em `placed.json` (ignorado pelo git); só o que uma pessoa
confirma entra no CSV.

## Revisão

O mantenedor revisa e faz o merge; a integração contínua precisa passar. Se dois pull requests usarem o
mesmo `id`, o segundo falha depois do merge do primeiro e é refeito com o próximo número.

---

## English

Contributions are welcome. The easiest way is an issue form (*Informar um radar* to report a device,
*Algo errado* to correct one): the maintainer verifies the report and adds the point. The full method is
in [docs/methodology.md](docs/methodology.md#methodology).

- **Ground rules:** fixed devices on public roads only (no police checkpoints or mobile radars); no
  personal data (no plates, faces or GPS tracks); verified points only; never copy coordinates from
  proprietary maps or imagery (Google Maps, Street View and similar), whose licences are incompatible
  with ODbL.
- **New row:** the id is the next number after the highest in `data/radars.csv` and `data/retired.txt`
  together; keep rows sorted by id; one row per direction; `source` is `community` for your own
  observation.
- **Fix a row:** change it and set `checked` to the date you verified it.
- **Remove a row:** delete it and add `id,date,reason` to `data/retired.txt`; retired ids never return.
- **Before sending:** `python tools/radars.py geojson` (commit the regenerated GeoJSON and `docs/map.svg`), then
  `python tools/radars.py validate` (it fails while either is stale), then `python -m pytest -q`.
- **Review map:** `python tools/radars.py place` places the candidates and opens the review map; drag
  each onto the carriageway of the enforced direction, check it and confirm it; then
  `place --apply path/to/placed.json` merges the confirmed points into the CSV. `--from` picks the
  candidates: `immu` (default), `osm`, `file`, `marks` (CarDeck marks kept as issues in a **private**
  repo; `marks-close` closes them once applied) or `laps` (Lap presses of a GNSS watch; every lap but the
  last, which ends at Stop; keep the activity private and never commit its file).
- **Review:** CI must pass; the maintainer reviews and merges.
