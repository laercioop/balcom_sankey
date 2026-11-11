"""Coleta retomável do cruzamento real, preservando respostas oficiais.

python codigos/coleta_cruzado.py [--paises brasil ue eua china] [--offline]
Todo o intervalo das bases da pasta 11, ambos os fluxos, todos os capítulos.
Credenciais opcionais: CENSUS_API_KEY, COMTRADE_API_KEY (não gravadas).
Uma falha de país não impede processar os demais; cobertura incompleta é erro
no status final, nunca uma aprovação de cobertura integral.
"""
import argparse
import csv
import gzip
import io
import json
import os
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from comum import DADOS, PASTAS_DADOS, MAPA_GRANULAR
from balanca_sankey_cruzado import (BASE, CACHE, COLS, EU2, EU3, NOMES, bloco,
                                    compactar, gravar_json)

MDIC = 'https://balanca.mdic.gov.br/balanca/bd/comexstat-bd/ncm/{}_{ano}.csv'
COMEXT = 'https://ec.europa.eu/eurostat/api/comext/dissemination/statistics/1.0/data/DS-045409'
CAPS = ['00'] + [f'{n:02d}' for n in range(1, 100) if n != 77]


def intervalo(pais):
    ds = [pd.read_csv(BASE / f'{pais}_{tipo}.csv') for tipo in ['parceiros', 'produtos']]
    return min(d.date.min() for d in ds), max(d.date.max() for d in ds)


def obter(url, p, offline):
    if p.exists():
        return p
    if offline:
        raise FileNotFoundError(f'Cache ausente: {p}')
    p.parent.mkdir(parents=True, exist_ok=True)
    for tentativa in range(3):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=180) as r:
                # Não confundir uma página HTML de chave ausente com JSON.
                raw = r.read()
            if p.name.endswith('.json.gz'):
                obj = json.loads(raw)
                if isinstance(obj, dict) and obj.get('error'):
                    raise RuntimeError(str(obj['error']))
                raw = gzip.compress(raw)
            tmp = p.with_suffix('.part')
            tmp.write_bytes(raw)
            tmp.replace(p)
            return p
        except Exception:
            if tentativa == 2:
                raise
            time.sleep(2)


def ler(p):
    return json.loads(gzip.decompress(p.read_bytes()))


