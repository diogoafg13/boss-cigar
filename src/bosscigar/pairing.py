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
WRAPPER_RULES = [
    (("maduro", "oscuro", "broadleaf"), ["Porto Tawny 20 anos", "Stout"], ["Chocolate negro"],
     "Capa escura: doçura e cacau ligam com bebidas de caramelo e torra."),
    (("connecticut", "claro"), ["Café com leite", "Chá"], ["Pastelaria"],
     "Capa clara: notas cremosas ligam com bebidas suaves."),
]


def suggest(strength: int, wrapper: str) -> dict:
    drinks, food, why = [], [], []
    for lo, hi, d, f, w in RULES:
        if lo <= strength <= hi:
            drinks += d; food += f; why.append(w)
    wl = (wrapper or "").lower()
    for keys, d, f, w in WRAPPER_RULES:
        if any(k in wl for k in keys):
            drinks += d; food += f; why.append(w)
    dedup = lambda xs: list(dict.fromkeys(xs))
    return {"drinks": dedup(drinks), "food": dedup(food), "why": why}


def rules_doc() -> list[dict]:
    out = [{"when": f"Força {lo}–{hi}" if lo != hi else f"Força {lo}", "drinks": d, "food": f, "why": w}
           for lo, hi, d, f, w in RULES]
    out += [{"when": "Capa " + "/".join(k), "drinks": d, "food": f, "why": w} for k, d, f, w in WRAPPER_RULES]
    return out
