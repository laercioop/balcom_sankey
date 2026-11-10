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