def preparar_brasil(offline):
    ini, fim = intervalo('brasil')
    aux = DADOS / 'sankey/brutos/paises.csv'
    a = pd.read_csv(aux).set_index('CO_PAIS')
    nomes = a.NO_PAIS.to_dict()
    principais = set(pd.read_csv(BASE / 'brasil_parceiros.csv').serie)
    blocos = {co: bloco('brasil', r.CO_PAIS_ISOA3, r.NO_PAIS, principais) for co, r in a.iterrows()}
    partes, fontes, cobertura = [], [aux], []
    for ano in range(int(ini[:4]), int(fim[:4]) + 1):
        for fl in ['exp', 'imp']:
            agregado = CACHE / 'brasil' / f'{fl}_{ano}_hs2.csv.gz'
            local = PASTAS_DADOS['brasil'].parent / 'balcom_r/downloads' / f'{fl.upper()}_{ano}.csv'
            existente = DADOS / 'sankey/brutos' / f'{fl}_pais_ncm_{ano}.csv.gz'
            if not agregado.exists():
                p = local if local.exists() else existente
                if not p.exists():
                    p = obter(MDIC.format(fl.upper(), ano=ano), CACHE / 'brasil' / f'{fl.upper()}_{ano}.csv', offline)
                sep = ';' if p.suffix == '.csv' else ','
                grupos = []
                for c in pd.read_csv(p, sep=sep, encoding='latin1' if sep == ';' else 'utf-8',
                        usecols=['CO_ANO','CO_MES','CO_PAIS','CO_NCM','VL_FOB'], dtype={'CO_NCM':str}, chunksize=500000):
                    c['hs2'] = c.CO_NCM.str.zfill(8).str[:2]
                    grupos.append(c.groupby(['CO_ANO','CO_MES','CO_PAIS','hs2']).VL_FOB.sum())
                g = pd.concat(grupos).groupby(level=[0,1,2,3]).sum().reset_index()
                agregado.parent.mkdir(parents=True, exist_ok=True)
                g.to_csv(agregado, index=False, compression='gzip')
                # Guarda hash do NCM de origem sem precisar reler GB na geração.
                from balanca_sankey_cruzado import sha
                gravar_json(agregado.with_suffix('.fonte.json'), dict(arquivo=p.name, sha256=sha(p)))
            fontes += [agregado, agregado.with_suffix('.fonte.json')]
            c = pd.read_csv(agregado, dtype={'hs2':str})
            assert set(c.CO_ANO) == {ano}, agregado
            c['date'] = c.CO_ANO.astype(str) + '-' + c.CO_MES.astype(str).str.zfill(2)
            c = c[c.date.between(ini, fim)].copy()
            c['fluxo'] = fl
            c['produto'] = c.hs2.astype(int).map(MAPA_GRANULAR).fillna(MAPA_GRANULAR[99])
            c['pais'] = c.CO_PAIS.map(nomes).fillna('Não especificado')
            c['bloco'] = c.CO_PAIS.map(blocos).fillna('Demais parceiros')
            cobertura += [(mes, fl) for mes in c.date.unique()]
            partes.append(c.groupby(COLS).VL_FOB.sum().rename('valor'))
            print(f'Brasil {ano} {fl}: pronto', flush=True)
    d = pd.concat(partes).groupby(level=list(range(5))).sum().reset_index()
    # Controle independente do total publicado no BALCOM (US$ milhões).
    controle = pd.read_excel(PASTAS_DADOS['brasil'].parent / 'balcom_r.xlsx', sheet_name='CGCE')
    controle['date'] = controle.date.str.replace('M', '-', regex=False)
    totais = d.groupby(['date','fluxo']).valor.sum()
    for fl, col in [('exp','x_tot'), ('imp','m_tot')]:
        r = controle.set_index('date')[col].dropna() * 1e6
        v = totais.xs(fl, level='fluxo')
        comum = v.index.intersection(r.index)
        if not np.allclose(v.loc[comum], r.loc[comum], rtol=1e-7, atol=2):
            diff = (v.loc[comum]-r.loc[comum]).abs()
            raise ValueError(f'Brasil diverge de CGCE: {diff.nlargest(5).to_dict()}')
    return compactar('brasil', d, fontes, cobertura, 'MDIC / Comex Stat')


def decodificar_comext(obj):
    labels = [[k for k,v in sorted(obj['dimension'][dim]['category']['index'].items(), key=lambda kv:kv[1])] for dim in obj['id']]
    for k, v in obj.get('value', {}).items():
        r = dict(zip(obj['id'], [labels[j][n] for j,n in enumerate(np.unravel_index(int(k), obj['size']))]))
        yield r, float(v)


def reino_unido_ue(offline):
    """UE27 fixa: reconstrói o detalhe britânico pré-Brexit pelos membros.

    O TOTAL da soma dos 27 membros precisa coincidir com EU27_2020/GB.
    Nenhum valor é distribuído por produto: cada capítulo vem do Comext.
    """
    def consulta(codigo):
        p = CACHE/'ue'/f'reino_unido_membros_{codigo.lower()}_2015_2020.json.gz'
        params=[('freq','M'),('partner','GB'),('indicators','VALUE_IN_EUROS'),('sinceTimePeriod','2015-01'),('untilTimePeriod','2020-12')]
        params += [('reporter',co) for co in sorted(EU2)]
        params += [('product',co) for co in ([codigo,'99'] if codigo=='98' else [codigo])]
        obj=ler(obter(COMEXT+'?'+urllib.parse.urlencode(params),p,offline))
        rows=[]
        for r,v in decodificar_comext(obj):
            if r['product']==codigo:
                rows.append(dict(date=r['time'],fluxo={'1':'imp','2':'exp'}[r['flow']],valor=v))
        if rows:
            assert len(obj['dimension']['reporter']['category']['index'])==27
        print('UE Reino Unido capítulo',codigo,'pronto',flush=True)
        return codigo,rows,p
    with ThreadPoolExecutor(max_workers=3) as ex:
        res=list(ex.map(consulta,['TOTAL']+CAPS))
    total=pd.DataFrame(res[0][1]).groupby(['date','fluxo']).valor.sum()
    ref=pd.read_csv(BASE/'ue_parceiros.csv')
    ref=ref[ref.serie=='Reino Unido'].set_index(['date','fluxo']).valor.reindex(total.index)
    assert np.allclose(total,ref,rtol=1e-9,atol=2),'UE27: soma dos membros não confere com Reino Unido agregado'
    partes=[]
    for codigo,rows,_ in res[1:]:
        if rows:
            t=pd.DataFrame(rows).groupby(['date','fluxo'],as_index=False).valor.sum()
            t['produto']=MAPA_GRANULAR.get(int(codigo),MAPA_GRANULAR[99])
            partes.append(t)
    d=pd.concat(partes,ignore_index=True)
    soma=d.groupby(['date','fluxo']).valor.sum()
    for (mes,fl),v in total.items():
        residual=v-soma.get((mes,fl),0)
        assert residual>=-max(2,v*1e-7),f'UE/Reino Unido capítulos acima do total: {mes}/{fl}'
        if residual>0:
            d=pd.concat([d,pd.DataFrame([dict(date=mes,fluxo=fl,produto='Produto não detalhado',valor=residual)])],ignore_index=True)
    d['pais'],d['bloco']='Reino Unido','Reino Unido'
    return d,[r[2] for r in res]


