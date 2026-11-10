"""Compacta o cruzamento oficial produto x país, sem estimar vínculos.

Brasil: arquivos anuais já baixados pelo BALCOM. Não faz downloads.
O detalhe mensal usa valores originais; 12m exige doze meses completos.
"""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from comum import DADOS, PASTAS_DADOS, MAPA_GRANULAR

BASE = DADOS / 'balanca_sankey'


def preparar():
    saida = BASE / 'brasil_produto_pais.json'
    pasta = PASTAS_DADOS['brasil'].parent / 'balcom_r/downloads'
    arquivos = sorted(pasta.glob('EXP_*.csv')) + sorted(pasta.glob('IMP_*.csv'))
    aux = DADOS / 'sankey/brutos/paises.csv'
    # O JSON compacto também permite regenerar a publicação sem caminhos locais.
    if not arquivos:
        return
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in arquivos + [aux, BASE / 'brasil_produtos.csv', BASE / 'brasil_parceiros.csv', Path(__file__)]}
    if saida.exists() and json.loads(saida.read_text(encoding='utf-8')).get('hashes') == hashes:
        return
    paises = pd.read_csv(aux).set_index('CO_PAIS')
    nomes = paises.NO_PAIS.to_dict()
    eu = set('AUT BEL BGR HRV CYP CZE DNK EST FIN FRA DEU GRC HUN IRL ITA LVA LTU LUX MLT NLD POL PRT ROU SVK SVN ESP SWE'.split())
    principais = set(pd.read_csv(BASE / 'brasil_parceiros.csv').serie) - {'Demais parceiros'}
    blocos = {code: ('União Europeia' if row.CO_PAIS_ISOA3 in eu else
                    row.NO_PAIS if row.NO_PAIS in principais else 'Demais parceiros')
              for code, row in paises.iterrows()}
    partes = []
    for p in arquivos:
        fluxo = p.name[:3].lower()
        for c in pd.read_csv(p, sep=';', encoding='latin1', dtype={'CO_NCM': str},
                             usecols=['CO_ANO', 'CO_MES', 'CO_NCM', 'CO_PAIS', 'VL_FOB'], chunksize=500000):
            c['date'] = c.CO_ANO.astype(str) + '-' + c.CO_MES.astype(str).str.zfill(2)
            c['produto'] = c.CO_NCM.str.zfill(8).str[:2].astype(int).map(MAPA_GRANULAR).fillna(MAPA_GRANULAR[99])
            c['pais'] = c.CO_PAIS.map(nomes).fillna('Não especificado')
            c['bloco'] = c.CO_PAIS.map(blocos).fillna('Demais parceiros')
            c['fluxo'] = fluxo
            partes.append(c.groupby(['date', 'fluxo', 'produto', 'pais', 'bloco']).VL_FOB.sum())
    d = pd.concat(partes).groupby(level=[0, 1, 2, 3, 4]).sum().rename('valor').reset_index()
    assert not d.duplicated(['date', 'fluxo', 'produto', 'pais']).any()
    assert np.isfinite(d.valor).all() and (d.valor >= 0).all()
    # Confere todos os meses comuns e o último mês contra a base oficial de produtos.
    ref = pd.read_csv(BASE / 'brasil_produtos.csv').set_index(['date', 'fluxo', 'serie']).valor
    calc = d.groupby(['date', 'fluxo', 'produto']).valor.sum()
    common = calc.index.intersection(ref.index)
    assert len(common) and np.allclose(calc.loc[common], ref.loc[common], rtol=1e-9, atol=2)
    assert d.date.max() == ref.index.get_level_values('date').max()
    d['valor'] /= 1e9
    out = dict(country='brasil', hashes=hashes, columns=list(d.columns), rows=d.values.tolist(),
               validacao=dict(duplicatas=0, produtos_conferidos=len(common), ultimo_mes=d.date.max(),
                              unidade='US$ bilhões', ajuste='original'))
    saida.write_text(json.dumps(out, ensure_ascii=False, allow_nan=False, separators=(',', ':')), encoding='utf-8')


def carregar():
    preparar()
    return {p.name.split('_')[0]: json.loads(p.read_text(encoding='utf-8'))
            for p in BASE.glob('*_produto_pais.json')}


if __name__ == '__main__':
    preparar()
