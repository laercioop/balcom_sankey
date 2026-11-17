"""Níveis mensais Brasil/EUA e mundo; acumulado 12m exibido seis meses antes."""
import json
import textwrap
import re
import unicodedata
import numpy as np
import pandas as pd
from comum import DADOS, GRAFICOS
from dessaz import ajustar, config
from dessaz_destinos import feriados, fontes
from estilo_ps import (make_figure, style_axes, plot_series, GRID, BLUE,
                       set_xaxis_years_centered, add_ylabel, add_title_aligned,
                       save_chart, LEGEND_FONT4)

BASE = DADOS / 'sankey'


def main():
    tabela = pd.read_excel(BASE / 'brutos/TABELAS_AUXILIARES.xlsx', sheet_name='16')
    assert not tabela.CO_NCM.duplicated().any()
    extr = tabela[tabela.CO_ISIC_SECAO == 'B'].copy()
    extr['ncm'] = extr.CO_NCM.astype(str).str.zfill(8)
    nomes = dict(zip(extr.ncm, extr.NO_CUCI_GRUPO))
    def grupo(ncm):
        if ncm.startswith('2709'):
            return 'Petróleo bruto'
        nome = nomes[ncm].lower()
        if 'ferro e seus' in nome:
            return 'Minério de ferro'
        if 'cobre e seus' in nome:
            return 'Minério de cobre'
        if any(p in nome for p in ('metais', 'níquel', 'alumínio', 'urânio', 'tório')):
            return 'Outros minérios metálicos'
        if any(p in nome for p in ('gás', 'carvão', 'linhita', 'turfa')):
            return 'Gás, carvão e outros energéticos'
        return 'Minerais não metálicos'
    mapa = {n: grupo(n) for n in nomes}
    partes = []
    for p in sorted((BASE / 'brutos').glob('exp_pais_ncm_*.csv.gz')):
        for d in pd.read_csv(p, dtype={'CO_NCM': str}, chunksize=300000):
            assert not d.duplicated(['CO_ANO', 'CO_MES', 'CO_PAIS', 'CO_NCM']).any()
            d['date'] = d.CO_ANO.astype(str) + '-' + d.CO_MES.map('{:02d}'.format)
            d['grupo'] = d.CO_NCM.map(mapa)
            for destino, b in [('EUA', d[d.CO_PAIS.isin([249, 611])]), ('Mundo', d)]:
                total = b.groupby('date').VL_FOB.sum().rename('valor').reset_index()
                total['serie'] = 'Exportações totais'
                comp = b[b.grupo.notna()].groupby(['date', 'grupo']).VL_FOB.sum().rename('valor').reset_index().rename(columns={'grupo': 'serie'})
                q = pd.concat([total, comp], ignore_index=True)
                q['destino'] = destino
                partes.append(q)
        print(p.name, flush=True)
    raw = pd.concat(partes).groupby(['destino', 'date', 'serie']).valor.sum().reset_index()
    raw.to_csv(BASE / 'extrativa_originais_eua_mundo.csv', index=False)
    idx = pd.period_range(raw.date.min(), raw.date.max(), freq='M')
    cfg = config('brasil')
    cfg['arquivo'] = feriados(idx[0], idx[-1])
    saida, diagnosticos = [], []
    for destino in ['EUA', 'Mundo']:
        pasta = GRAFICOS / '9_exp_brasil_para_EUA' / ('niveis_mensais' if destino == 'EUA' else 'total_brasil')
        pasta.mkdir(parents=True, exist_ok=True)
        val = raw[raw.destino == destino].pivot(index='date', columns='serie', values='valor').reindex(idx.astype(str)).fillna(0)
        componentes = [c for c in val if c != 'Exportações totais']
        val['Indústria extrativa'] = val[componentes].sum(axis=1)
        ordem = ['Exportações totais', 'Petróleo bruto', 'Indústria extrativa'] + [c for c in componentes if c != 'Petróleo bruto']
        for numero, serie in enumerate(ordem, 3):
            s = pd.Series(val[serie].values, index=idx)
            # A janela pode começar após zeros antigos, mas precisa cobrir 2010.
            candidatos = [i for i in range(len(idx)) if idx[i] <= pd.Period('2010-01') and (i == 0 or idx[i].month == 1)]
            dg = {'status': 'sem janela admissível'}
            for ini in candidatos:
                _, sa, dg = ajustar(s.iloc[ini:], cfg, serie, [], exigir_nao_negativo=True)
                if dg['status'].startswith('ok'):
                    break
            spec = dg.pop('spec', None)
            ascii_nome = unicodedata.normalize('NFKD', serie).encode('ascii', 'ignore').decode().lower()
            slug = re.sub(r'[^a-z0-9]+', '_', ascii_nome).strip('_')
            if spec:
                (pasta / f'{numero}_{slug}.spc').write_text(spec, encoding='latin-1')
            diagnosticos.append(dict(destino=destino, serie=serie, inicio_ajuste=str(sa.index[0]), **dg))
            if not dg['status'].startswith('ok'):
                print('SEM GRÁFICO DESSAZ:', destino, serie, dg['status'], flush=True)
                continue
            tab = pd.DataFrame({'original_usd': s, 'mensal_sa_usd': sa, 'acumulado_12m_usd': s.rolling(12, min_periods=12).sum()})
            tab['data_exibicao_12m'] = (tab.index - 6).astype(str)
            tab['destino'], tab['serie'] = destino, serie
            saida.append(tab.rename_axis('date').reset_index())
            fig, ax = make_figure()
            style_axes(ax)
            x = np.array([(p.year - 2000) * 12 + p.month - 1 for p in idx])
            vis = idx >= pd.Period('2010-01')
            plot_series(ax, x[vis], tab.mensal_sa_usd.values[vis] * 12 / 1e9, GRID,
                        label='Mensal anualizado dessazonalizado', smooth_line=False, lw=1.5)
            azul = (idx - 6 >= pd.Period('2010-01')) & tab.acumulado_12m_usd.notna().values
            plot_series(ax, x[azul] - 6, tab.acumulado_12m_usd.values[azul] / 1e9, BLUE,
                        label='Acumulado em 12 meses', smooth_line=False, lw=2.0)
            ax.set_ylim(bottom=0, top=max(tab.mensal_sa_usd.values[vis].max()*12, tab.acumulado_12m_usd.values[azul].max())/1e9*1.35)
            anos = list(range(2010, idx[-1].year + 1))
            set_xaxis_years_centered(ax, [(a-2000)*12 for a in anos], [str(a) if a % 2 == 0 else '' for a in anos], x[-1], year_span=12, x_start=120)
            ax.legend(loc='upper left', bbox_to_anchor=(.035,.99), frameon=False, prop=LEGEND_FONT4, handlelength=2.5)
            add_ylabel(ax, 'US$ bilhões', ypos=.5)
            titulo = serie + (' - EUA' if destino == 'EUA' else ' - Brasil')
            add_title_aligned(fig, ax, '\n'.join(textwrap.wrap(titulo, 44)), fontsize=12)
            print(save_chart(fig, pasta, numero, slug), flush=True)
        (pasta / 'README.md').write_text('Séries mensais desde jan/2010, US$ bilhões FOB. Cinza: mensal dessazonalizado × 12. Azul: soma dos valores originais em 12 meses, deslocada em -6 meses apenas na exibição; sem extrapolação. X-13 direto por série; total extrativo ajustado diretamente, podendo diferir da soma dos componentes ajustados. Petróleo = bruto (HS 2709). Extrativa = seção B da ISIC na tabela oficial MDIC, aba 16; componentes agrupados por CUCI. EUA inclui Porto Rico, conforme pasta 9. Histórico de estimação desde 1997 ou primeiro janeiro admissível até 2010. Séries sem ajuste válido não geram PNG; consultar diagnósticos. Calendário prioritário cobre 2024–2030; fora dessa cobertura usam-se regras gregorianas do gerador existente.\n', encoding='utf-8')
    resultados = pd.concat(saida)
    assert not resultados.duplicated(['date', 'destino', 'serie']).any()
    visiveis = resultados[resultados.date.astype(str) >= '2010-01']
    assert np.isfinite(visiveis[['original_usd', 'mensal_sa_usd']]).all().all()
    assert (visiveis.mensal_sa_usd >= 0).all()
    for _, g in resultados.groupby(['destino', 'serie']):
        np.testing.assert_allclose(g.acumulado_12m_usd, g.original_usd.rolling(12).sum(), equal_nan=True)
        assert ((pd.PeriodIndex(g.date, freq='M') - 6).astype(str) == g.data_exibicao_12m).all()
    resultados.to_csv(BASE / 'series_extrativa_eua_mundo.csv', index=False)
    pd.DataFrame(diagnosticos).to_csv(BASE / 'diagnostico_extrativa_eua_mundo.csv', index=False)
    extr.to_csv(BASE / 'classificacao_extrativa.csv', index=False)
    (BASE / 'validacao_extrativa_eua_mundo.json').write_text(json.dumps(dict(ultimo_mes=str(idx[-1]), shift_12m_meses=-6, series_com_grafico=len(saida), duplicatas=0, acumulados_conferidos=True, fontes=fontes()), ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