def preparar_ue(offline):
    ini, fim = intervalo('ue')
    principais = set(pd.read_csv(BASE / 'ue_parceiros.csv').serie)
    def cap(codigo):
        p = CACHE / 'ue' / f'hs2_{codigo}_{ini}_{fim}.json.gz'
        params = dict(freq='M', reporter='EU27_2020', product=[codigo, '99'] if codigo == '98' else codigo,
                      indicators='VALUE_IN_EUROS', sinceTimePeriod=ini, untilTimePeriod=fim)
        obj = ler(obter(COMEXT + '?' + urllib.parse.urlencode(params, doseq=True), p, offline))
        names = obj['dimension']['partner']['category'].get('label', {})
        rows, total = [], {}
        for r, v in decodificar_comext(obj):
            if r['product'] != codigo:
                continue
            mes, fl, co = r['time'], {'1':'imp','2':'exp'}[r['flow']], r['partner']
            if not ini <= mes <= fim:
                continue
            if co == 'EXT_EU27_2020':
                total[mes,fl] = v
            # Somente países extra-UE e códigos oficiais não especificados.
            elif len(co) == 2 and co not in EU2 and not co.startswith('X') and co not in ['EU']:
                if co.startswith('Q') and co not in ['QP','QQ','QS','QU','QW','QX','QZ']:
                    continue
                nome = NOMES.get(co, names.get(co, co))
                rows.append(dict(date=mes, fluxo=fl, produto=MAPA_GRANULAR.get(int(codigo), MAPA_GRANULAR[99]),
                                 pais=nome, bloco=bloco('ue', co, nome, principais), valor=v))
        # A ausência de capítulo em todo o histórico não é comércio estimado.
        if not total and not rows:
            print('UE capítulo', codigo, 'sem valores', flush=True)
            return [], p, set()
        d = pd.DataFrame(rows)
        soma = d.groupby(['date','fluxo']).valor.sum() if rows else pd.Series(dtype=float)
        for (mes, fl), v in total.items():
            residuo = v - soma.get((mes,fl), 0)
            if residuo < -max(2, v*1e-7):
                raise ValueError(f'UE {codigo}/{mes}/{fl}: parceiros acima do total ({residuo})')
            if residuo > 0:
                rows.append(dict(date=mes, fluxo=fl, produto=MAPA_GRANULAR.get(int(codigo), MAPA_GRANULAR[99]),
                                 pais='Parceiro não detalhado', bloco='Demais parceiros', valor=residuo))
        print('UE capítulo', codigo, 'pronto', flush=True)
        return rows, p, set(total)
    # Evita consultas simultâneas excessivas ao Comext.
    with ThreadPoolExecutor(max_workers=3) as ex:
        res = list(ex.map(cap, CAPS))
    rows = [r for registros, _, _ in res for r in registros]
    d = pd.DataFrame(rows).groupby(COLS, as_index=False).valor.sum()
    uk, fontes_uk = reino_unido_ue(offline)
    d=d[~((d.pais=='Reino Unido')&(d.date<='2020-12'))]
    d=pd.concat([d,uk],ignore_index=True)
    # A requisição por capítulo cobre o intervalo inteiro. O TOTAL independente
    # abaixo define os meses publicados; nunca usa a presença de uma célula.
    p = CACHE / 'ue' / f'total_{ini}_{fim}.json.gz'
    params = dict(freq='M', reporter='EU27_2020', partner='EXT_EU27_2020', product='TOTAL',
                  indicators='VALUE_IN_EUROS', sinceTimePeriod=ini, untilTimePeriod=fim)
    obj = ler(obter(COMEXT + '?' + urllib.parse.urlencode(params), p, offline))
    total = {(r['time'], {'1':'imp','2':'exp'}[r['flow']]):v for r,v in decodificar_comext(obj) if ini <= r['time'] <= fim}
    soma = d.groupby(['date','fluxo']).valor.sum()
    for (mes, fl), v in total.items():
        residual = v-soma.get((mes,fl), 0)
        if residual < -max(2, v*1e-7):
            raise ValueError(f'UE capítulos acima do TOTAL: {mes}/{fl}: {residual}')
        if residual > 0:
            d = pd.concat([d, pd.DataFrame([dict(date=mes,fluxo=fl,produto=MAPA_GRANULAR[99],
                pais='Produto e parceiro não detalhados',bloco='Demais parceiros',valor=residual)])], ignore_index=True)
    return compactar('ue', d.groupby(COLS,as_index=False).valor.sum(), [x[1] for x in res]+fontes_uk+[p], list(total), 'Eurostat Comext DS-045409 (Reino Unido até 2020: soma dos 27 membros)')


