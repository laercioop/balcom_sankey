"""Sankey das exportações do Brasil: produto -> destino, por quadrimestre.

Pasta 5 (graficos/5_sankey_destinos):
  {n}_brasil_exp_sankey_{periodo}.png       ex-petróleo (padrão)
  com_petroleo/{n}_..._com_petroleo.png     inclui petróleo bruto e derivados
  todos_sankey*.png                         painel com os períodos

Dados: dados/sankey/brutos/exp_pais_ncm_{ano}.csv.gz (coleta_sankey.py).

Dessazonalização direta de cada grupo de produto x bloco de destino pelo X-13,
com histórico NCM desde 1997. Base: produto_destino_dessaz.csv, gerada por
 dessaz_destinos.py. Totais e agregações visuais são somas indiretas.

Valores: média mensal do período, US$ bilhões (períodos parciais comparáveis).
Escala vertical fixa entre os períodos de cada versão.

Uso: python sankey.py
"""
import sys

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from PIL import Image

from comum import DADOS, GRAFICOS
from estilo_ps import PALETTE, TITLE_GRAY, GRID

PASTA = GRAFICOS / "5_sankey_destinos"
PASTA_PETRO = PASTA / "com_petroleo"
BRUTOS = DADOS / "sankey" / "brutos"

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
PERIODOS = [("2024-11", "2025-02"), ("2025-03", "2025-06"), ("2025-07", "2025-10"), ("2025-11", "2026-02"),
            ("2026-03", "2026-06"), ("2026-07", "2026-10")]

# Grupos granulares pequenos juntados em "Demais produtos"
DEMAIS_PROD = "Demais produtos"
JUNTAR = {"Outros vegetais", "Instrumentos e diversos", "Plásticos e borracha",
          "Máquinas elétricas e eletrônicos", "Combustíveis"}  # Combustíveis = HS 27 ex-petróleo
PETRO_BRUTO, DERIVADOS = "Petróleo bruto", "Derivados de petróleo"
ROTULO_PROD = {"Pedras, vidro e metais preciosos": "Pedras, vidro e ouro",
               "Óleos, alim. e bebidas": "Óleos, farelo, açúcar e bebidas",
               "Têxteis, couro e calçados": "Têxteis, couro e calçados",
               "Aeronaves, navios e ferrovias": "Aeronaves e navios"}

DEMAIS_DEST = "Demais destinos"
DESTINOS = ["China", "EUA", "União Europeia", "Argentina", "Demais Am. Latina",
            "Ásia ex-China", "Oriente Médio", "África", DEMAIS_DEST]
# China azul, EUA terracota, UE verde-ciano, Argentina dourado, Am. Latina verde,
# Ásia roxo, Oriente Médio rosa, África cinza escuro, demais cinza claro
COR_DEST = dict(zip(DESTINOS, [PALETTE[0], PALETTE[1], PALETTE[2], PALETTE[4], PALETTE[5],
                               PALETTE[6], PALETTE[8], PALETTE[9], GRID]))

NOTA_EX = "Ex-petróleo: exclui petróleo bruto, derivados e gás (HS 2709 a 2715)."
NOTA_COM = "Inclui petróleo bruto, derivados e gás (HS 2709 a 2715)."


# ── Dados ─────────────────────────────────────────────────────────────────────
def destino(pais):
    """Linha da tabela de países -> grupo de destino."""
    cod, nome, bloco = pais.CO_PAIS, str(pais.NO_PAIS), str(pais.NO_BLOCO)
    if cod == 160:
        return "China"
    if nome in ("Estados Unidos", "Porto Rico"):
        return "EUA"
    if "União Europeia" in bloco and nome not in ("Andorra", "San Marino"):
        return "União Europeia"
    if cod == 63:
        return "Argentina"
    if "América do Sul" in bloco or "América Central" in bloco or nome == "México":
        return "Demais Am. Latina"
    if "Ásia (Exclusive" in bloco:   # "Ásia (Exclusive Oriente Médio)"
        return "Ásia ex-China"
    if "Oriente Médio" in bloco:
        return "Oriente Médio"
    if "África" in bloco:
        return "África"
    return DEMAIS_DEST


def carregar():
    from dessaz_destinos import SAIDA, fontes
    import json
    meta = json.loads((DADOS / 'sankey' / 'dessaz_produto_destino_meta.json').read_text(encoding='utf-8'))
    if meta['fontes'] != fontes():
        raise RuntimeError('Os brutos mudaram. Execute dessaz_destinos.py antes dos gráficos.')
    d = pd.read_csv(SAIDA).rename(columns={'valor': 'VL_FOB', 'serie': 'granular'})
    if d.duplicated(['date', 'destino', 'granular']).any():
        raise RuntimeError('Duplicatas no dessaz produto x destino')
    d['petro'] = d.granular.where(d.granular.isin([PETRO_BRUTO, DERIVADOS]))
    prod = d.granular.where(~d.granular.isin(JUNTAR), DEMAIS_PROD)
    d['produto'] = prod.map(lambda x: ROTULO_PROD.get(x, x))
    ult_sa = d.date.max()

    return d, ult_sa


