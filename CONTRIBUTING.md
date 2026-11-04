# Como contribuir

Contribuições são bem-vindas. A forma mais simples é abrir uma issue com um dos formulários
(*Informar um radar* ou *Algo errado*); o dono do repositório confere e adiciona a linha. Se preferir
mexer no arquivo, siga este guia.

## Regras

- Só pontos **fixos** e públicos: radar, lombada eletrônica ou câmera de avanço de sinal. Nada de
  blitz, barreira policial ou radar móvel.
- Sem dados pessoais: fotos sem placas nem rostos, e nunca trajetos brutos de GPS.
- Só pontos confirmados. Se não tem certeza da posição ou do sentido, use o formulário
  *Informar um radar* em vez de editar o CSV.

## Adicionar ou corrigir uma linha à mão

Edite só o CSV à mão e commite o GeoJSON regenerado (veja "Conferir antes de enviar"). As colunas estão no [README](README.md).

1. **Novo ponto:** o `id` é o próximo número depois do maior que existe, contando também os de
   `data/retired.txt` (por exemplo, se o maior é `mao-0007`, use `mao-0008`). Mantenha as linhas em
   ordem de `id`. Um ponto por sentido: uma câmera nos dois sentidos ocupa duas linhas, com `heading` opostos.
2. **Corrigir:** mude a linha e atualize `checked` para a data (AAAA-MM-DD) em que você confirmou.
3. **Remover:** apague a linha e acrescente o `id` em `data/retired.txt`, no formato
   `mao-0008,2026-11-04,motivo`. Um id removido nunca volta ao CSV.
4. Use o estilo `Rua · Bairro` em `label`, sem vírgulas nem aspas, e `source` com um destes valores:
   `immu`, `osm`, `survey`, `car`, `community` (use `community` para o que vem de você).

## Conferir antes de enviar

Com Python 3.12 (só biblioteca padrão, e `pytest` para os testes):

```
python tools/radars.py geojson
python tools/radars.py validate
python -m pytest -q
```

`geojson` refaz `data/radars.geojson`, que deve ir no mesmo commit; `validate` aplica as regras dos
dados e falha enquanto o GeoJSON está desatualizado, por isso vem depois. A CI roda a mesma verificação e também compara os ids com a branch `main`.

## Mapa de revisão (quem tem o repositório)

`python tools/radars.py place` abre um mapa local onde cada ponto é arrastado para a sua pista e
confirmado; o resultado vai para `placed.json`, aplicado com
`python tools/radars.py place --apply caminho/para/placed.json` (o navegador salva em Downloads).
Os pontos vêm do IMMU: a página dele e os pontos anunciados à imprensa, transcritos em `tools/lists/`
(um anúncio novo vira um CSV novo ali). Para os nós do OpenStreetMap use `place --from osm`. Um ponto num
cruzamento ("Avenida A/Rua B") já aparece onde as duas ruas se encontram, antes da faixa, na pista do sentido.
Palpites automáticos só existem nesse mapa; só o que uma pessoa confirma entra no CSV.

## Revisão

O dono do repositório revisa e faz o merge; ninguém mais faz merge em `main`, e a CI precisa passar.
Se dois PRs usarem o mesmo `id`, o segundo falha depois do primeiro e é refeito com o próximo número.

---

## English

Contributions are welcome. The easiest way is an issue form (*Informar um radar* / *Algo errado*);
the owner checks it and adds the row. To edit the file yourself (edit only the CSV by hand and commit the regenerated GeoJSON):

- **Ground rules:** fixed public points only (no checkpoints, blitz or mobile radars); no personal
  data (no plates or faces, no raw GPS traces); confirmed points only.
- **New row:** the id is the next number after the highest in `data/radars.csv` and `data/retired.txt`
  together; keep rows sorted by id; one row per direction (a camera covering both directions takes two rows); `source` is `community` for your own report.
- **Fix a row:** change it and set `checked` to the date you confirmed it.
- **Remove a row:** delete it and add `id,date,reason` to `data/retired.txt`; retired ids never return.
- **Before sending:** `python tools/radars.py geojson` (commit the regenerated GeoJSON), then
  `python tools/radars.py validate` (it fails while the GeoJSON is stale), then `python -m pytest -q`.
- **Review map:** with the repo cloned, `python tools/radars.py place` opens a local map to drag and
  confirm points (IMMU by default: its page plus the press announcements typed into `tools/lists/`;
  `place --from osm` for the OpenStreetMap nodes). A crossing ("Avenida A/Rua B") starts where the two
  roads meet, just before the junction on the lane of its sentido;
  `place --apply path/to/placed.json` merges the result into the CSV.
- **Review:** CI must pass and the owner reviews and merges.