def respostas_census(ini, fim, key, offline):
    tarefas = [(ano,fl,endpoint,commodity,value)
        for ano in range(int(ini[:4]),int(fim[:4])+1)
        for fl,endpoint,commodity,value in [('exp','exports','E_COMMODITY','ALL_VAL_MO'),('imp','imports','I_COMMODITY','GEN_VAL_MO')]]
    def carregar_tarefa(item):
        ano,fl,endpoint,commodity,value = item
        p = CACHE / 'eua' / f'{ano}_{fl}_ano.json.gz'
        meses = [m for m in pd.period_range(max(ini,f'{ano}-01'),min(fim,f'{ano}-12'),freq='M').astype(str)]
        mensais = [CACHE / 'eua' / f'{m}_{fl}.json.gz' for m in meses]
        if not p.exists() and all(x.exists() for x in mensais):
            frames = []
            for arquivo in mensais:
                o = ler(arquivo)
                frames.append(pd.DataFrame(o[1:],columns=o[0]))
            frame = pd.concat(frames,ignore_index=True)
            return ano,fl,commodity,value,mensais,[list(frame.columns)]+frame.values.tolist()
        # Ano inteiro com MONTH no get: mantém os meses separados, em uma
        # consulta por fluxo/ano. Requisição oficial já confirmou >180 mil
        # registros e os 12 meses, sem truncamento.
        params = dict(get=f'CTY_CODE,CTY_NAME,{commodity},{value},MONTH',YEAR=str(ano),COMM_LVL='HS2',DISTRICT='-')
        if fl == 'exp':
            params['DF'] = '-'
        if key:
            params['key'] = key
        obj = ler(obter(f'https://api.census.gov/data/timeseries/intltrade/{endpoint}/hs?' + urllib.parse.urlencode(params),p,offline))
        return ano,fl,commodity,value,[p],obj
    pool = ThreadPoolExecutor(max_workers=2)
    pendentes = {i:pool.submit(carregar_tarefa,item) for i,item in enumerate(tarefas[:2])}
    try:
        for i in range(len(tarefas)):
            result = pendentes.pop(i).result()
            if i+2 < len(tarefas):
                pendentes[i+2] = pool.submit(carregar_tarefa,tarefas[i+2])
            yield result
    finally:
        pool.shutdown(wait=True,cancel_futures=True)


