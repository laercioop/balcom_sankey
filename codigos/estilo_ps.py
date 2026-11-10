"""Helpers Focus/PS. Scripts Python e PNGs numerados; regras em SKILL.md."""
from pathlib import Path
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator
from matplotlib.font_manager import FontProperties
from scipy.interpolate import Akima1DInterpolator

# ── Canvas & DPI ──────────────────────────────────────────────────────────────
FIG_W_IN, FIG_H_IN = 5.0, 3.0        # paisagem 5in x 3in
DPI_EXPORT = 300                     # 1500 x 900 px

# ── Paleta (10 cores + apoios) ────────────────────────────────────────────────
# Ordem canonical 2026-07-02: 4ª cor = cinza, dourado passou a 5ª. SOB REVISÃO.
BLUE       = "#4a7fb5"   # 1  série principal / IPCA / atual
TERRACOTTA = "#cd6252"   # 2  segunda série / Livres / anterior
GREEN_CYAN = "#5c9478"   # 3  terceira série / Administrados
GRAY       = "#808080"   # 4  quarta série (também bordas/ticks estruturais)
GOLDEN     = "#b29234"   # 5
GREEN      = "#65a356"   # 6
PURPLE     = "#796cb7"   # 7
RED_LIGHT  = "#dc7878"   # 8
PINK       = "#c285a3"   # 9
GRAY_DARK  = "#515151"   # 10 (também cor do título)
PALETTE = [BLUE, TERRACOTTA, GREEN_CYAN, GRAY, GOLDEN,
           GREEN, PURPLE, RED_LIGHT, PINK, GRAY_DARK]

GRID       = "#bcbcbc"   # cinza secundário: grade/meta/série bruta/apoio
TITLE_GRAY = "#515151"   # título
DOTTED     = (0, (1.6, 1.6))   # pontilhado padrão (preservar do original)
LW_MAIN    = 2.4               # espessura da série principal (era 2.8; levemente mais fina)
LW_RAW     = 1.5               # série bruta / histórico diário longo
CAP        = "round"           # pontas e junções levemente arredondadas

# ── Geometria fixa (nunca usar tight/constrained layout) ──────────────────────
AX_LEFT, AX_BOTTOM, AX_WIDTH, AX_HEIGHT = 0.11, 0.150, 0.82, 0.720

# ── Tipografia ────────────────────────────────────────────────────────────────
mpl.rcParams.update({
    "font.family": "Arial",
    "font.sans-serif": ["Arial", "DejaVu Sans"],
    "font.size": 8,
    "axes.unicode_minus": True,
    "svg.fonttype": "none",
})
FS_TITLE, FS_YLABEL, FS_TICK = 16.0, 7.0, 7.2  # ylabel menor (era 8.0)
TITLE_FONT   = FontProperties(family="Segoe UI", weight="bold",   size=16)  # 12 se legenda longa no topo
LEGEND_FONT  = FontProperties(family="Segoe UI", weight="normal", size=9)    # 7.5 se >= 4 séries
LEGEND_FONT4 = FontProperties(family="Segoe UI", weight="normal", size=7.5)


# ── Figura & eixos ────────────────────────────────────────────────────────────
def make_figure():
    """Canvas fixo de 1500 x 900 px, com espaço para o título."""
    fig = plt.figure(figsize=(FIG_W_IN, FIG_H_IN), dpi=DPI_EXPORT)
    fig.patch.set_facecolor("white")
    ax = fig.add_axes([AX_LEFT, AX_BOTTOM, AX_WIDTH, AX_HEIGHT])
    ax.set_facecolor("white")
    return fig, ax


def style_axes(ax):
    # Sem moldura em cima/direita/esquerda; só a linha inferior (eixo X).
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_visible(True)
    ax.spines["bottom"].set_color(GRAY)
    ax.spines["bottom"].set_linewidth(0.75)
    ax.yaxis.grid(False)          # grade SEMPRE desligada
    ax.xaxis.grid(False)
    ax.set_axisbelow(True)
    ax.tick_params(axis="both", which="major", length=3.5, width=0.65,
                   color=GRAY, labelsize=FS_TICK, labelcolor="#404040")
    ax.tick_params(axis="x", which="minor", length=3.0, width=0.55, color=GRAY)


