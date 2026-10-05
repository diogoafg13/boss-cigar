# 🚬 Boss Cigar

Base de dados de charutos com mapa de origens, clima por terroir, harmonizações, comparador, vitolas à escala, humidor, diário de provas e guia em PDF.
Pipeline Python (Parquet + DuckDB) a alimentar um site estático (Leaflet) publicado no GitHub Pages por GitHub Actions, no mesmo modelo do imobAI.

## Como funciona

```
data/seed/*.yml  ──►  validação (pydantic)  ──►  Wikidata + Open-Meteo  ──►  Parquet/DuckDB  ──►  site/data/*.json
 (curado à mão)         schema + integridade       (cache como fallback)      data/clean/         cigars, meta, quality
```

- **Seed curado** (`data/seed/cigars.yml`, `regions.yml`): fonte de verdade, editável por pull request.
- **Validação**: campos obrigatórios, força 1–5, regiões existentes, ids únicos. Um campo só pode ser declarado `verified_fields` se houver `sources` com URL.
- **Fontes abertas** (enriquecimento, nunca sobrepõem o seed):
  - [Wikidata](https://www.wikidata.org/) (CC0): ano de fundação e país das marcas. Divergências de país vão para o relatório de qualidade.
  - [Open-Meteo](https://open-meteo.com/) (CC BY 4.0, uso não comercial): temperatura e precipitação médias 2015–2024 por zona de cultivo.
- **Fallback**: cada resposta é guardada em `data/cache/`. Se uma fonte falhar, usa-se a cache e o `meta.json` marca `CACHE`, `PARCIAL` ou `ERRO`.
- **Qualidade** (`site/data/quality.json`, calculada em SQL): % de dados verificados, marcas sem Wikidata, regiões sem clima ou sem charutos, divergências de país.
- **Sem scraping** de lojas nem de pontuações de revistas (termos de utilização e direitos de autor).

## Correr localmente

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
python -m bosscigar validate        # só valida o seed
python -m bosscigar build           # fontes + Parquet + JSON do site
BOSSCIGAR_MODE=cache python -m bosscigar build   # sem rede, usa a cache
cd site && python -m http.server 8000            # http://localhost:8000
```

`BOSSCIGAR_MODE`: `auto` (rede com fallback), `cache` ou `offline` (só cache).
Nota: o Open-Meteo tem limites diários por IP; o que falhar numa execução fica em cache e completa-se na seguinte.

## Publicar no GitHub

1. Criar o repositório `boss-cigar` e fazer push para `main`.
2. Settings → Pages → Source: **GitHub Actions**.
3. Settings → Actions → General → Workflow permissions: **Read and write** (o workflow guarda `data/cache` e `data/clean`).
4. O workflow `build-and-deploy` corre a cada push, à segunda-feira e manualmente (Actions → Run workflow).

## Adicionar ou corrigir um charuto

Editar `data/seed/cigars.yml` e correr `python -m bosscigar validate`. Para marcar um campo como verificado:

```yaml
verified_fields: [wrapper, strength]
sources:
  - {title: "Nome da fonte", url: "https://…"}
```

O PDF do guia vai em `site/docs/do-zero-ao-expert-livro-do-charuto.pdf`.

## Estado dos dados

Os 28 charutos foram compilados de conhecimento geral. Só os campos com `verified_fields` foram confirmados numa fonte; o resto aparece no site como **por confirmar**. Prioridade do roadmap: verificar linha a linha.

## Roadmap

- [ ] Verificar os restantes charutos contra fontes públicas (fabricantes, Habanos S.A., Cigar Coop, Halfwheel)
- [ ] Fotos de anilhas e vitolas (apenas com licença livre)
- [ ] Roda de sabores interativa
- [ ] Onde comprar em Portugal (só com moradas confirmadas)
- [ ] Checklist de falsificações
- [ ] Notificação de dados desatualizados (campos sem verificação há mais de N meses)

## Aviso

Projeto pessoal e educativo, para maiores de 18 anos. As características dos charutos variam por lote e colheita. Fumar prejudica a saúde.