def preparar_census(offline):
    key = os.environ.get('CENSUS_API_KEY')
    if not key and not offline:
        raise RuntimeError('Census exige chave: configure CENSUS_API_KEY. Não foi estimado nenhum cruzamento.')
    ini, fim = intervalo('eua')
    principais = set(pd.read_csv(BASE / 'eua_parceiros.csv').serie)
    from balanca_sankey_dados import EU_NOMES, TRAD
    atlas = pd.read_excel(BASE / 'brutos/census_country.xlsx')[['CTY_CODE','CTYNAME']].drop_duplicates('CTY_CODE').set_index('CTY_CODE').CTYNAME.to_dict()
    partes, fontes, cobertura = [], [], []
    for ano,fl,commodity,value,arquivos,obj in respostas_census(ini,fim,key,offline):
        if not isinstance(obj,list) or len(obj)<2:
            raise ValueError(f'Census sem dados: {ano}/{fl}')
        frame = pd.DataFrame(obj[1:],columns=obj[0])
        frame = frame.loc[:,~frame.columns.duplicated()]
        frame['date'] = str(ano)+'-'+frame.MONTH.str.zfill(2)
        frame = frame[frame.date.between(ini,fim)].copy()
        mundo = frame[frame.CTY_CODE=='-'].set_index(['date',commodity])[value].astype(float)
        frame = frame[(pd.to_numeric(frame.CTY_CODE,errors='coerce')>=1000)&frame[commodity].str.fullmatch(r'\d{2}')].copy()
        if frame.duplicated(['date','CTY_CODE',commodity]).any():
            raise ValueError('Census retornou duplicatas')
        soma = frame.assign(v=pd.to_numeric(frame[value])).groupby(['date',commodity]).v.sum()
        assert len(mundo) and not mundo.index.duplicated().any()
        assert np.allclose(soma.reindex(mundo.index).fillna(0),mundo,rtol=1e-9,atol=2), f'Census países não fecham com o mundo: {ano}/{fl}'
        ingles = frame.CTY_CODE.astype(int).map(atlas).fillna(frame.CTY_NAME.str.title())
        frame['pais'] = ingles.map(TRAD).fillna(ingles)
        frame['bloco'] = frame.pais.where(frame.pais.isin(principais),'Demais parceiros')
        frame.loc[ingles.isin(EU_NOMES),'bloco'] = 'União Europeia'
        frame['produto'] = frame[commodity].astype(int).map(MAPA_GRANULAR).fillna(MAPA_GRANULAR[99])
        frame['fluxo'],frame['valor'] = fl,pd.to_numeric(frame[value])
        partes.append(frame.groupby(COLS).valor.sum())
        fontes.extend(arquivos)
        cobertura.extend((mes,fl) for mes in frame.date.unique())
        print('EUA',ano,fl,'pronto; meses:',len(frame.date.unique()),flush=True)
    d = pd.concat(partes).groupby(level=list(range(5))).sum().reset_index()
    return compactar('eua',d,fontes,cobertura,'US Census (importações gerais, valor de alfândega)')


GACC_MANUAL = CACHE / 'china_manual'
GACC_PARCEIROS = Path(__file__).with_name('gacc_parceiros.csv')
GACC_CAB = ['Date of data', 'Commodity code', 'Commodity', 'Trading partner code', 'Trading partner', 'US dollar']
GACC_LIMITE = 10000
ASEAN3 = set('BRN KHM IDN LAO MYS MMR PHL SGP THA TLS VNM'.split())
# Comtrade usa códigos regionais "nes"; S19 ("Other Asia, nes") é Taiwan
# quando a China é a reportante.
NES = dict(S19='Taiwan', _X='Países não especificados', O19='Outros territórios da Oceania',
           E19='Outros territórios da Europa', F19='Outros territórios da África',
           A59='Outros territórios da América do Norte', A79='Outros territórios da América Latina')


def nomes_iso():
    """Nomes em português por ISO3 (tabela MDIC), com nomes curtos usados nos blocos."""
    aux = DADOS / 'sankey/brutos/paises.csv'
    nomes = pd.read_csv(aux).set_index('CO_PAIS_ISOA3').NO_PAIS.to_dict()
    nomes.update(USA='EUA', CHN='China', GBR='Reino Unido', CHE='Suíça',
                 KOR='Coreia do Sul', JPN='Japão', BRA='Brasil', HKG='Hong Kong', RUS='Rússia',
                 DEU='Alemanha', PNG='Papua Nova Guiné', UMI='Ilhas menores dos EUA',
                 TWN='Taiwan', MYT='Mayotte', JEY='Jersey', GGY='Guernsey', MAF='São Martinho')
    # A tabela MDIC contém códigos históricos com o mesmo ISO3 (ex.: DEU
    # para Alemanha Oriental). Não permitir que o último sobrescreva o atual.
    nomes.pop('ZZZ', None)
    return nomes, aux


def bloco_china(iso, nome, principais):
    if iso in EU3:
        return 'União Europeia'
    if iso in ASEAN3:
        return 'ASEAN'
    return nome if nome in principais else 'Demais parceiros'