def rotulo_periodo(ini, fim, n_meses):
    a, b = pd.Period(ini, "M"), pd.Period(fim, "M")
    txt = f"{MESES[a.month - 1]}-{MESES[b.month - 1]}/{b.year % 100:02d}"
    if a.year != b.year:
        txt = f"{MESES[a.month - 1]}/{a.year % 100:02d}-{MESES[b.month - 1]}/{b.year % 100:02d}"
    return txt


def matrizes(d, ult, com_petro):
    """{rótulo: DataFrame produto x destino, média mensal em US$ bi}."""
    if not com_petro:
        d = d[d.petro.isna()]
    out = {}
    for ini, fim in PERIODOS:
        fim_ef = min(fim, ult)
        if fim_ef < ini:
            continue
        x = d[(d.date >= ini) & (d.date <= fim_ef)]
        n = x.date.nunique()
        m = x.pivot_table(index="produto", columns="destino", values="valor_sa",
                          aggfunc="sum", fill_value=0) / n / 1e9
        rot = rotulo_periodo(ini, fim_ef, n)
        out[rot] = dict(m=m, n=n, parcial=fim_ef < fim, slug=f"{ini[:4]}{ini[5:]}_{fim_ef[:4]}{fim_ef[5:]}")
    return out


# ── Desenho ───────────────────────────────────────────────────────────────────
def fmt(v, casas=1):
    return f"{v:.{casas}f}".replace(".", ",")


def layout(valores, k, gap, hmin, topo):
    """Posições (y0 topo, y1 base) dos nós, de cima para baixo; cada nó ocupa
    pelo menos hmin para caber o rótulo."""
    pos, y = {}, topo
    for nome, v in valores.items():
        h = v * k
        slot = max(h, hmin)
        y0 = y - (slot - h) / 2
        pos[nome] = (y0, y0 - h)
        y -= slot + gap
    return pos, topo - y - gap


def faixa(ax, x0, x1, a0, a1, b0, b1, cor):
    """Faixa curva entre [a1, a0] em x0 e [b1, b0] em x1 (topo, base)."""
    t = np.linspace(0, 1, 60)
    s = 3 * t ** 2 - 2 * t ** 3
    x = x0 + (x1 - x0) * t
    top = a0 + (b0 - a0) * s
    bot = a1 + (b1 - a1) * s
    ax.fill_between(x, bot, top, color=cor, alpha=0.42, lw=0, zorder=1)


def desenhar(m, ordem_p, ordem_d, k, titulo, nota, arquivo):
    W, H = 7.2, 5.0
    fig = plt.figure(figsize=(W, H), dpi=300)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    XL, XR, BW = 0.315, 0.665, 0.012
    TOPO, GAP, HMIN = 0.855, 0.0085, 0.026

    m = m.reindex(index=ordem_p, columns=ordem_d, fill_value=0)
    m = m.loc[m.sum(axis=1) > 0.005, m.sum(axis=0) > 0.005]
    tot = m.values.sum()
    vp, vd = m.sum(axis=1), m.sum(axis=0)
    pp, _ = layout(vp, k, GAP, HMIN, TOPO)
    pd_, _ = layout(vd, k, GAP, HMIN, TOPO)

    # Faixas: no produto, segmentos na ordem dos destinos; no destino, na dos produtos
    cur_p = {p: pp[p][0] for p in m.index}
    cur_d = {d: pd_[d][0] for d in m.columns}
    seg = {}
    for p in m.index:
        for d in m.columns:
            h = m.at[p, d] * k
            seg[(p, d)] = [cur_p[p], cur_p[p] - h]
            cur_p[p] -= h
    for d in m.columns:
        for p in m.index:
            h = m.at[p, d] * k
            seg[(p, d)] += [cur_d[d], cur_d[d] - h]
            cur_d[d] -= h
    for (p, d), (a0, a1, b0, b1) in seg.items():
        if a0 - a1 > 1e-5:
            faixa(ax, XL + BW, XR, a0, a1, b0, b1, COR_DEST[d])

    fs, cinza = 6.6, "#404040"
    for p in m.index:
        y0, y1 = pp[p]
        ax.add_patch(plt.Rectangle((XL, y1), BW, max(y0 - y1, 0.0008), color="#6b6b6b", lw=0, zorder=2))
        ax.text(XL - 0.008, (y0 + y1) / 2, p, ha="right", va="center", fontsize=fs, color=cinza)
    for d in m.columns:
        y0, y1 = pd_[d]
        ax.add_patch(plt.Rectangle((XR, y1), BW, max(y0 - y1, 0.0008), color=COR_DEST[d], lw=0, zorder=2))
        ax.text(XR + BW + 0.008, (y0 + y1) / 2, d, ha="left", va="center", fontsize=fs,
                color=cinza, weight="bold")
        ax.text(XR + BW + 0.155, (y0 + y1) / 2, f"{fmt(vd[d])}", ha="right", va="center",
                fontsize=fs, color=cinza)
        ax.text(XR + BW + 0.205, (y0 + y1) / 2, f"{fmt(vd[d] / tot * 100, 0)}%", ha="right",
                va="center", fontsize=fs, color="#8a8a8a")
    # Valores dos produtos à esquerda dos nomes (coluna própria)
    for p in m.index:
        y0, y1 = pp[p]
        ax.text(0.062, (y0 + y1) / 2, f"{fmt(vp[p])}", ha="right", va="center", fontsize=fs, color=cinza)
        ax.text(0.105, (y0 + y1) / 2, f"{fmt(vp[p] / tot * 100, 0)}%", ha="right", va="center",
                fontsize=fs, color="#8a8a8a")

    # Cabeçalhos
    yh = TOPO + 0.028
    kw = dict(fontsize=6.6, color="#8a8a8a", va="bottom")
    ax.text(0.062, yh, "US$ bi", ha="right", **kw)
    ax.text(0.105, yh, "%", ha="right", **kw)
    ax.text(XL - 0.008, yh, "Produto", ha="right", **kw)
    ax.text(XR + BW + 0.008, yh, "Destino", ha="left", **kw)
    ax.text(XR + BW + 0.155, yh, "US$ bi", ha="right", **kw)
    ax.text(XR + BW + 0.205, yh, "%", ha="right", **kw)
    ax.text((XL + XR + BW) / 2, yh, f"Total: US$ {fmt(tot)} bi/mês", ha="center",
            fontsize=7.2, color=TITLE_GRAY, va="bottom", weight="bold")

    ax.text(0.02, 0.965, titulo.replace("—", "-").replace("–", "-"), ha="left", va="top",
            family="Segoe UI", weight="bold", fontsize=12, color=TITLE_GRAY)
    ax.text(0.02, 0.018, nota, ha="left", va="bottom", fontsize=6.2, color="#6b6b6b", style="italic")
    ax.text(0.98, 0.018, "Média mensal dessazonalizada, US$ bilhões", ha="right", va="bottom",
            fontsize=6.2, color="#6b6b6b", style="italic")
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(arquivo, dpi=300, facecolor="white")
    plt.close(fig)
    return arquivo


