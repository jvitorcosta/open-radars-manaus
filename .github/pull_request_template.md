## O que muda / What changes

<!-- ids adicionados, movidos, corrigidos ou removidos / ids added, moved, fixed or removed -->

## Checklist

- [ ] É um ponto fixo e público (não é blitz nem radar móvel) / A fixed public point
- [ ] Sem dados pessoais (sem placas nem rostos, sem trajetos de GPS) / No personal data
- [ ] GeoJSON regenerado com `python tools/radars.py geojson` / GeoJSON regenerated
- [ ] `python tools/radars.py validate` passa / passes (depois do geojson / after geojson)
- [ ] `python -m pytest -q` passa / passes