def ler_gacc(p):
    """CSV da plataforma GACC: GB18030, campos entre aspas (alguns com quebra
    de linha), valor em US$ com separador de milhar e vírgula final."""
    linhas = list(csv.reader(io.StringIO(p.read_text(encoding='gb18030'))))
    if [c.strip() for c in linhas[0][:6]] != GACC_CAB:
        raise ValueError(f'{p.name}: cabeçalho GACC inesperado')
    if any(len(x) != 7 or x[6] != '' for x in linhas[1:]):
        raise ValueError(f'{p.name}: linha com número de campos inesperado')
    d = pd.DataFrame([x[:6] for x in linhas[1:]], columns=['mes', 'hs2', 'produto_gacc', 'codigo', 'parceiro', 'usd'])
    d['valor'] = pd.to_numeric(d.usd.str.replace(',', '', regex=False), errors='raise')
    return d


def linhas_gacc(principais):
    """Partições mensais da plataforma GACC (china_manual/gacc_{fluxo}_{AAAAMM}.csv).

    Importações vêm completas e entram como publicadas. Exportações vêm
    ordenadas por valor e cortadas em 10.000 linhas: a sobra positiva de cada
    capítulo contra china_hs2.csv vira "Parceiro não detalhado". Diferenças
    negativas são revisões da plataforma e não alteram as células.
    Sem china_hs2.csv para o mês (2015), o arquivo truncado entra como está.
    """
    nomes, aux = nomes_iso()
    mapa = pd.read_csv(GACC_PARCEIROS, dtype=str, keep_default_na=False).set_index('codigo_gacc')
    ref = pd.read_csv(PASTAS_DADOS['china'] / 'china_hs2.csv', dtype={'hs2': str})
    ref = ref[ref.hs2 != 'TOTAL'].set_index(['date', 'fluxo', 'hs2']).valor * 1000  # US$ mil -> US$
    arquivos = sorted(GACC_MANUAL.glob('gacc_*_*.csv'))
    partes, fontes, cobertura, resumo = [], [aux, GACC_PARCEIROS, PASTAS_DADOS['china'] / 'china_hs2.csv'], [], []
    for p in arquivos:
        partes_nome = p.stem.split('_')
        if len(partes_nome) != 3 or partes_nome[1] not in ('exp', 'imp') or not partes_nome[2].isdigit():
            raise ValueError(f'Nome fora do padrão gacc_{{exp|imp}}_AAAAMM.csv: {p.name}')
        fl, aaaamm = partes_nome[1], partes_nome[2]
        mes = aaaamm[:4] + '-' + aaaamm[4:]
        d = ler_gacc(p)
        if set(d.mes) != {aaaamm}:
            raise ValueError(f'{p.name}: meses {sorted(set(d.mes))} no arquivo')
        if not d.hs2.str.fullmatch(r'\d{2}').all() or (d.valor < 0).any():
            raise ValueError(f'{p.name}: capítulo ou valor inválido')
        if d.duplicated(['hs2', 'codigo']).any():
            raise ValueError(f'{p.name}: capítulo x parceiro duplicado')
        novos = set(d.codigo) - set(mapa.index)
        if novos:
            raise ValueError(f'{p.name}: parceiros GACC sem mapeamento em {GACC_PARCEIROS.name}: {sorted(novos)}')
        m = mapa.reindex(d.codigo)
        d['pais'] = [pt or nomes.get(iso, iso) for iso, pt in zip(m.iso3, m.nome_pt)]
        d['bloco'] = [bloco_china(iso, n, principais) for iso, n in zip(m.iso3, d.pais)]
        n_linhas = len(d)
        truncado = n_linhas >= GACC_LIMITE
        sobra = 0.0
        if truncado and mes in ref.index.get_level_values(0):
            r = ref.xs((mes, fl), level=['date', 'fluxo'])
            s = r.sub(d.groupby('hs2').valor.sum(), fill_value=0)
            s = s[s > 0]
            sobra = float(s.sum())
            d = pd.concat([d, pd.DataFrame(dict(hs2=s.index, valor=s.values,
                pais='Parceiro não detalhado', bloco='Demais parceiros'))], ignore_index=True)
        d['date'], d['fluxo'] = mes, fl
        d['produto'] = d.hs2.astype(int).map(MAPA_GRANULAR).fillna(MAPA_GRANULAR[99])
        partes.append(d.groupby(COLS).valor.sum())
        fontes.append(p)
        cobertura.append((mes, fl))
        resumo.append(dict(arquivo=p.name, linhas=n_linhas, truncado=truncado, sobra_usd=sobra))
    if len(set(cobertura)) != len(cobertura):
        raise ValueError('GACC: mês/fluxo repetido em china_manual')
    if not partes:
        return None, fontes, cobertura, resumo
    return pd.concat(partes).groupby(level=list(range(5))).sum().reset_index(), fontes, cobertura, resumo


