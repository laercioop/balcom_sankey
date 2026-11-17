"""Histórico mensal dos destinos dos Sankeys, em % das exportações.

Uso: python codigos/series_destinos.py
Sete grupos de destino principais nos últimos 12 meses (ranking ex-petróleo
fixo nas duas versões); restante em Outros. Mesma dessazonalização direta por produto x destino
e definição de petróleo de sankey.py. Não realiza downloads.
"""
import json
import argparse
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
from sankey import carregar, COR_DEST, DEMAIS_DEST
from comum import DADOS, PASTAS_DADOS, GRAFICOS
from estilo_ps import (make_figure, style_axes, plot_series, GRID,
                       LEGEND_FONT4, add_title_aligned, add_ylabel,
                       set_xaxis_years_centered, save_chart, PALETTE)


def desenhar(pct, pasta, com_petroleo, area, destino=None, cores_prod=None, slug='destinos', numero=None, mm3m=False):
    fig, ax = make_figure()
    pos = ax.get_position()
    ax.set_position([pos.x0, pos.y0, .56, pos.height])
    style_axes(ax)
    x = np.array([(p.year - 2000) * 12 + p.month - 1 for p in pct.index])
    cores = [(cores_prod or COR_DEST).get(c, GRID) for c in pct.columns]
    if area:
        ax.stackplot(x, pct.T.values, colors=cores, labels=pct.columns,
                     linewidth=.25, edgecolor='white')
        ax.set_ylim(0, 100)
        ax.set_yticks(range(0, 101, 20))
    else:
        for c, cor in zip(pct.columns, cores):
            plot_series(ax, x, pct[c].values, cor, label=c, smooth_line=False, lw=1.8)
        ax.set_ylim(bottom=0)
    anos = range(pct.index[0].year, pct.index[-1].year + 1)
    set_xaxis_years_centered(ax, [(a-2000)*12 for a in anos], [a if len(anos) <= 10 or (a % 5 == 0 and anos[-1] - a >= 2) or a in (anos[0], anos[-1]) else '' for a in anos],
                             x[-1], year_span=12, x_start=x[0])
    h, l = ax.get_legend_handles_labels()
    if destino:
        import textwrap
        l = [textwrap.fill(t, width=23) for t in l]
    if area:
        h, l = h[::-1], l[::-1]
    ax.legend(h, l, loc='center left', bbox_to_anchor=(1.02, .5),
              frameon=False, prop=LEGEND_FONT4, handlelength=1.3,
              labelspacing=.4, borderaxespad=0)
    ylabel = '% ao destino, dessaz.' if destino else '% das exportações, dessaz.'
    if mm3m:
        ylabel += ' MM3M'
    add_ylabel(ax, ylabel, outside=area)
    titulo = 'Brasil - destinos com petróleo' if com_petroleo else 'Brasil - destinos ex-petróleo'
    if destino:
        titulo = f"Brasil para {destino} - {'com petróleo' if com_petroleo else 'ex-petróleo'}"
    add_title_aligned(fig, ax, titulo, fontsize=12)
    return save_chart(fig, pasta, numero if numero is not None else (1 if area else 2),
                      f'brasil_exp_{slug}_area' if area else f'brasil_exp_{slug}_series')