# ── Eixo X: anos centralizados entre os riscos ────────────────────────────────
def set_xaxis_years_centered(ax, tick_pos, tick_labels, x_end,
                             year_span=4, x_start=None, left_pad=None, right_pad=None):
    """Anos no centro calendário; pontas parciais sem divisórias artificiais.

    tick_pos: inícios reais de cada ano; year_span na unidade numérica de X.
    Inclua o início anterior à janela quando o primeiro ano for parcial.
    x_start/x_end são limites dos dados. Margens não extrapolam as séries:
    direita = três meses; esquerda = até um mês ou 1.5% da janela.
    left_pad/right_pad permitem ajustes explícitos, na unidade de X.
    """
    starts = np.asarray(tick_pos, dtype=float)
    if len(starts) != len(tick_labels) or not len(starts):
        raise ValueError("Forneça um início real para cada rótulo de ano.")
    if year_span <= 0 or np.any(np.diff(starts) <= 0):
        raise ValueError("Duração positiva e inícios em ordem crescente.")
    data_start = float(starts[0] if x_start is None else x_start)
    data_end = float(x_end)
    if data_end <= data_start:
        raise ValueError("O fim deve ser posterior ao início.")
    left_pad = min(year_span / 12, (data_end-data_start)*.015) if left_pad is None else float(left_pad)
    right_pad = year_span / 4 if right_pad is None else float(right_pad)
    if not np.isfinite([left_pad, right_pad]).all() or min(left_pad, right_pad) < 0:
        raise ValueError("Margens devem ser finitas e não negativas.")
    left, right = data_start-left_pad, data_end+right_pad
    ax.set_xlim(left, right)
    boundaries = np.unique(np.r_[starts, starts[-1] + year_span])
    boundaries = boundaries[(boundaries >= left) & (boundaries <= right)]
    ax.set_xticks(boundaries)
    ax.set_xticklabels([""] * len(boundaries))
    for start, label in zip(starts, tick_labels):
        end = start + year_span
        if end <= left or start >= right:
            continue
        artist = ax.text((start + end) / 2, -0.04, str(label),
                         transform=ax.get_xaxis_transform(), ha="center", va="top",
                         fontsize=FS_TICK, color="#404040", clip_on=False)
        # Conserva o centro calendário, deslocando só para caber na janela.
        ax.figure.canvas.draw()
        half_width = artist.get_window_extent().width / 2 + 2
        lo_px = ax.transData.transform((left, 0))[0] + half_width
        hi_px = ax.transData.transform((right, 0))[0] - half_width
        ideal_px = ax.transData.transform(((start + end) / 2, 0))[0]
        pos_px = np.clip(ideal_px, lo_px, hi_px)
        artist.set_x(ax.transData.inverted().transform((pos_px, 0))[0])


def add_title(ax, title, x=0.0, fontsize=FS_TITLE):
    """Título único, sem subtítulo ou numeração; use hífen normal."""
    if "\n" in title:
        raise ValueError("Título deve ter uma única linha, sem subtítulo.")
    title = title.replace("—", "-").replace("–", "-")
    return ax.text(x, 1.03, title, transform=ax.transAxes, ha="left", va="bottom",
                   family="Segoe UI", weight="bold", fontsize=fontsize,
                   color=TITLE_GRAY, clip_on=False)


def align_title_x(fig, ax):
    """x (em axes coords) da borda esquerda do rótulo do MAIOR valor do eixo Y
    (ex.: com [50..250] -> borda do '2' de 250; com [-4..4] -> borda do '4', não do '-4').
    Chamar DEPOIS de definir ylim/locator e plotar as séries."""
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    inv = ax.transAxes.inverted()
    lo, hi = min(ax.get_ylim()), max(ax.get_ylim())
    best_val, best_x = None, 0.0
    for tick, lbl in zip(ax.get_yticks(), ax.get_yticklabels()):
        if not lbl.get_text() or not (lo - 1e-9 <= tick <= hi + 1e-9):
            continue                       # ignora ticks vazios ou fora do range visível
        if best_val is None or tick > best_val:
            best_val = tick
            best_x = inv.transform((lbl.get_window_extent(r).x0, 0))[0]
    return best_x

def add_title_aligned(fig, ax, title, fontsize=FS_TITLE):
    return add_title(ax, title, x=align_title_x(fig, ax), fontsize=fontsize)


