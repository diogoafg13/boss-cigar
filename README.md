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
| Estancos nas cidades espanholas junto à fronteira (morada) | [Ministerio de Hacienda — CMT, Red de Expendedurías](https://www.hacienda.gob.es/es-ES/Areas%20Tematicas/CMTabacos/Paginas/Red-Expendedurias-y-PVR.aspx) (CSV oficial) | Reutilização permitida citando "Origem dos dados: Ministerio de Hacienda" |
| Tabacarias em Portugal | [OpenStreetMap](https://www.openstreetmap.org/) via Overpass | ODbL |
| **~4 800 charutos à venda em Espanha: marca, nome, embalagem, preço oficial** (lista vigente) | [Ministerio de Hacienda — CMT, Precios de labores](https://www.hacienda.gob.es/es-ES/Areas%20Tematicas/CMTabacos/Paginas/PreciosLabores.aspx) (exportação CSV do buscador oficial) | Reutilização permitida, incluindo comercial, citando "Origem dos dados: Ministerio de Hacienda" (Ley 37/2007) |
| **~3 400 charutos à venda em França: nome, vitola, embalagem, preço oficial** (mensal) | [Douane — nomenclature des prix des tabacs](https://www.douane.gouv.fr/la-douane/opendata/categories/tabacs-manufactures) (ODS) | Informação pública reutilizável (CRPA art. L321-1), com menção da fonte |

A nomenclatura francesa é a maior lista oficial e aberta de charutos que encontrei. Não traz força, capa nem sabores, mas traz o nome comercial exato de cada referência, o formato, a embalagem e o preço homologado. O pipeline:
- atribui a marca pelo catálogo da Wikipédia ou, se não estiver lá, infere-a do início do nome quando há pelo menos 3 referências (assinalada como *inferida*);
- deteta vitola e medidas no nome quando existem;
- liga cada ficha do seed às referências francesas (o nome tem de começar por marca + linha), mostrando o preço oficial;
- se a página da douane bloquear o pedido, usa o URL em `data/seed/sources.yml` e, em último caso, a cache.

### Espanha e comparação

O buscador oficial do CMT tem um botão "Exportar a CSV"; o pipeline reproduz esse pedido (zona Península e Illes Balears, labor Cigarros). A marca vem explícita (em maiúsculas no início do nome) e serve também para reconhecer marcas no catálogo francês. Cada execução guarda um snapshot datado, por isso o histórico espanhol cresce a cada semana. `compare.json` junta as referências que existem nos dois países (nome normalizado) e calcula a diferença de preço.

### Feed de novidades

`site/feed.xml` (Atom) tem uma entrada por cada nova edição francesa e por cada alteração detetada em Espanha: subidas, descidas, novas referências e retiradas.

### Histórico de preços

`douane_fr_archive` em `data/seed/sources.yml` lista as edições anteriores da nomenclatura (desde janeiro de 2025). Cada uma é descarregada uma vez e fica em cache como *snapshot*. O build calcula a série de preço de cada referência, as maiores subidas e descidas, a variação mediana por marca e as referências que saíram do mercado no último ano. Variações acima de 75% são tratadas como erros de origem (preço da embalagem posto como unitário) e excluídas.

### O que não tem fonte aberta

Não existe nenhuma base de dados aberta com força, capa e sabores por linha de charuto (a nomenclatura francesa tem nomes e preços, mas não perfil). Os sites que têm esses dados (revistas, lojas, agregadores) não têm licença aberta, e o projeto [cigarspace](https://github.com/sw3rm-labs/cigarspace) é não comercial e alimenta-se de catálogos de lojas. Por isso:

- **Força, capa, vitola e sabores** ficam no seed curado. Um campo só conta como verificado (`verified_fields`) se tiver uma fonte citada em `sources`.
- **Harmonizações** são calculadas por regras explícitas (`src/bosscigar/pairing.py`, publicadas no site), em vez de afirmações por charuto impossíveis de verificar.

### Robustez

- Cada fonte é guardada em `data/cache/`. Se falhar, usa-se a cache e o `meta.json` marca `CACHE`, `PARCIAL` ou `ERRO`.
- O relatório de qualidade (`site/data/quality.json`, calculado em SQL) inclui: % verificado, marcas fora da Wikipédia/Wikidata, divergências de país e regiões sem clima.

## Funcionalidades para aficionados

Tudo o que é pessoal fica no browser (localStorage) e pode ser exportado em JSON.

- **Recomendações**: perfil de palato a partir do Diário (força, capa, país, marca, vitola, preço), recomendações da base e do catálogo oficial com explicação, e estatísticas (provas por mês, marcas, acompanhamentos, valor do humidor).
- **Humidor**: referências do catálogo oficial, preço pago, código da caixa Habanos (mês/ano de embalamento; os códigos de fábrica são secretos e não são interpretados), alertas de descanso e de envelhecimento, registo do higrómetro e conselhos para o clima de Lisboa no mês corrente (NASA POWER).
- **Preços oficiais**: evolução de cada referência, edições especiais (limitadas, regionais, zodíaco, reservas, aniversários) detetadas no nome, referências retiradas.
- **Guias**: checklist anti-falsificação (marcas oficiais da Habanos S.A.), descodificador do código da caixa, tempo de fumada estimado, franquias de viagem (Guia para Viajantes, Portal das Finanças, fev. 2026).
- **Diário**: provas de qualquer referência do catálogo oficial, partilha de uma nota por link, importação do diário de um amigo.
- **Offline**: PWA com service worker; instalável no telemóvel e usável sem rede.
- **Lista de desejos e plano de compra** (Comprar → Lista de desejos): ♡ em qualquer referência oficial (FR/ES), quantidades, custo total em Espanha e em França (com o par do outro país pela comparação), preço português opcional (Portugal não publica a tabela), contagem face aos 200 charutos indicativos da UE, custo da viagem até à cidade fronteiriça, regras (compra online transfronteiriça proibida a consumidores em Portugal, Lei 37/2007 art. 14.º-A; compra presencial em Espanha permitida) e onde comprar: estancos oficiais junto à fronteira e lojas especializadas em Portugal, por distância.
- **Prova guiada**: sabores por terço numa roda de sabores, tiragem, combustão, cinza, força sentida e retrohale; os sabores alimentam as recomendações.
- **Sincronização**: diário, humidor, higrómetro, favoritos, desejos e notas de amigos num Gist privado do utilizador (token guardado só no browser); a reposição junta sem apagar nada.
- **Guias**: também calculadora de Boveda (regra do fabricante) e glossário pesquisável.
- **Inglês**: botão EN/PT para a interface (menus, títulos, botões); os dados mantêm a língua de origem.
- **Navegação**: 4 grupos (Descobrir, Comprar, O meu, Aprender), título e descrição em cada página, endereço por página (`#wishlist`, `#frcat`, `#marca=Cohiba`…) com o botão "voltar" a funcionar, botão "Limpar filtros (n)" e pesquisa global no topo.
- **Páginas de marca**: fichas, referências e intervalos de preço em França e Espanha, variação de preço, comparação FR/ES, Wikipédia e Wikidata.
- **Livro**: "Do Zero ao Expert" em PDF (`site/docs/`), roteiro de aprendizagem com progresso, vinhos portugueses (Porto, Madeira, Moscatel) e mapa de sabores por origem. É conteúdo editorial do projeto, não fonte de verificação.
- **Lojas**: filtro de especialistas em charutos no mapa (identificados pelo nome no OpenStreetMap).

## Receber novidades (RSS)

Subscreve `https://diogoafg13.github.io/boss-cigar/feed.xml` em qualquer leitor de RSS/Atom (Feedly, Inoreader, NetNewsWire, Reeder…). Cada nova edição francesa e cada alteração em Espanha aparece como uma entrada, com subidas, descidas, novidades e retiradas.

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
3. Settings → Actions → General → Workflow permissions: **Read and write** (o workflow guarda `data/cache` e `data/clean` com commits do `boss-cigar-bot`, para a próxima execução ter sempre a última versão de cada fonte).
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

44 fichas, das quais 43 têm campos confirmados numa fonte citada (`verified_fields` + `sources`): medidas e vitola de galera (Wikipédia, listas de vitolas das marcas cubanas), capa, país e força (fichas técnicas dos fabricantes/retalhistas). A verificação corrigiu medidas erradas (ex.: H. Upmann Magnum 50, Cohiba Siglo VI, Padrón 1926 No. 9, Oliva Melanio, Liga Privada No. 9).

- **Força** só é preenchida quando há fonte. Nos Habanos usa-se a [classificação oficial de intensidade da Habanos S.A.](https://www.habanos.com/en/strengths/) por marca/linha; 3 fichas ficam "sem dado" (H. Upmann tem duas classificações e o Lusitanias não tem linha listada).
- **Sabores** das fichas originais continuam por confirmar (não há fonte aberta); as fichas novas não têm sabores inventados.
- Os sabores sentidos por cada utilizador (prova guiada) ficam no browser dele e alimentam as recomendações.

## Roadmap

- [ ] Fotos de anilhas e vitolas (apenas com licença livre)
- [ ] Notas de prova partilhadas entre utilizadores (exige backend; ex.: GitHub Discussions via giscus)
- [ ] Notificação de dados desatualizados (campos sem verificação há mais de N meses)

## Aviso

Projeto pessoal e educativo, para maiores de 18 anos. As características dos charutos variam por lote e colheita. Fumar prejudica a saúde.