def por_destino(d, corte, somente=None):
    """Composição por produto: 100% = exportações ao destino na versão."""
    registros = []
    destinos = [('China', 'China', '7_exp_brasil_para_china', 'china'),
                ('União Europeia', 'UE', '8_exp_brasil_para_UE', 'ue'),
                ('EUA', 'EUA', '9_exp_brasil_para_EUA', 'eua')]
    for nome, titulo, pasta_nome, slug in destinos:
        if somente and nome not in somente:
            continue
        dest = d[d.destino == nome]
        # Ranking comum às duas versões, incluindo petróleo para que este
        # possa aparecer entre os principais produtos na versão completa.
        ranking = dest[(dest.date >= corte) & (dest.produto != 'Demais produtos')].groupby('produto').valor_sa.sum()
        principais = ranking.nlargest(7).index.tolist()
        cores = dict(zip(principais, [PALETTE[i] for i in (0, 1, 2, 4, 5, 6, 8)]))
        cores['Outros'] = GRID
        for com in (False, True):
            base = dest if com else dest[dest.petro.isna()]
            val = base.pivot_table(index='date', columns='produto', values='valor_sa',
                                   aggfunc='sum', fill_value=0)
            agrup = val.reindex(columns=principais, fill_value=0).copy()
            agrup['Outros'] = val.drop(columns=principais, errors='ignore').sum(axis=1)
            agrup = agrup.loc[:, agrup.sum() > 0]
            np.testing.assert_allclose(agrup.sum(axis=1), val.sum(axis=1), atol=1)
            pct = agrup.div(val.sum(axis=1), axis=0) * 100
            np.testing.assert_allclose(pct.sum(axis=1), 100, atol=1e-9)
            assert np.isfinite(pct.values).all() and (pct.values >= 0).all()
            pct.index = pd.PeriodIndex(pct.index, freq='M')
            assert len(pct) == len(pd.period_range(pct.index.min(), pct.index.max(), freq='M'))
            pasta = GRAFICOS / pasta_nome
            if com:
                pasta = pasta / 'com_petroleo'
            for area in (True, False):
                print(desenhar(pct, pasta, com, area, titulo, cores, slug))
            tab = pct.rename_axis('date').reset_index().melt('date', var_name='produto', value_name='participacao_pct')
            tab['destino'] = nome
            tab['versao'] = 'com_petroleo' if com else 'ex_petroleo'
            registros.append(tab)
        texto = (f'# Exportações do Brasil para {nome}\n\n'
                 'Séries mensais dessazonalizadas por produto, em % do total enviado ao destino. '
                 f'Sem média móvel. Exibição desde {dest.date.min()}, estimação desde 1997 ou início admissível de cada série.\n\n'
                 'Nesta pasta: ex-petróleo (exclui HS 2709–2715). Em `com_petroleo/`: inclui petróleo. '
                 'Gráfico 1: área; gráfico 2: linhas. Classificação e ajuste direto produto x destino iguais aos Sankeys. '
                 'Até sete produtos principais pelo valor dos últimos 12 meses com petróleo, '
                 'ranking fixo e cores iguais nas duas versões; demais em Outros.\n\n'
                 'Gerador: `python codigos/series_destinos.py`. '
                 'Dados: `dados/sankey/series_produtos_destinos.csv`.\n')
        (GRAFICOS / pasta_nome / 'README.md').write_text(texto, encoding='utf-8')
    saida = pd.concat(registros)
    assert not saida.duplicated(['date', 'produto', 'destino', 'versao']).any()
    arquivo = DADOS / 'sankey' / 'series_produtos_destinos.csv'
    if somente and arquivo.exists():
        anterior = pd.read_csv(arquivo)
        saida = pd.concat([anterior[~anterior.destino.isin(somente)], saida], ignore_index=True)
    saida.to_csv(arquivo, index=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--inicio', default='2015-01', help='Início da exibição; não altera o histórico de estimação.')
    a = ap.parse_args()
    d, ult = carregar()
    d = d[d.date >= a.inicio].copy()
    meses = pd.period_range(d.date.min(), ult, freq='M')
    if set(d.date) != set(meses.astype(str)):
        raise RuntimeError('Há lacunas mensais na base.')
    # Conferência independente dos totais originais contra o pipeline HS2.
    hs = pd.read_csv(PASTAS_DADOS['brasil'] / 'brasil_hs2.csv', dtype={'hs2': str})
    assert not hs.duplicated(['date', 'fluxo', 'hs2']).any()
    hs = hs[hs.fluxo == 'exp']
    cap = hs[hs.hs2 != 'TOTAL'].groupby('date').valor.sum()
    ref = hs[hs.hs2 == 'TOTAL'].set_index('date').valor
    if ref.empty:
        ref = cap
    else:
        np.testing.assert_allclose(cap.reindex(ref.index), ref, rtol=1e-9, atol=1)
    raw = d.groupby('date').VL_FOB.sum()
    comum = raw.index.intersection(ref.index)
    np.testing.assert_allclose(raw.loc[comum], ref.loc[comum], rtol=1e-9, atol=1)
    ex = d[d.petro.isna()]
    corte = str(meses[-1] - 11)
    ranking = ex[(ex.date >= corte) & (ex.destino != DEMAIS_DEST)].groupby('destino').valor_sa.sum()
    principais = ranking.nlargest(7).index.tolist()
    registros = []
    for com in (False, True):
        base = d if com else ex
        val = base.pivot_table(index='date', columns='destino', values='valor_sa',
                               aggfunc='sum', fill_value=0)
        agrup = val.reindex(columns=principais, fill_value=0).copy()
        agrup['Outros'] = val.drop(columns=principais, errors='ignore').sum(axis=1)
        pct = agrup.div(val.sum(axis=1), axis=0) * 100
        np.testing.assert_allclose(pct.sum(axis=1), 100, atol=1e-9)
        assert np.isfinite(pct.values).all() and (pct.values >= 0).all()
        pct.index = pd.PeriodIndex(pct.index, freq='M')
        pasta = GRAFICOS / '6_series_históricas'
        if com:
            pasta = pasta / 'com_petroleo'
        for area in (True, False):
            print(desenhar(pct, pasta, com, area))
        tab = pct.rename_axis('date').reset_index().melt('date', var_name='destino', value_name='participacao_pct')
        tab['versao'] = 'com_petroleo' if com else 'ex_petroleo'
        registros.append(tab)
    pd.concat(registros).to_csv(DADOS / 'sankey' / 'series_destinos.csv', index=False)
    info = {'inicio': str(meses[0]), 'ultimo_mes': ult, 'ranking_inicio': corte,
            'principais': principais, 'ultimo_total_original_usd': float(raw.iloc[-1]),
            'erro_max_total_hs2_usd': float((raw-ref.reindex(raw.index)).abs().max())}
    (DADOS / 'sankey' / 'validacao_series_destinos.json').write_text(
        json.dumps(info, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(info, ensure_ascii=False, indent=2))
    por_destino(d, corte)


if __name__ == '__main__':
    main()
