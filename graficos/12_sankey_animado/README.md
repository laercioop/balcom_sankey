# Balança comercial: Sankeys interativos

Abra `index.html` no navegador. O nome antigo `brasil_sankey_mensal.html` também
abre o painel completo. Ambos são autocontidos, offline e podem ser copiados.

- Brasil, EUA, UE27 e China.
- Parceiros ou produtos; mensal dessazonalizado ou acumulado original em 12 meses.
- Mês, linha do tempo, reprodução, velocidade, repetição e escala fixa por análise.
- Downloads SVG e CSV (histórico da seleção), link para a seleção específica.
- UE27 em euros; demais países em dólares americanos, sempre em bilhões.
- Cobertura própria por análise, com o período efetivo mostrado na tela.
- Em telas pequenas, role horizontalmente dentro do gráfico.

Ordem, cores e cálculos da pasta 11. Totais mensais indiretos podem diferir entre
parceiros e produtos. Produtos chineses usam a identidade com acumulados publicados
no 12m; janelas com observações ou referências anuais faltantes são omitidas.
A escala fixa vale para o histórico da análise selecionada, sem conversão cambial.
O centro é contábil e não representa relações bilaterais entre categorias.

Clique em um produto, parceiro ou título do fluxo para abrir Produto × País.
O detalhe abrange os quatro países, conforme a cobertura das bases conjuntas,
nos dois fluxos e no mensal ou 12 meses. Use 12 maiores, 30 maiores ou todos
os países; o CSV inclui todas as células da seleção. Voltar ou Esc retorna.
São valores originais; revisões da fonte e diferenças de classificação podem
mudar a composição em relação às barras anteriores. Sem rateio de ajustes.
Os 12 meses precisam estar completos. Meses ausentes na fonte não viram zero.
O cruzamento chinês cobre jan/2016 a dez/2024. 2015 e 2025–2026 não retornaram
registros no UN Comtrade e aguardam outra base para completar o cruzamento.

Os dados detalhados estão comprimidos dentro do HTML. A abertura continua
offline e requer navegador atual com DecompressionStream (Edge/Chrome/Firefox).

## Atualizar e verificar

```powershell
python codigos/balanca_sankey_animado.py
python codigos/verificar_sankey_html.py
python codigos/preparar_publicacao_sankey.py
```

O último comando sincroniza o clone `publicacao/`, sem commit/push automáticos.
O teste de navegador requer Playwright e Microsoft Edge. Auditorias:
`validacao.json` e `validacao_navegador.json`. O gerador verifica hashes das 16
bases, duplicatas, valores, cobertura, fechamento de cada quadro e confronta os
últimos quadros com os números exportados pelos PNGs da pasta 11.

Site: https://laercioop.github.io/balcom_sankey/
Repositório: https://github.com/laercioop/balcom_sankey
GitHub Pages publica a raiz da branch `main`; o HTML da raiz é uma cópia deste
`index.html`. Template: `codigos/balanca_sankey_animado.html`.