def preparar_china(offline):
    """Comtrade (GACC reportado à ONU, 2016–2024) + plataforma GACC (demais meses).

    Um mês/fluxo vem de uma só fonte: o Comtrade quando publicado; senão,
    o arquivo manual da GACC.
    """
    principais = set(pd.read_csv(BASE / 'china_parceiros.csv').serie)
    ct, fontes_ct, cob_ct = linhas_comtrade('china', offline)
    gacc, fontes_g, cob_g, resumo = linhas_gacc(principais)
    usar = sorted(set(cob_g) - set(cob_ct))
    partes = [ct] if ct is not None else []
    if gacc is not None and usar:
        chave = pd.MultiIndex.from_frame(gacc[['date', 'fluxo']])
        partes.append(gacc[chave.isin(usar)])
    if not partes:
        raise ValueError('China: nenhuma partição mensal disponível')
    d = pd.concat(partes, ignore_index=True)
    gravar_json(BASE / 'china_gacc_manual_resumo.json', resumo)
    print('China: Comtrade', len(cob_ct), 'mês/fluxo; GACC', len(usar), 'mês/fluxo', flush=True)
    fonte = ('GACC: UN Comtrade em 2016–2024 e plataforma de consulta da GACC nos demais meses '
             '(importações CIF; exportações FOB)')
    return compactar('china', d, fontes_ct + fontes_g, cob_ct + usar, fonte)


def respostas_comtrade(pais, meses, offline):
    """Prefetch de duas tarefas; HTTP global exclusivo, sem repetição automática."""
    from comtrade_cota import consultar
    def obter_mes(mes):
        p = CACHE / pais / f'{mes}_reportercode_hs2.json'
        if not p.exists():
            p = p.with_suffix('.json.gz')
        if offline and not p.exists():
            return p, None
        return p, consultar(dict(reporterCode=156 if pais == 'china' else 842,
            period=mes.replace('-',''), cmdCode='TOTAL,AG2', flowCode='X,M',
            partner2Code=0, customsCode='C00', motCode=0, maxRecords=100000,
            includeDesc='true'), p)
    pool = ThreadPoolExecutor(max_workers=2)
    pendentes = {i:pool.submit(obter_mes,mes) for i,mes in enumerate(meses[:2])}
    try:
        for i, mes in enumerate(meses):
            p, obj = pendentes.pop(i).result()
            if i+2 < len(meses):
                pendentes[i+2] = pool.submit(obter_mes,meses[i+2])
            yield mes, p, obj
    finally:
        pool.shutdown(wait=True, cancel_futures=True)


def preparar_comtrade_china(offline, pais='china'):
    d, fontes, cobertura = linhas_comtrade(pais, offline)
    if d is None:
        raise ValueError(f'{pais}: nenhuma partição mensal completa disponível na fonte')
    fonte = ('GACC' if pais == 'china' else 'US Census') + ' reportado ao UN Comtrade (importações CIF; exportações FOB)'
    return compactar(pais,d,fontes,cobertura,fonte)


