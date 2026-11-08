## O que muda / What changes

<!-- ids adicionados, movidos, corrigidos ou removidos / ids added, moved, fixed or removed -->

## Checklist

- [ ] É um equipamento fixo em via pública (não é blitz nem radar móvel) / A fixed device on a public road
- [ ] Cada ponto novo ou alterado foi verificado e tem `checked` com a data da verificação / Each new or changed point was verified and `checked` holds that date
- [ ] Nenhuma coordenada copiada de mapas proprietários (Google Maps, Street View) / No coordinates copied from proprietary maps
- [ ] Sem dados pessoais (sem placas nem rostos, sem trajetos de GPS) / No personal data
- [ ] GeoJSON e mapa do README regenerados com `python tools/radars.py geojson` / GeoJSON and README map regenerated
- [ ] `python tools/radars.py validate` passa / passes (depois do geojson / after geojson)
- [ ] `python -m pytest -q` passa / passes
