"""Auditoria offline das células prontas e comparação com as bases da pasta 11."""
import json
import time
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from balanca_sankey_cruzado import BASE, gravar_json, validar_payload
from comum import MAPA_GRANULAR


def main():
    report={}
    for p in sorted(BASE.glob('*_produto_pais.json')):
        obj=json.loads(p.read_text(encoding='utf-8'))
        validar_payload(obj)
        pais=obj['country']
        dic=obj['dictionaries']
        cobertura_real=set(map(tuple,obj['coverage']))
        registros,parceiros=[],[]
        for mes,rows in obj['months'].items():
            prod=np.zeros((len(dic['fluxo']),len(dic['produto'])))
            bloc=np.zeros((len(dic['fluxo']),len(dic['bloco'])))
            for f,pr,pa,bl,v in rows:
                prod[int(f),int(pr)]+=v*1e9
                bloc[int(f),int(bl)]+=v*1e9
            for f,fluxo in enumerate(dic['fluxo']):
                if (mes,fluxo) not in cobertura_real:
                    continue
                for j,nome in enumerate(dic['produto']):
                    registros.append((mes,fluxo,MAPA_GRANULAR[99] if nome=='Produto não detalhado' else nome,prod[f,j]))
                for j,nome in enumerate(dic['bloco']):
                    parceiros.append((mes,fluxo,nome,bloc[f,j]))
        calc=pd.DataFrame(registros,columns=['date','fluxo','produto','valor']).groupby(['date','fluxo','produto']).valor.sum()
        ref=pd.read_csv(BASE/f'{pais}_produtos.csv').set_index(['date','fluxo','serie']).valor.dropna()
        comum=calc.index.intersection(ref.index)
        diff=(calc.reindex(comum)-ref.reindex(comum)).abs()
        idx=diff[diff>ref.reindex(comum).abs()*1e-7+2].index
        pd.DataFrame(dict(valor_cruzado=calc.reindex(idx).values,valor_pasta11=ref.reindex(idx).values,
            diferenca_absoluta=diff.reindex(idx).values),index=idx.set_names(['date','fluxo','produto'])).to_csv(BASE/f'{pais}_cruzado_divergencias.csv')
        obj['validacao'].update(produtos_conferidos=len(comum),divergencias_pasta11=len(idx),
                               maior_diferenca_pasta11=float(diff.max()))
        obj['hashes']={Path(k).name:v for k,v in obj.get('hashes',{}).items()}
        gravar_json(p,obj)
        total=pd.DataFrame(parceiros,columns=['date','fluxo','bloco','valor']).groupby(['date','fluxo']).valor.sum()
        ref_total=pd.read_csv(BASE/f'{pais}_parceiros.csv').groupby(['date','fluxo']).valor.sum()
        dt=(total-ref_total).dropna()
        cobertura={}
        for fl in ['exp','imp']:
            meses=sorted(m for m,f in obj['coverage'] if f==fl)
            cobertura[fl]=dict(inicio=meses[0],fim=meses[-1],meses=len(meses),
                lacunas=sorted(set(pd.period_range(meses[0],meses[-1],freq='M').astype(str))-set(meses)))
        report[pais]=dict(cobertura=cobertura,paises=len(dic['pais']),produtos=len(dic['produto']),
            celulas=sum(len(r) for r in obj['months'].values()),duplicatas=0,
            produtos_conferidos=len(comum),divergencias_pasta11=len(idx),
            maior_diferenca_total_parceiros=float(dt.abs().max()),
            maior_diferenca_pct_total_parceiros=float((dt/ref_total.reindex(dt.index)).abs().max()*100),
            fonte=obj['validacao']['fonte'])
        print(pais,report[pais],flush=True)
    banco=BASE/'brutos/cruzado/comtrade_cota.sqlite'
    if banco.exists():
        db=sqlite3.connect(str(banco),timeout=30)
        report['comtrade']=dict(reservas_24h=db.execute('SELECT COUNT(*) FROM chamadas WHERE instante>?',(time.time()-86400,)).fetchone()[0],teto=450)
        db.close()
    gravar_json(BASE/'auditoria_cruzados.json',report)


if __name__=='__main__': main()