def linhas_comtrade(pais, offline):
    ini, fim = intervalo(pais)
    # Parte anterior a 2018 só aparece nos parceiros da pasta 11; o cruzamento
    # também a solicita. Meses vazios permanecem fora da cobertura.
    nomes, aux = nomes_iso()
    if pais == 'china':
        nomes.update(NES)
    principais = set(pd.read_csv(BASE / (pais + '_parceiros.csv')).serie)
    partes, fontes, cobertura = [], [aux], []
    meses = list(reversed(pd.period_range(ini, fim, freq='M').astype(str).tolist()))
    for mes, p, obj in respostas_comtrade(pais, meses, offline):
        if obj is None:
            continue
        fontes.append(p)
        registros = obj.get('data', [])
        if len(registros) >= 100000:
            raise ValueError(f'China {mes}: resposta potencialmente truncada; não incorporada.')
        if not registros:
            print(pais,mes,'não publicado no Comtrade; cache vazio preservado',flush=True)
            continue
        mundo, totais, rows = {}, {}, []
        for r in registros:
            if str(r.get('period')) != mes.replace('-','') or r.get('flowCode') not in ['X','M']:
                raise ValueError('Comtrade: período/fluxo inesperado')
            fl, hs, co = {'X':'exp','M':'imp'}[r['flowCode']], str(r['cmdCode']), r['partnerCode']
            v = r.get('primaryValue')
            if v is None or not np.isfinite(v) or v < 0:
                raise ValueError('Comtrade: valor inválido')
            if co == 0:
                if hs == 'TOTAL':
                    totais[fl] = v
                elif len(hs) == 2 and hs.isdigit():
                    mundo[fl,hs] = v
                continue
            # Códigos de países/áreas ONU têm três dígitos; blocos especiais
            # de quatro dígitos são agregados, excluídos para não somar duas vezes.
            if co >= 1000 or not (len(hs)==2 and hs.isdigit()):
                continue
            iso = (r.get('partnerISO') or '').strip()
            nome = nomes.get(iso, r.get('partnerDesc') or f'Área ONU {co}')
            b = bloco_china(iso, nome, principais) if pais == 'china' else 'União Europeia' if iso in EU3 else nome if nome in principais else 'Demais parceiros'
            rows.append(dict(date=mes,fluxo=fl,hs2=hs,produto=MAPA_GRANULAR.get(int(hs),MAPA_GRANULAR[99]),pais=nome,bloco=b,valor=v,co=co))
        d = pd.DataFrame(rows)
        if d.empty:
            continue
        if d.duplicated(['fluxo','hs2','co']).any():
            raise ValueError(f'China {mes}: duplicatas na fonte')
        soma = d.groupby(['fluxo','hs2']).valor.sum()
        for (fl,hs), v in mundo.items():
            residual = v-soma.get((fl,hs),0)
            if residual < -max(2,v*1e-7):
                raise ValueError(f'China {mes}/{fl}/{hs}: parceiros acima do mundo')
            if residual > 0:
                rows.append(dict(date=mes,fluxo=fl,hs2=hs,produto=MAPA_GRANULAR.get(int(hs),MAPA_GRANULAR[99]),pais='Parceiro não detalhado',bloco='Demais parceiros',valor=residual))
        for fl,v in totais.items():
            residual = v-sum(x for (flow,_),x in mundo.items() if flow==fl)
            if residual < -max(2,v*1e-7):
                raise ValueError(f'China {mes}/{fl}: capítulos acima do TOTAL')
            if residual > 0:
                rows.append(dict(date=mes,fluxo=fl,hs2='00',produto=MAPA_GRANULAR[99],pais='Produto e parceiro não detalhados',bloco='Demais parceiros',valor=residual))
            cobertura.append((mes,fl))
        if set(totais) != {'exp','imp'}:
            raise ValueError(f'China {mes}: faltou TOTAL de um dos fluxos')
        partes.append(pd.DataFrame(rows).groupby(COLS).valor.sum())
        print(pais,mes,'pronto',flush=True)
    if not partes:
        return None, fontes, cobertura
    return pd.concat(partes).groupby(level=list(range(5))).sum().reset_index(), fontes, cobertura


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--paises', nargs='+', choices=['brasil','ue','eua','china'], default=['brasil','ue','eua','china'])
    ap.add_argument('--offline', action='store_true')
    ap.add_argument('--eua-comtrade', action='store_true', help='Alternativa ao Census; mesma chave e cota global do Comtrade')
    args = ap.parse_args()
    funcs = dict(brasil=preparar_brasil, ue=preparar_ue, eua=preparar_census, china=preparar_china)
    if args.eua_comtrade:
        funcs['eua'] = lambda offline: preparar_comtrade_china(offline, 'eua')
    status = {}
    status_path = BASE / ('coleta_cruzado_' + '_'.join(args.paises) + '_status.json')
    for pais in args.paises:
        try:
            out = funcs[pais](args.offline)
            ini, fim = intervalo(pais)
            esperado = {(str(m), fl) for m in pd.period_range(ini, fim, freq='M') for fl in ['exp','imp']}
            faltantes = sorted(esperado - set(map(tuple, out['coverage'])))
            status[pais] = dict(completo=not faltantes, faltantes=faltantes, validacao=out['validacao'])
        except Exception as exc:
            status[pais] = dict(completo=False, erro=f'{type(exc).__name__}: {exc}')
            print(pais, status[pais]['erro'], flush=True)
        gravar_json(status_path, status)
    if not all(x['completo'] for x in status.values()):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
