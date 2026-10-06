# 🚬 Boss Cigar

Base de dados de charutos com mapa de origens, clima por terroir, harmonizações, comparador, vitolas à escala, humidor, diário de provas e guia em PDF.
Pipeline Python (Parquet + DuckDB) a alimentar um site estático (Leaflet) publicado no GitHub Pages por GitHub Actions, no mesmo modelo do imobAI.

## Como funciona

```
data/seed/*.yml ─► validação (pydantic) ─► fontes abertas ─► Parquet/DuckDB ─► site/data/*.json
 (curado à mão)     schema + integridade    (cache = fallback)   data/clean/
```

### Fontes abertas

| Dado | Fonte | Licença |
|---|---|---|
| Catálogo de marcas e fabricantes (~160) | [Wikipédia — List of cigar brands](https://en.wikipedia.org/wiki/List_of_cigar_brands) | CC BY-SA 4.0 |
| Ano de fundação e país das marcas | [Wikidata](https://www.wikidata.org/) | CC0 |
| Temperatura, chuva e humidade por zona de cultivo | [NASA POWER](https://power.larc.nasa.gov/) (climatologia) | Domínio público |
| Produção de tabaco por país desde 2000 | [FAOSTAT](https://www.fao.org/faostat/) (item 826) | CC BY 4.0 |
| Tabacarias em Portugal | [OpenStreetMap](https://www.openstreetmap.org/) via Overpass | ODbL |
| **~3 400 charutos à venda em França: nome, vitola, embalagem, preço oficial** (mensal) | [Douane — nomenclature des prix des tabacs](https://www.douane.gouv.fr/la-douane/opendata/categories/tabacs-manufactures) (ODS) | Informação pública reutilizável (CRPA art. L321-1), com menção da fonte |

A nomenclatura francesa é a maior lista oficial e aberta de charutos que encontrei. Não traz força, capa nem sabores, mas traz o nome comercial exato de cada referência, o formato, a embalagem e o preço homologado. O pipeline:
- atribui a marca pelo catálogo da Wikipédia ou, se não estiver lá, infere-a do início do nome quando há pelo menos 3 referências (assinalada como *inferida*);
- deteta vitola e medidas no nome quando existem;
- liga cada ficha do seed às referências francesas (o nome tem de começar por marca + linha), mostrando o preço oficial;
- se a página da douane bloquear o pedido, usa o URL em `data/seed/sources.yml` e, em último caso, a cache.

### O que não tem fonte aberta

Não existe nenhuma base de dados aberta com força, capa e sabores por linha de charuto (a nomenclatura francesa tem nomes e preços, mas não perfil). Os sites que têm esses dados (revistas, lojas, agregadores) não têm licença aberta, e o projeto [cigarspace](https://github.com/sw3rm-labs/cigarspace) é não comercial e alimenta-se de catálogos de lojas. Por isso:

- **Força, capa, vitola e sabores** ficam no seed curado. Um campo só conta como verificado (`verified_fields`) se tiver uma fonte citada em `sources`.
- **Harmonizações** são calculadas por regras explícitas (`src/bosscigar/pairing.py`, publicadas no site), em vez de afirmações por charuto impossíveis de verificar.

### Robustez

- Cada fonte é guardada em `data/cache/`. Se falhar, usa-se a cache e o `meta.json` marca `CACHE`, `PARCIAL` ou `ERRO`.
- O relatório de qualidade (`site/data/quality.json`, calculado em SQL) inclui: % verificado, marcas fora da Wikipédia/Wikidata, divergências de país e regiões sem clima.

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
Nota: a Wikipédia e o Overpass limitam pedidos por IP. O que falhar numa execução fica com a cache e completa-se na seguinte.

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
- [ ] Checklist de falsificações
- [ ] Notificação de dados desatualizados (campos sem verificação há mais de N meses)

## Aviso

Projeto pessoal e educativo, para maiores de 18 anos. As características dos charutos variam por lote e colheita. Fumar prejudica a saúde.
