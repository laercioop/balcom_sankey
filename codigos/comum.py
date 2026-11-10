"""Definições comuns: pastas, grupos HS e categorias de petróleo.

Todos os países são classificados pelo Sistema Harmonizado (HS), a mesma
base em todas as fontes:
- Brasil: NCM (8 dígitos; os 6 primeiros são HS6) - MDIC/Comex Stat;
- EUA: HS reportado pelo Census, via UN Comtrade;
- UE27: HS/CN, comércio extra-UE, Eurostat Comext;
- China: capítulos HS da alfândega (GACC), tabela mensal (4).
"""
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DADOS = RAIZ / "dados"
BRUTOS = DADOS / "brutos"
GRAFICOS = RAIZ / "graficos"

INICIO = 2015  # primeiro ano coletado (China começa em 2018 na fonte em inglês)

# Onde ficam os arquivos padronizados de cada país ({pais}_hs2.csv, {pais}_petroleo.csv).
# Cada país tem pipeline próprio (coleta + README) na pasta Dados da sua base.
P = Path("P:/Atualização")
PASTAS_DADOS = {
    "brasil": P / "Setor Externo/SECEX/Dados",
    "eua": P / "Internacional/EUA/Setor Externo/Dados",
    "ue": P / "Internacional/Europa/Setor Externo/Dados",
    "china": P / "Internacional/China/setor externo/Dados",
}

PAISES = {
    "brasil": "Brasil",
    "eua": "EUA",
    "ue": "UE",
    "china": "China",
}
FLUXOS = {"exp": "Exportações", "imp": "Importações"}

# ── Análise 1: grandes grupos (faixas de capítulos HS) ───────────────────────
GRANDES = [
    ("Agro e alimentos", range(1, 25)),
    ("Minérios", range(25, 27)),
    ("Combustíveis", range(27, 28)),
    ("Químicos e plásticos", range(28, 41)),
    ("Couro, madeira, papel e têxteis", range(41, 68)),
    ("Metais, pedras e vidro", range(68, 84)),
    ("Máquinas e elétricos", range(84, 86)),
    ("Material de transporte", range(86, 90)),
    ("Outros", range(90, 100)),
]

# ── Análise 2: grupos granulares (capítulos HS) ─────────────────────────────
GRANULAR = [
    ("Carnes e prod. animais", list(range(1, 6))),
    ("Soja, grãos e café", [9, 10, 12]),
    ("Outros vegetais", [6, 7, 8, 11, 13, 14]),
    ("Óleos, alim. e bebidas", list(range(15, 25))),
    ("Minérios", [25, 26]),
    ("Combustíveis", [27]),
    ("Químicos e farmacêuticos", list(range(28, 39))),
    ("Plásticos e borracha", [39, 40]),
    ("Madeira, celulose e papel", list(range(44, 50))),
    ("Têxteis, couro e calçados", [41, 42, 43] + list(range(50, 68))),
    ("Pedras, vidro e metais preciosos", [68, 69, 70, 71]),
    ("Ferro, aço e metais", list(range(72, 84))),
    ("Máquinas mecânicas", [84]),
    ("Máquinas elétricas e eletrônicos", [85]),
    ("Veículos", [87]),
    ("Aeronaves, navios e ferrovias", [86, 88, 89]),
    ("Instrumentos e diversos", list(range(90, 100))),
]

# ── Análises 3 e 4: petróleo, derivados e gás (HS 2709 a 2715) ──────────────
# Prefixos HS6/HS4; a primeira correspondência vale.
PETROLEO = [
    ("Petróleo bruto", ("2709",)),
    ("Derivados leves (gasolina, nafta)", ("271012", "271011")),  # 271011: código HS2007
    ("Derivados médios e pesados (diesel, QAV, óleo comb.)", ("271019", "271020")),
    ("Gás natural (GNL e gasoso)", ("271111", "271121")),
    ("GLP e outros gases", ("271112", "271113", "271114", "271119", "271129")),
    ("Resíduos, coque, betume e outros", ("271091", "271099", "2712", "2713", "2714", "2715")),
]
PETRO_TOTAL = "Petróleo, derivados e gás"
EX_PETRO = "Ex-petróleo"


def categoria_petroleo(codigo):
    """Recebe um código HS/NCM (>= 4 dígitos) e devolve a categoria ou None."""
    codigo = str(codigo)
    for nome, prefixos in PETROLEO:
        if codigo.startswith(prefixos):
            return nome
    return None


def mapa_capitulos(grupos):
    """Capítulo HS (int 1-99) -> grupo. O capítulo 77 (reservado) e códigos
    especiais ficam no último grupo (outros/diversos)."""
    out = {}
    for nome, caps in grupos:
        for c in caps:
            if c in out:
                raise ValueError(f"Capítulo {c} em dois grupos")
            out[c] = nome
    faltam = sorted(set(range(1, 100)) - set(out) - {77})
    if faltam:
        raise ValueError(f"Capítulos sem grupo: {faltam}")
    out[77] = grupos[-1][0]
    return out


MAPA_GRANDES = mapa_capitulos(GRANDES)
MAPA_GRANULAR = mapa_capitulos(GRANULAR)


def ler_dados(pais, tipo):
    """Lê {pais}_{tipo}.csv da pasta Dados do país (None se não existir)."""
    import pandas as pd
    arq = PASTAS_DADOS[pais] / f"{pais}_{tipo}.csv"
    if not arq.exists():
        return None
    return pd.read_csv(arq, dtype={"hs2": str})


# A GACC muda a lista de subitens de derivados entre anos; a divisão
# leves/médios/não discriminados criaria saltos artificiais na China.
DERIVADOS_CHINA = "Derivados de petróleo"
_JUNTA_CHINA = {"Derivados leves (gasolina, nafta)", "Derivados não discriminados",
                "Derivados médios e pesados (diesel, QAV, óleo comb.)"}


def juntar_derivados_china(pet):
    pet = pet.assign(categoria=pet.categoria.where(~pet.categoria.isin(_JUNTA_CHINA),
                                                   DERIVADOS_CHINA))
    cols = [c for c in ("valor", "valor_acum") if c in pet]
    return pet.groupby(["date", "fluxo", "categoria"], as_index=False)[cols].sum(min_count=1)
