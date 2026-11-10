"""Pasta 11: Sankeys de exportação x importação, parceiros e produtos.

python balanca_sankey.py [--paises brasil eua ue china]
Requer balanca_sankey_dados.py. Não faz downloads. O centro é uma espinha
contábil: as faixas não são relações bilaterais produto x produto.
"""
import argparse
import hashlib
import json
import textwrap

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from comum import DADOS, GRAFICOS, GRANULAR
from estilo_ps import PALETTE, TITLE_GRAY, GRID
from sankey import faixa

BASE = DADOS/'balanca_sankey'
SAIDA = GRAFICOS/'11_balanca_comercial'
NOMES = dict(brasil='Brasil',eua='EUA',ue='UE27',china='China')
MESES = 'jan fev mar abr mai jun jul ago set out nov dez'.split()
CORES_PROD = dict(zip([x[0] for x in GRANULAR],
    [PALETTE[2],PALETTE[5],'#8eaa72','#b29234','#808080','#cd6252',
     '#796cb7','#a69acb','#5c9478','#c285a3','#ad8d60','#6e7b91',
     '#4a7fb5','#74a4ca','#dc7878','#b56074','#bcbcbc']))
CORES_PARCEIROS = {
    'China':'#4a7fb5', 'União Europeia':'#5c9478',
    'EUA':'#cd6252', 'Estados Unidos':'#cd6252',
    'Brasil':'#796cb7', 'Argentina':'#b29234', 'México':'#65a356',
    'Canadá':'#6e7b91', 'Chile':'#c285a3', 'Índia':'#ad8d60',
    'Japão':'#859bc1', 'Coreia do Sul':'#a69acb', 'Rússia':'#515151',
    'Singapura':'#80aa98', 'ASEAN':'#b29234', 'Hong Kong':'#74a4ca',
    'Reino Unido':'#b56074', 'Suíça':'#9da16a', 'Taiwan':'#c285a3',
    'Vietnã':'#bc9a7a', 'Tailândia':'#dc7878', 'Turquia':'#a69acb',
    'Noruega':'#80aa98', 'Demais parceiros':GRID,
}
ABREV = {'Máquinas elétricas e eletrônicos':'Máquinas elétricas e eletrônicos',
         'Pedras, vidro e metais preciosos':'Pedras, vidro e metais preciosos',
         'Aeronaves, navios e ferrovias':'Aeronaves, navios e ferrovias',
         'Coreia, República da (Sul)':'Coreia do Sul',
         'Países Baixos (Holanda)':'Países Baixos'}


def fmt(v):
    return f'{v:,.1f}'.replace(',','@').replace('.',',').replace('@','.')


def periodo(p):
    p=pd.Period(p,'M')
    return MESES[p.month-1]+'/'+str(p.year)[2:]


def acumular(d,modo):
    """Exige doze observações por série, ou uma observação SA por série."""
    assert not d.duplicated(['date','fluxo','serie']).any()
    fim=min(d[d.fluxo==fl].date.max() for fl in ['exp','imp'])
    ini=str(pd.Period(fim,'M')-(11 if modo=='12m' else 0))
    x=d[d.date.between(ini,fim)].copy()
    n=12 if modo=='12m' else 1
    assert x.date.nunique()==n,(ini,fim)
    cont=x.groupby(['fluxo','serie']).date.nunique()
    assert (cont==n).all(),cont[cont!=n]
    valor='valor' if modo=='12m' else 'valor_sa'
    if modo=='mensal' and 'ajustado' in x:
        assert x.ajustado.all(), 'O último mês precisa estar ajustado em todas as séries'
    assert np.isfinite(x[valor]).all() and (x[valor]>=0).all()
    if modo=='12m' and 'valor_acum' in d:
        # China: 12m = acumulado atual + dezembro anterior - acumulado
        # do mesmo mês anterior. Usa revisões publicadas, como graficos.py.
        p=pd.Period(fim,'M')
        z=d.set_index(['date','fluxo','serie']).valor_acum
        atual=z.xs(fim,level='date')
        if p.month==12:
            g=atual
        else:
            g=atual+z.xs(f'{p.year-1}-12',level='date')-z.xs(str(p-12),level='date')
        assert g.notna().all() and (g>=0).all()
    else:
        g=x.groupby(['fluxo','serie'])[valor].sum()
    return g.unstack('fluxo').fillna(0)/1e9,ini,fim


