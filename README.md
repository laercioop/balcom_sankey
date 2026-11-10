# Balança comercial · Sankeys

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
