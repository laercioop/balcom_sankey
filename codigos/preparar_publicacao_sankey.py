"""Sincroniza somente as pastas 11/12 e suas dependências no clone publicacao/.

Não envia alterações. Depois de revisar: git -C publicacao add .; commit; push.
Brutos e caminhos internos do manifesto não são publicados.
"""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'publicacao'


def main():
    assert (DEST / '.git').is_dir(), 'Clone o repositório em publicacao/ primeiro'
    def copiar(rel, target=None):
        p = DEST / (target or rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, p)
    for nome in ['balanca_sankey_animado.py', 'balanca_sankey_animado.html', 'balanca_sankey.py',
                 'comum.py', 'estilo_ps.py', 'sankey.py', 'verificar_sankey_html.py',
                 'preparar_publicacao_sankey.py', 'balanca_sankey_cruzado.py']:
        copiar('codigos/' + nome)
    for pais in ['brasil', 'eua', 'ue', 'china']:
        for tipo in ['parceiros', 'produtos']:
            for sufixo in ['', '_sa']:
                copiar('dados/balanca_sankey/' + pais + '_' + tipo + sufixo + '.csv')
    for nome in ['valores_graficos.csv', 'README.md']:
        copiar('dados/balanca_sankey/' + nome)
    for p in (ROOT / 'dados/balanca_sankey').glob('*_produto_pais.json'):
        copiar(p.relative_to(ROOT))
    original = json.loads((ROOT / 'dados/balanca_sankey/fontes.json').read_text(encoding='utf-8'))
    manifesto = dict(cobertura=original['cobertura'], bases=[dict(arquivo=Path(x['arquivo']).name,
                    sha256=x['sha256']) for x in original['bases']])
    (DEST / 'dados/balanca_sankey/fontes.json').write_text(json.dumps(manifesto, ensure_ascii=False, indent=2), encoding='utf-8')
    for p in (ROOT / 'graficos/11_balanca_comercial').glob('*/*.png'):
        copiar(p.relative_to(ROOT))
    for nome in ['index.html', 'brasil_sankey_mensal.html', '.nojekyll', 'validacao.json',
                 'validacao_navegador.json', 'README.md']:
        p = ROOT / 'graficos/12_sankey_animado' / nome
        if p.exists():
            copiar(p.relative_to(ROOT))
    copiar('graficos/12_sankey_animado/index.html', 'index.html')
    (DEST / '.nojekyll').touch()
    (DEST / '.gitignore').write_text('__pycache__/\n*.pyc\npublicacao/\npreview_*.png\n', encoding='utf-8')
    (DEST / 'requirements.txt').write_text('numpy\npandas\nmatplotlib\nscipy\nPillow\n', encoding='utf-8')
    (DEST / 'README.md').write_text('''# Balança comercial · Sankeys

[Abrir painel interativo](https://laercioop.github.io/balcom_sankey/)

Brasil, EUA, UE27 e China; parceiros ou produtos; mensal dessazonalizado ou
acumulado de 12 meses. Todas as 16 análises da pasta 11 com histórico animado.
Seleção de mês, velocidade, escala fixa, repetição, exportação SVG/CSV e links
para uma seleção específica. HTML autocontido e sem dependências de rede.

UE27 em euros; demais países em dólares americanos. Mensal com totais indiretos
por análise; acumulados com dados originais. Produtos chineses usam acumulados
publicados; janelas incompletas são omitidas. Cada análise tem cobertura própria.
O centro do Sankey fecha a identidade contábil; não representa vínculos bilaterais.

## Reproduzir

Abra `index.html` offline ou instale `requirements.txt` e execute:

```sh
python codigos/balanca_sankey_animado.py
```

O gerador escreve `graficos/12_sankey_animado/index.html`. Para publicar uma
atualização, copie esse arquivo também para `index.html` da raiz e envie à branch
`main`. GitHub Pages está configurado para publicar a raiz de `main`.

As bases compactas utilizadas pelo gerador estão em `dados/balanca_sankey/`.
O manifesto contém hashes SHA-256. A validação confronta as 16 análises com
`valores_graficos.csv`, exportado pelos PNGs da pasta 11. Os PNGs também estão
em `graficos/11_balanca_comercial/`. Downloads brutos permanecem no projeto local.
Para verificar os controles: instale `playwright>=1.57.0` e execute
`python codigos/verificar_sankey_html.py` com Microsoft Edge instalado.
''', encoding='utf-8')
    print('Publicação preparada em', DEST)


if __name__ == '__main__':
    main()
