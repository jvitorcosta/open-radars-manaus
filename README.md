# open-radars-manaus

Radares, lombadas eletrônicas e câmeras de avanço de sinal em Manaus: dados abertos.

## O que é

Uma lista aberta e revisada à mão dos pontos fixos de fiscalização de trânsito em Manaus (AM), com
posição exata, sentido fiscalizado, limite de velocidade e a data da última conferência. São três tipos:

- `speed`: radar de velocidade fixo (um radar que também confere avanço de sinal conta como `speed`);
- `bump`: lombada eletrônica;
- `redlight`: câmera de avanço de sinal.

Só entram pontos **fixos** e públicos. A lista existe para quem quiser usar os dados (um mapa, um
aplicativo, um estudo); como usar fica por conta de cada um.

## Contribuições são bem-vindas

Você pode ajudar de duas formas, e não precisa saber git para a primeira:

1. **Abra uma issue** com um dos formulários: [Informar um radar](https://github.com/jvitorcosta/open-radars-manaus/issues/new?template=informar-radar.yml)
   para um ponto novo, ou [Algo errado](https://github.com/jvitorcosta/open-radars-manaus/issues/new?template=algo-errado.yml) para corrigir um
   ponto que já está na lista (mudou de lugar, não existe mais, limite ou sentido errado).
2. **Envie um Pull Request** editando `data/radars.csv`. O passo a passo está em
   [CONTRIBUTING.md](CONTRIBUTING.md).

Toda contribuição é conferida automaticamente e revisada pelo dono do repositório, que é quem faz o merge.

## Baixar a versão mais recente

- CSV: https://github.com/jvitorcosta/open-radars-manaus/releases/latest/download/radars.csv
- GeoJSON: https://github.com/jvitorcosta/open-radars-manaus/releases/latest/download/radars.geojson

A primeira versão ainda não foi publicada; os links funcionam a partir dela.

As versões usam o calendário (`AAAA.MM.N`, por exemplo `2026.11.0`), então dá para fixar uma versão.
O que mudou em cada uma está no [CHANGELOG.md](CHANGELOG.md). O arquivo `data/radars.csv` é a fonte
da verdade; `data/radars.geojson` é gerado a partir dele e nunca é editado à mão.

## Colunas de `data/radars.csv`

CSV simples, UTF-8, quebra de linha LF, sem aspas, linhas em ordem de `id`.

| Coluna | Significado |
|--------|-------------|
| `id` | `mao-NNNN`, quatro dígitos, em ordem, nunca reutilizado |
| `kind` | `speed`, `bump` (lombada eletrônica) ou `redlight` (avanço de sinal) |
| `lat`, `lon` | WGS84, 6 casas decimais, na pista que o ponto fiscaliza |
| `heading` | 0 a 359, sentido de deslocamento fiscalizado (graus a partir do norte). Obrigatório |
| `limit` | km/h, 1 a 199; vazio quando não se sabe; sempre vazio em `redlight` |
| `label` | descrição curta no estilo `Rua · Bairro`, por exemplo `Av. Prof. Nilton Lins 900 · Flores`. Sem vírgulas nem aspas |
| `source` | de onde o ponto veio primeiro: `immu`, `osm`, `survey`, `car` ou `community` |
| `checked` | data (AAAA-MM-DD) em que uma pessoa confirmou o ponto no mapa de revisão ou na rua. Obrigatório |

Um ponto por sentido: uma câmera nos dois sentidos ocupa duas linhas, com `heading` opostos.

## Regras

- Só pontos **fixos** e públicos. Nada de blitz, barreiras policiais, radares móveis ou qualquer
  coisa que se mova. Pedidos assim são fechados.
- Sem dados pessoais: nada de placas ou rostos em fotos, e nunca trajetos brutos de GPS de ninguém.
- Só entra o que foi confirmado. Palpite não vai para o CSV.
- Nada aqui detecta sinal de radar: o repositório só lista onde fica a infraestrutura.

## Licenças

- **Dados** (`data/`): [ODbL 1.0](data/LICENSE). Parte dos pontos vem do OpenStreetMap:
  © OpenStreetMap contributors.
- **Código** (`tools/` e CI): [MIT](LICENSE).

## Nota legal

Este repositório não contém nem incentiva detectores de radar, proibidos pelo CTB (art. 230, III);
só lista onde fica a infraestrutura pública de fiscalização, e não capta nem emite sinal algum.
Isto é uma nota informativa, não é aconselhamento jurídico.

---

## English

### What it is

An open, hand-reviewed list of the fixed traffic-enforcement points in Manaus, Brazil, with exact
position, enforced direction of travel, speed limit and the date it was last confirmed. Three kinds:
`speed` (fixed speed camera), `bump` (electronic speed bump, *lombada eletrônica*) and `redlight`
(red-light camera). Fixed public points only. How you use the data is up to you.

### Contributions are welcome

Two ways to help; the first needs no git:

1. **Open an issue** with a form: *Informar um radar* (report a camera) or *Algo errado* (something's
   wrong with a listed point).
2. **Send a pull request** editing `data/radars.csv`; see [CONTRIBUTING.md](CONTRIBUTING.md).

Every change is checked by CI and reviewed by the owner, who merges.

### Download

- CSV: https://github.com/jvitorcosta/open-radars-manaus/releases/latest/download/radars.csv
- GeoJSON: https://github.com/jvitorcosta/open-radars-manaus/releases/latest/download/radars.geojson

No release yet; the links work once the first one is out.

Releases use calendar versions (`YYYY.MM.N`), so you can pin one. `data/radars.csv` is the source of
truth; `data/radars.geojson` is generated from it.

### Columns

`id,kind,lat,lon,heading,limit,label,source,checked`: see the Portuguese table above. In short: `id`
is `mao-NNNN` and never reused; `kind` is `speed`, `bump` or `redlight`; `heading` (0..359) is the
enforced direction and is required; `limit` is km/h or empty (always empty for `redlight`); `source`
is `immu`, `osm`, `survey`, `car` or `community`; `checked` is the date a human confirmed the point.
One row per direction.

### Ground rules

- Fixed public points only: no police checkpoints, blitz or mobile radars.
- No personal data: no plates or faces in photos, never raw GPS traces.
- Confirmed points only; guesses stay out of the CSV.

### Licences

Data: ODbL 1.0, © OpenStreetMap contributors for the parts that come from OpenStreetMap. Code: MIT.

### Legal note

This repository lists positions of public infrastructure. It is not a radar detector: it senses and
transmits nothing. This repository neither contains nor encourages radar detectors, which Brazil's
traffic code (CTB art. 230, III) bans; it only lists where the public enforcement infrastructure
stands. This is information, not legal advice.