def add_ylabel(ax, text, ypos=0.5, outside=False):
    """Rótulo interno sem colisão com séries; fallback externo se necessário.

    Chame depois de plotar todas as séries e fixar limites e layout.
    A caixa renderizada do texto é comparada com os caminhos renderizados
    das linhas, considerando a espessura do traço e uma folga de 2 px.
    """
    from matplotlib.transforms import Bbox

    def external():
        return ax.set_ylabel(text, fontsize=FS_YLABEL, color="#404040",
                             labelpad=3.5, rotation=90)

    if outside:
        return external()
    artist = ax.text(0.025, ypos, text, transform=ax.transAxes, rotation=90,
                     ha="center", va="center", fontsize=FS_YLABEL,
                     color="#404040")
    ax.figure.canvas.draw()
    renderer = ax.figure.canvas.get_renderer()
    candidates = list(dict.fromkeys([ypos, .5, .8, .2, .65, .35, .9, .1]))
    for candidate in candidates:
        artist.set_position((0.025, candidate))
        box = artist.get_window_extent(renderer)
        # O rótulo deve caber inteiramente dentro da área útil.
        if (box.x0 < ax.bbox.x0 + 2 or box.x1 > ax.bbox.x1 - 2 or
                box.y0 < ax.bbox.y0 + 2 or box.y1 > ax.bbox.y1 - 2):
            continue
        collision = False
        for line in ax.lines:
            if not line.get_visible() or line.get_alpha() == 0:
                continue
            padding = 2 + line.get_linewidth() * ax.figure.dpi / 144
            padded = Bbox.from_extents(box.x0-padding, box.y0-padding,
                                       box.x1+padding, box.y1+padding)
            path = line.get_transform().transform_path(line.get_path())
            if path.intersects_bbox(padded, filled=False):
                collision = True
                break
        if collision:
            continue
        # Também evite a legenda, quando já tiver sido posicionada.
        legend = ax.get_legend()
        if legend is not None and legend.get_visible():
            if box.overlaps(legend.get_window_extent(renderer)):
                continue
        return artist
    artist.remove()
    return external()


def add_comment(ax, text, xy=(0.98, 0.08), ha="right"):
    """Comentário opcional em caixa discreta; nunca rodapé automático."""
    return ax.text(*xy, text, transform=ax.transAxes, ha=ha, va="bottom",
                   fontsize=6.5, color=GRID, fontstyle="italic",
                   bbox=dict(facecolor="white", edgecolor="none", alpha=0.85, pad=2))


# ── Suavização (default: Akima misturado com linear) ──────────────────────────
def smooth(x_orig, y_orig, factor=10, blend=0.5):
    """blend=1 -> totalmente Akima; blend=0 -> retas. factor=1 -> pontos ligados
    por reta (usar em projeções ponto a ponto, sem distorção)."""
    x_orig = np.asarray(x_orig, float)
    y_orig = np.asarray(y_orig, float)
    if factor == 1:
        return x_orig, y_orig
    x_fine = np.linspace(x_orig[0], x_orig[-1], len(x_orig) * factor)
    y_akima  = Akima1DInterpolator(x_orig, y_orig)(x_fine)
    y_linear = np.interp(x_fine, x_orig, y_orig)
    return x_fine, blend * y_akima + (1 - blend) * y_linear


def plot_series(ax, x, y, color, label=None, ls="-", lw=None, smooth_line=True,
                blend=0.5, factor=10):
    """Plota uma série no estilo canonical: espessura LW_MAIN, pontas/junções
    arredondadas (CAP) e suavização Akima. Use no lugar de ax.plot direto."""
    lw = LW_MAIN if lw is None else lw
    if smooth_line:
        x, y = smooth(x, y, factor=factor, blend=blend)
    return ax.plot(x, y, color=color, linestyle=ls, linewidth=lw, label=label,
                   solid_capstyle=CAP, solid_joinstyle=CAP, dash_capstyle=CAP)


# ── Legenda ───────────────────────────────────────────────────────────────────
def eviews_legend(ax, bbox, ncol=1, n_series=None):
    """Sem caixa, posição manual. Fonte 7.5 quando >= 4 séries (n_series)."""
    prop = LEGEND_FONT4 if (n_series and n_series >= 4) else LEGEND_FONT
    loc = "upper right" if bbox[1] > 0.5 else "lower right"
    return ax.legend(loc=loc, bbox_to_anchor=bbox, frameon=False, ncol=ncol,
                     prop=prop, handlelength=3.0, handletextpad=0.45,
                     labelspacing=0.55, borderaxespad=0.0)


# Exportação de um PNG numerado por gráfico.
def save_chart(fig, out_dir, n, slug):
    """Salva PNG numerado, recortando só margens externas com folga de 0.025 in.

    Mantém o espaço vazio intencional dentro do eixo; não altera seu layout.
    """
    import re
    if not isinstance(n, int) or n < 1:
        raise ValueError("O número do gráfico deve ser inteiro positivo.")
    if not re.fullmatch(r"[a-z0-9]+(?:_[a-z0-9]+)*", slug):
        raise ValueError("Use slug ASCII minúsculo com underscores.")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{n}_{slug}.png"
    fig.savefig(path, dpi=DPI_EXPORT, facecolor="white",
                bbox_inches="tight", pad_inches=0.025)
    plt.close(fig)
    return path