def layout(v,k,top=.88,gap=.006,hmin=.032):
    pos={}
    y=top
    for nome,valor in v.items():
        h=valor*k
        slot=max(h,hmin)
        a=y-(slot-h)/2
        pos[nome]=(a,a-h)
        y-=slot+gap
    return pos,top-y-gap


def desenhar(m,pais,tipo,modo,ini,fim,arquivo):
    exp,imp=m.exp.sum(),m.imp.sum()
    saldo=exp-imp
    ordem=list(m.index)
    esq=m.exp.to_dict()
    direita=m.imp.to_dict()
    cores=CORES_PROD.copy() if tipo=='produtos' else CORES_PARCEIROS.copy()
    cores['Demais parceiros']=GRID
    cores['Superávit comercial']='#5c9478'
    cores['Déficit comercial']='#cd6252'
    if saldo>0:
        direita['Superávit comercial']=saldo
        cores['Superávit comercial']='#5c9478'
    elif saldo<0:
        esq['Déficit comercial']=-saldo
        cores['Déficit comercial']='#cd6252'
    # Preserva zero nos dados exportados; não desenha faixa de largura zero.
    esq={n:v for n,v in esq.items() if v>0}
    direita={n:v for n,v in direita.items() if v>0}
    total=max(exp,imp)
    lo,hi=0,.73/total
    for _ in range(55):
        k=(lo+hi)/2
        if max(layout(esq,k)[1],layout(direita,k)[1])>.72:
            hi=k
        else:
            lo=k
    k=lo
    a,ha=layout(esq,k)
    b,hb=layout(direita,k)
    # Centraliza a altura ocupada por cada coluna na mesma janela.
    a={n:(u-(.72-ha)/2,v-(.72-ha)/2) for n,(u,v) in a.items()}
    b={n:(u-(.72-hb)/2,v-(.72-hb)/2) for n,(u,v) in b.items()}
    centro=.52+total*k/2
    fig=plt.figure(figsize=(11,10),dpi=240)
    ax=fig.add_axes([0,0,1,1])
    ax.set(xlim=(0,1),ylim=(0,1)); ax.axis('off')
    xl,xr,bw=.295,.705,.009
    fs=8.5
    for valores,pos,lado in [(esq,a,'exp'),(direita,b,'imp')]:
        cursor=centro
        for nome,v in valores.items():
            h=v*k
            u,w=pos[nome]
            c=cores.get(nome,GRID)
            if lado=='exp':
                faixa(ax,xl+bw,.496,u,w,cursor,cursor-h,c)
                ax.add_patch(Rectangle((xl,w),bw,h,color=c,lw=0,zorder=3))
                ax.add_patch(Rectangle((.492,cursor-h),.008,h,color=c,lw=0,zorder=3))
                x,ha_text=xl-.012,'right'
            else:
                faixa(ax,.504,xr,cursor,cursor-h,u,w,c)
                ax.add_patch(Rectangle((xr,w),bw,h,color=c,lw=0,zorder=3))
                ax.add_patch(Rectangle((.500,cursor-h),.008,h,color=c,lw=0,zorder=3))
                x,ha_text=xr+bw+.012,'left'
            cursor-=h
            label=ABREV.get(nome,nome)
            label='\n'.join(textwrap.wrap(label,width=30,break_long_words=False))
            ax.text(x,(u+w)/2,label,ha=ha_text,va='center',fontsize=fs,
                    color=c if 'comercial' in nome else '#404040',
                    weight='bold' if 'comercial' in nome else 'normal',linespacing=1.06)
            # Valores em coluna separada, próxima ao fluxo, sem sobrepor nomes.
            xv=xl+bw+.012 if lado=='exp' else xr-.012
            ax.text(xv,(u+w)/2,fmt(v),ha='left' if lado=='exp' else 'right',
                    va='center',fontsize=8,color='#303030',weight='bold',zorder=5,
                    bbox=dict(facecolor='white',edgecolor='none',alpha=.78,pad=.25))
    ax.plot([.5,.5],[centro-total*k,centro],color='white',lw=.6,zorder=4)
    descricao='parceiros' if tipo=='parceiros' else 'produtos'
    per=f'12 meses até {periodo(fim)}' if modo=='12m' else periodo(fim)+' (dessaz.)'
    ax.text(.025,.976,f'{NOMES[pais]} - Balança por {descricao} - {per}',
            family='Segoe UI',weight='bold',fontsize=16,color=TITLE_GRAY,ha='left',va='top')
    moeda='€ bi' if pais=='ue' else 'US$ bi'
    ax.text(xl,.922,'EXPORTAÇÕES',fontsize=12,weight='bold',color=TITLE_GRAY,ha='right')
    ax.text(xr+bw,.922,'IMPORTAÇÕES',fontsize=12,weight='bold',color=TITLE_GRAY,ha='left')
    ax.text(.5,.922,moeda,fontsize=10,color='#808080',ha='center')
    ax.text(xl,.104,f'Exportações: {fmt(exp)}',ha='right',fontsize=11,weight='bold',color=TITLE_GRAY)
    ax.text(xr+bw,.104,f'Importações: {fmt(imp)}',ha='left',fontsize=11,weight='bold',color=TITLE_GRAY)
    cor=cores['Superávit comercial'] if saldo>=0 else cores['Déficit comercial']
    ax.text(.5,.056,f'{"Superávit" if saldo>=0 else "Déficit"}: {fmt(abs(saldo))} {moeda}',
            ha='center',fontsize=13,weight='bold',color=cor)
    fig.savefig(arquivo,dpi=240,bbox_inches='tight',pad_inches=.025,facecolor='white')
    plt.close(fig)
    assert np.isclose(sum(esq.values()),sum(direita.values()))
    return dict(pais=pais,tipo=tipo,periodo=modo,inicio=ini,fim=fim,
                moeda='EUR' if pais=='ue' else 'USD',exportacoes_bi=exp,
                importacoes_bi=imp,saldo_bi=saldo,fechamento_esquerda_bi=sum(esq.values()),
                fechamento_direita_bi=sum(direita.values()),arquivo=str(arquivo))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--paises',nargs='+',default=list(NOMES),choices=list(NOMES))
    args=ap.parse_args()
    manifesto=BASE/'fontes.json'
    if manifesto.exists():
        for item in json.loads(manifesto.read_text(encoding='utf-8')).get('bases',[]):
            from pathlib import Path
            p=Path(item['arquivo'])
            assert hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256'], f'Base alterada: {p}'
    validacao=[]; tabelas=[]
    for pais in args.paises:
        pasta=SAIDA/pais; pasta.mkdir(parents=True,exist_ok=True)
        numero=0
        for tipo in ['parceiros','produtos']:
            original=pd.read_csv(BASE/(pais+'_'+tipo+'.csv'))
            sa=pd.read_csv(BASE/(pais+'_'+tipo+'_sa.csv'))
            referencia,_,_=acumular(original,'12m')
            ordem=list((referencia.exp+referencia.imp).sort_values(ascending=False).index)
            if 'Demais parceiros' in ordem:
                ordem.remove('Demais parceiros'); ordem.append('Demais parceiros')
            for modo,d in [('12m',original),('mensal',sa)]:
                numero+=1
                m,ini,fim=acumular(d,modo)
                # Ranking comum aos dois lados e aos dois períodos.
                m=m.reindex(ordem)
                arq=pasta/f'{numero}_{pais}_{tipo}_{modo}_{fim.replace("-","")}.png'
                validacao.append(desenhar(m,pais,tipo,modo,ini,fim,arq))
                tabelas.append(m.reset_index().assign(pais=pais,tipo=tipo,periodo=modo,inicio=ini,fim=fim))
                print(str(arq),flush=True)
    pd.concat(tabelas,ignore_index=True).to_csv(BASE/'valores_graficos.csv',index=False)
    (BASE/'validacao.json').write_text(json.dumps(validacao,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':
    main()