def escala(mats, ordem_p, ordem_d, gap=0.0085, hmin=0.026, disponivel=0.80):
    """Maior k (altura por US$ bi) que faz todos os períodos caberem."""
    k = disponivel / max(x["m"].values.sum() for x in mats.values())
    for _ in range(200):
        alt = 0
        for x in mats.values():
            m = x["m"].reindex(index=ordem_p, columns=ordem_d, fill_value=0)
            for v in (m.sum(axis=1), m.sum(axis=0)):
                v = v[v > 0.005]
                alt = max(alt, layout(v, k, gap, hmin, 1)[1])
        if alt <= disponivel:
            return k
        k *= 0.98
    return k


def painel(arqs, destino, cols=3, gap=40):
    imgs = [Image.open(a).convert("RGB") for a in arqs]
    w, h = imgs[0].size
    linhas = -(-len(imgs) // cols)
    tela = Image.new("RGB", (cols * w + (cols - 1) * gap, linhas * h + (linhas - 1) * gap), "white")
    for i, im in enumerate(imgs):
        tela.paste(im, ((i % cols) * (w + gap), (i // cols) * (h + gap)))
    tela.save(destino, dpi=(300, 300))
    return destino


def main():
    d, ult = carregar()
    tabela = []
    for com_petro in (False, True):
        mats = matrizes(d, ult, com_petro)
        media = sum(x["m"].reindex(columns=DESTINOS, fill_value=0) for x in mats.values())
        media = media.fillna(0)
        demais = [DEMAIS_PROD]
        ordem_p = [p for p in media.sum(axis=1).sort_values(ascending=False).index if p not in demais] + demais
        ordem_d = DESTINOS
        k = escala(mats, ordem_p, ordem_d)
        pasta = PASTA_PETRO if com_petro else PASTA
        sufixo = "_com_petroleo" if com_petro else ""
        nota = NOTA_COM if com_petro else NOTA_EX
        arqs = []
        for i, (rot, x) in enumerate(mats.items(), 1):
            tit = f"Exportações {'com petróleo' if com_petro else 'ex-petróleo'} por produto e destino - {rot}"
            if x["parcial"]:
                tit += f" ({x['n']} meses)"
            arq = pasta / f"{i}_brasil_exp_sankey_{x['slug']}{sufixo}.png"
            arqs.append(desenhar(x["m"], ordem_p, ordem_d, k, tit, nota, arq))
            print(f"  {arq.relative_to(GRAFICOS)}  total {x['m'].values.sum():.2f} bi/mês")
            t = x["m"].stack().rename("us_bi_mes").reset_index()
            t.insert(0, "periodo", rot)
            t.insert(0, "versao", "com_petroleo" if com_petro else "ex_petroleo")
            tabela.append(t)
        print(f"  painel: {painel(arqs, pasta / f'todos_sankey{sufixo}.png').relative_to(GRAFICOS)}")
    saida = DADOS / "sankey" / "sankey_periodos.csv"
    pd.concat(tabela).to_csv(saida, index=False, encoding="utf-8-sig")
    print(f"  tabela: {saida}  (dados até {ult})")


if __name__ == "__main__":
    sys.exit(main())
