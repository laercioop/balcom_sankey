"""Produto x parceiro: compactação auditável; coleta em coleta_cruzado.py.

O HTML só lê os JSONs prontos. Nenhum download é disparado pelo gerador.
Os valores são originais, na moeda da fonte, sem rateio de marginais.
"""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from comum import DADOS, MAPA_GRANULAR

BASE = DADOS / 'balanca_sankey'
CACHE = BASE / 'brutos/cruzado'
COLS = ['date', 'fluxo', 'produto', 'pais', 'bloco']
EU3 = set('AUT BEL BGR HRV CYP CZE DNK EST FIN FRA DEU GRC HUN IRL ITA LVA LTU LUX MLT NLD POL PRT ROU SVK SVN ESP SWE'.split())
EU2 = set('AT BE BG HR CY CZ DK EE FI FR DE EL GR HU IE IT LV LT LU MT NL PL PT RO SK SI ES SE'.split())
ASEAN = set('BN KH ID LA MY MM PH SG TH TL VN'.split())
NOMES = dict(US='EUA', CN='China', GB='Reino Unido', CH='Suíça', TR='Turquia',
             NO='Noruega', JP='Japão', KR='Coreia do Sul', IN='Índia', BR='Brasil',
             RU='Rússia', CA='Canadá', MX='México', HK='Hong Kong', VN='Vietnã',
             TW='Taiwan', SG='Singapura', AU='Austrália', ID='Indonésia', MY='Malásia',
             TH='Tailândia', SA='Arábia Saudita', AE='Emirados Árabes')


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def gravar_json(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix('.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, allow_nan=False, separators=(',', ':')), encoding='utf-8')
    tmp.replace(p)


def bloco(pais, codigo, nome, principais):
    if pais in ['brasil', 'eua', 'china'] and codigo in EU2 | EU3:
        return 'União Europeia'
    if pais == 'china' and codigo in ASEAN:
        return 'ASEAN'
    return nome if nome in principais else 'Demais parceiros'


def compactar(pais, d, fontes, cobertura, fonte):
    """Cobertura é explícita: só meses com toda a partição produto x país."""
    d = d.copy()
    assert not d.duplicated(COLS[:-1]).any(), 'Duplicatas no cruzamento'
    assert np.isfinite(d.valor).all() and (d.valor >= 0).all(), 'Valores inválidos'
    assert set(d.fluxo) <= {'exp', 'imp'}
    assert set(zip(d.date, d.fluxo)) <= set(map(tuple, cobertura))
    # Comparação independente com os produtos da pasta 11. Revisões/fontes
    # diferentes ficam explícitas; jamais reescalamos as células para escondê-las.
    ref = pd.read_csv(BASE / (pais + '_produtos.csv')).set_index(['date', 'fluxo', 'serie']).valor.dropna()
    calc = d.assign(produto=d.produto.replace({'Produto não detalhado':MAPA_GRANULAR[99]})).groupby(['date', 'fluxo', 'produto']).valor.sum()
    comum = calc.index.intersection(ref.index)
    delta = (calc.reindex(comum) - ref.reindex(comum)).abs()
    tolerancia = ref.reindex(comum).abs() * 1e-7 + 2
    divergentes = delta[delta > tolerancia]
    diagnostico = dict(duplicatas=0, produtos_conferidos=len(comum),
        divergencias_pasta11=len(divergentes), maior_diferenca_pasta11=float(delta.max()) if len(delta) else None,
        ultimo_mes=d.date.max(), primeiro_mes=d.date.min(), unidade='EUR' if pais == 'ue' else 'USD',
        ajuste='original', fonte=fonte,
        observacao='Comparação informativa entre versões/fontes; valores não rateados.')
    if len(divergentes):
        idx=divergentes.index
        comparacao=pd.DataFrame(dict(valor_cruzado=calc.reindex(idx).values,
            valor_pasta11=ref.reindex(idx).values,diferenca_absoluta=divergentes.values),
            index=idx.set_names(['date','fluxo','produto']))
        comparacao.to_csv(BASE/(pais+'_cruzado_divergencias.csv'))
    # Dicionários e partições por mês evitam repetir nomes e decodificar o
    # histórico inteiro em cada clique. Exportação CSV decodifica só a janela.
    dictionaries = {c: sorted(d[c].unique().tolist()) for c in COLS[1:]}
    for c, vals in dictionaries.items():
        d[c] = d[c].map({v: i for i, v in enumerate(vals)})
    d['valor'] = d.valor / 1e9
    partitions = {mes: g[COLS[1:] + ['valor']].values.tolist() for mes, g in d.groupby('date', sort=True)}
    fontes = list(fontes)+[BASE/(pais+'_produtos.csv'),BASE/(pais+'_parceiros.csv'),Path(__file__),Path(__file__).with_name('coleta_cruzado.py'),Path(__file__).with_name('comum.py')]
    if pais == 'eua':
        fontes.append(BASE/'brutos/census_country.xlsx')
    hashes = {p.name: sha(p) for p in fontes}
    out = dict(version=2, country=pais, dictionaries=dictionaries, months=partitions,
               coverage=sorted([list(x) for x in set(map(tuple, cobertura))]),
               hashes=hashes, validacao=diagnostico)
    gravar_json(BASE / (pais + '_produto_pais.json'), out)
    print(pais, diagnostico, flush=True)
    return out


def validar_payload(base):
    """Verifica a base portátil sem acessar brutos, fontes externas ou API."""
    if base.get('version') != 2:
        return
    dicts = base['dictionaries']
    assert set(dicts) == set(COLS[1:])
    assert all(len(v)==len(set(v)) for v in dicts.values()), 'Dicionário duplicado'
    coverage = {tuple(x) for x in base['coverage']}
    assert len(coverage)==len(base['coverage']), 'Cobertura duplicada'
    observed = set()
    for mes,rows in base['months'].items():
        vistos = set()
        for r in rows:
            assert len(r)==5 and np.isfinite(r).all() and r[4]>=0, 'Célula inválida'
            for j,c in enumerate(COLS[1:]):
                assert r[j]==int(r[j]) and 0<=r[j]<len(dicts[c]), 'Índice inválido'
            key = tuple(r[:3])
            assert key not in vistos, 'Produto/país duplicado no mês/fluxo'
            vistos.add(key)
            observed.add((mes,dicts['fluxo'][int(r[0])]))
    assert observed==coverage, 'Cobertura não corresponde às células'


def carregar():
    """Compatível com a cópia portátil; não acessa pipelines nem brutos."""
    out = {}
    for p in BASE.glob('*_produto_pais.json'):
        base = json.loads(p.read_text(encoding='utf-8'))
        validar_payload(base)
        base['validacao']['sha256_base_cruzada'] = sha(p)
        base['hashes'] = {Path(k).name:v for k,v in base.get('hashes',{}).items()}
        out[p.name.split('_')[0]] = base
    return out


if __name__ == '__main__':
    from coleta_cruzado import main
    main()
