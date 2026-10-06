"""Harmonizações por regra, a partir da força e da capa.

Não há fonte aberta de harmonizações por charuto. Em vez de afirmações por linha
que não podem ser verificadas, usam-se regras explícitas e consultáveis
(princípio geral: igualar intensidades; capas escuras/doces pedem bebidas com
notas de caramelo/cacau; capas claras pedem bebidas leves). As regras estão
publicadas no site para o utilizador as poder contestar.
"""
from __future__ import annotations

RULES = [
    # (força mínima, força máxima, bebidas, comida, justificação)
    (1, 2, ["Café", "Porto branco", "Champanhe", "Cerveja lager"], ["Pastelaria", "Fruta", "Queijo fresco"],
     "Charutos suaves: bebidas leves que não abafem o tabaco."),
    (3, 3, ["Porto Tawny 10 anos", "Rum añejo", "Cognac VSOP", "Madeira"], ["Frutos secos", "Queijo semicurado"],
     "Corpo médio: bebidas envelhecidas de intensidade semelhante."),
    (4, 5, ["Rum escuro", "Bourbon", "Whisky de malte", "Espresso", "Stout"], ["Chocolate negro", "Carne grelhada", "Queijo curado"],
     "Charutos fortes: bebidas com estrutura para acompanhar a intensidade."),
]
# Vinhos fortificados portugueses (cap. 28 do livro "Do Zero ao Expert", guia editorial do projeto).
PT_WINE_RULES = [
    (1, 2, ["Porto branco reserva", "Madeira Sercial/Verdelho"], "Charutos suaves: fortificados secos e frescos."),
    (3, 3, ["Porto Ruby", "Porto Tawny 10 anos", "Madeira Bual"], "Médios: fruta e caramelo sem abafar."),
    (4, 5, ["Porto Vintage / LBV", "Porto Tawny 20 anos"], "Encorpados: fruta negra e estrutura para um charuto com espinha."),
]
PT_WINE_WRAPPER = [
    (("maduro", "oscuro", "broadleaf", "san andr"), ["Porto Tawny 20 anos", "Madeira Malmsey"], "Capa escura: tawny e Malmsey espelham cacau e café."),
    (("cameroon",), ["Moscatel de Setúbal"], "Capa Cameroon: laranja confitada e mel do Moscatel com o doce-picante da capa."),
    (("connecticut",), ["Porto branco com tónica (portonic)"], "Capa Connecticut num fim de tarde de verão."),
]

WRAPPER_RULES = [
    (("maduro", "oscuro", "broadleaf"), ["Porto Tawny 20 anos", "Stout"], ["Chocolate negro"],
     "Capa escura: doçura e cacau ligam com bebidas de caramelo e torra."),
    (("connecticut", "claro"), ["Café com leite", "Chá"], ["Pastelaria"],
     "Capa clara: notas cremosas ligam com bebidas suaves."),
]


def suggest(strength: int | None, wrapper: str) -> dict:
    drinks, food, why = [], [], []
    for lo, hi, d, f, w in RULES:
        if strength is not None and lo <= strength <= hi:
            drinks += d; food += f; why.append(w)
    wl = (wrapper or "").lower()
    for keys, d, f, w in WRAPPER_RULES:
        if any(k in wl for k in keys):
            drinks += d; food += f; why.append(w)
    pt, pt_why = [], []
    for lo, hi, d, w in PT_WINE_RULES:
        if strength is not None and lo <= strength <= hi:
            pt += d; pt_why.append(w)
    for keys, d, w in PT_WINE_WRAPPER:
        if any(k in wl for k in keys):
            pt += d; pt_why.append(w)
    if not pt:
        pt = ["Porto Tawny 10 anos"]
    if strength is None and not drinks:
        drinks, food = ["Porto Tawny 10 anos", "Rum añejo", "Café"], ["Frutos secos", "Chocolate negro"]
        why.append("Força ainda sem fonte: sugestões versáteis, que acompanham bem a maioria dos charutos.")
    dedup = lambda xs: list(dict.fromkeys(xs))
    return {"drinks": dedup(drinks), "food": dedup(food), "why": why, "ptWines": dedup(pt), "ptWhy": pt_why}


def rules_doc() -> list[dict]:
    out = [{"when": f"Força {lo}–{hi}" if lo != hi else f"Força {lo}", "drinks": d, "food": f, "why": w}
           for lo, hi, d, f, w in RULES]
    out += [{"when": "Capa " + "/".join(k), "drinks": d, "food": f, "why": w} for k, d, f, w in WRAPPER_RULES]
    return out
