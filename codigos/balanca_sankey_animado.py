"""Gera a pasta 12: HTML offline dos 16 Sankeys da pasta 11 com histórico.

Uso: python codigos/balanca_sankey_animado.py
Não baixa nem reestima dados. Requer as bases auditadas da pasta 11.
"""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from balanca_sankey import BASE, NOMES, CORES_PARCEIROS, CORES_PROD, acumular
from comum import GRAFICOS

SAIDA = GRAFICOS / '12_sankey_animado'


def preparar():
    manifesto = json.loads((BASE / 'fontes.json').read_text(encoding='utf-8'))
    for item in manifesto.get('bases', []):
        p = BASE / Path(item['arquivo']).name
        assert hashlib.sha256(p.read_bytes()).hexdigest() == item['sha256'], p
    dados, validacao = {}, {}
    for pais, tipo, modo in [(p, t, m) for p in NOMES for t in ['parceiros', 'produtos'] for m in ['mensal', '12m']]:
        cores = CORES_PARCEIROS if tipo == 'parceiros' else CORES_PROD
        chave = '_'.join([pais, tipo, modo])
        arq = BASE / (pais + '_' + tipo + ('_sa' if modo == 'mensal' else '') + '.csv')
        d = pd.read_csv(arq)
        original = pd.read_csv(BASE / (pais + '_' + tipo + '.csv'))
        referencia, _, _ = acumular(original, '12m')
        ordem = list((referencia.exp + referencia.imp).sort_values(ascending=False).index)
        if 'Demais parceiros' in ordem:
            ordem.remove('Demais parceiros')
            ordem.append('Demais parceiros')
        assert not d.duplicated(['date', 'fluxo', 'serie']).any()
        assert set(d.fluxo) == {'exp', 'imp'}
        assert set(d.serie) == set(ordem)
        coluna = 'valor_sa' if modo == 'mensal' else 'valor'
        if modo == '12m' and 'valor_acum' in d:
            assert np.isfinite(d.valor_acum).all() and (d.valor_acum >= 0).all()
            assert (d[coluna].dropna() >= 0).all()
        else:
            assert np.isfinite(d[coluna]).all()
            assert (d[coluna] >= 0).all()
        quadros, excluidos = [], []
        for mes, g in d.groupby('date', sort=True):
            assert len(g) == 2 * len(ordem), (tipo, mes, 'mês incompleto')
            if modo == 'mensal' and 'ajustado' in g:
                assert set(g.ajustado.unique()) <= {True, False}
                if not g.ajustado.all():
                    excluidos.append(mes)
                    continue
            if modo == '12m':
                janela = pd.period_range(end=mes, periods=12, freq='M').astype(str)
                if not set(janela) <= set(d.date):
                    excluidos.append(mes)
                    continue
                if not np.isfinite(d.loc[d.date.isin(janela), 'valor']).all():
                    excluidos.append(mes)
                    continue
                p = pd.Period(mes, 'M')
                if 'valor_acum' in d and p.month != 12 and not {str(p-12), f'{p.year-1}-12'} <= set(d.date):
                    excluidos.append(mes)
                    continue
            m, ini, _ = acumular(d[d.date <= mes], modo)
            m = m.reindex(ordem)
            assert np.isfinite(m[['exp', 'imp']]).all().all()
            assert (m[['exp', 'imp']] >= 0).all().all()
            exp, imp = float(m.exp.sum()), float(m.imp.sum())
            saldo = exp - imp
            assert np.isclose(exp + max(-saldo, 0), imp + max(saldo, 0))
            quadros.append(dict(date=mes, start=ini, exp=m.exp.tolist(), imp=m.imp.tolist()))
        assert quadros
        meses = [q['date'] for q in quadros]
        if modo == 'mensal':
            assert meses == pd.period_range(meses[0], meses[-1], freq='M').astype(str).tolist()
        # Confronto do último quadro com a mesma função usada nos PNGs da pasta 11.
        ultimo, _, fim = acumular(d, modo)
        ultimo = ultimo.reindex(ordem)
        assert fim == meses[-1]
        assert np.allclose(quadros[-1]['exp'], ultimo.exp)
        assert np.allclose(quadros[-1]['imp'], ultimo.imp)
        dados[chave] = dict(country=pais, label=NOMES[pais], type=tipo, mode=modo,
                           currency='€' if pais == 'ue' else 'US$',
                           source=dict(brasil='MDIC', eua='Census / UN Comtrade',
                                       ue='Eurostat Comext', china='GACC / Bloomberg')[pais],
                           names=ordem, colors=[cores.get(n, '#bcbcbc') for n in ordem], frames=quadros)
        validacao[chave] = dict(inicio=meses[0], fim=meses[-1], meses=len(meses),
                               series=len(ordem), meses_sem_ajuste_excluidos=excluidos,
                               sha256_base=hashlib.sha256(arq.read_bytes()).hexdigest(),
                               exportacoes_fim_bi=sum(quadros[-1]['exp']),
                               importacoes_fim_bi=sum(quadros[-1]['imp']),
                               saldo_fim_bi=sum(quadros[-1]['exp'])-sum(quadros[-1]['imp']),
                               duplicatas=0, fechamento_validado=True,
                               ultimo_mes_confere_pasta_11=True)
    png = pd.read_csv(BASE / 'valores_graficos.csv')
    for chave, serie in dados.items():
        ref = png[(png.pais == serie['country']) & (png.tipo == serie['type']) & (png.periodo == serie['mode'])]
        assert len(ref) == len(serie['names']), chave
        ref = ref.set_index('serie').reindex(serie['names'])
        assert set(ref.fim) == {serie['frames'][-1]['date']}, chave
        for fluxo in ['exp', 'imp']:
            assert np.allclose(ref[fluxo], serie['frames'][-1][fluxo]), (chave, fluxo)
    return dados, validacao


def main():
    dados, validacao = preparar()
    template = Path(__file__).with_name('balanca_sankey_animado.html').read_text(encoding='utf-8')
    conteudo = template.replace('__DADOS_SANKEY__', json.dumps(dados, ensure_ascii=False, allow_nan=False))
    SAIDA.mkdir(parents=True, exist_ok=True)
    (SAIDA / 'brasil_sankey_mensal.html').write_text(conteudo, encoding='utf-8')
    (SAIDA / 'index.html').write_text(conteudo, encoding='utf-8')
    (SAIDA / '.nojekyll').touch()
    (SAIDA / 'validacao.json').write_text(json.dumps(validacao, ensure_ascii=False, indent=2), encoding='utf-8')
    print(SAIDA / 'brasil_sankey_mensal.html')
    for chave, v in validacao.items():
        print(chave, v['inicio'], v['fim'], v['meses'])


if __name__ == '__main__':
    main()
