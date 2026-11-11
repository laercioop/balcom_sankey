# Sankeys da balança comercial (pasta 11)

Os PNGs ficam em `graficos/11_balanca_comercial/{brasil,eua,ue,china}/`.
Cada subpasta tem exatamente quatro figuras:

1. Parceiros comerciais, soma dos últimos 12 meses originais.
2. Parceiros comerciais, último mês dessazonalizado.
3. Produtos (17 grupos granulares HS), soma dos últimos 12 meses originais.
4. Produtos, último mês dessazonalizado.

Exportações à esquerda, importações à direita. As faixas têm largura proporcional
ao valor. Uma faixa de superávit à direita ou déficit à esquerda fecha a identidade
contábil. A espinha central compara os dois totais: **não é uma matriz de relações
entre produtos nem entre parceiros**. A ordem e as cores de uma categoria são
iguais nos dois lados e nos dois períodos. O ranking é o da corrente de comércio
em 12 meses. As cores dos parceiros também são fixas entre países.
Zero não recebe faixa. As escalas se ajustam a cada figura;
não comparar larguras entre países ou entre o mensal e o acumulado.

## Fontes e unidades

Cobertura verificada em 10/11/2026 (o mensal e o final da janela de 12 meses
usam o mesmo mês dentro de cada análise):

| País | Parceiros | Produtos |
|---|---|---|
| Brasil | out/2026 | out/2026 |
| EUA | set/2026 | ago/2026 |
| UE27 | ago/2026 | ago/2026 |
| China | out/2026 | set/2026 |

O índice do Monthly Bulletin GACC ainda não tinha link da tabela HS2 de outubro
na consulta feita para este trabalho, embora os totais e parceiros de outubro
já constassem da planilha local atualizada. As lacunas históricas dos valores
mensais de produtos chineses são preservadas como ausentes; a janela corrente
de 12 meses e o mensal exibido são completos.

- **Brasil/parceiros:** MDIC, `SH/BLOCOS_PAISES.xlsx`, aba `DADOS_SH`, sem
  duplicatas por mês, fluxo e país. A UE27 é agregada com composição fixa pelos
  códigos ISO dos 27 membros atuais, usando a tabela oficial de países já
  preservada na base Sankey. Os demais parceiros são países individuais.
- **Brasil/produtos:** contrato `brasil_hs2.csv` para o histórico anterior a 2026;
  em 2026, agregação direta dos CSVs oficiais `EXP_2026.csv` e `IMP_2026.csv`
  já baixados pelo BALCOM em `SECEX/balcom_r/downloads/`. As somas são conferidas
  contra `x_tot` e `m_tot` da aba CGCE de `SECEX/balcom_r.xlsx`. Este fluxo
  não altera os quatro pipelines anteriores nem suas bases dessazonalizadas.
- **EUA/parceiros:** Census, `foreign-trade/balance/country.xlsx`, valores
  originais em US$ milhões. Exclui agregados regionais e o total ajustado antes
  de somar parceiros. UE27 agregada com composição fixa pela soma dos membros.
  O total original do próprio arquivo determina o residual. A API Census
  exigia chave na consulta realizada; o XLSX oficial dispensa chave.
- **UE27/parceiros:** Eurostat Comext DS-045409, produto TOTAL, reporter
  EU27_2020. Onze parceiros selecionados e residual em relação a
  EXT_EU27_2020. Comércio intra-UE excluído. Importações CIF, exportações FOB.
- **China/parceiros:** planilha local
  `Internacional/China/setor externo/setor_externo_china.xlsx`, abas
  EviewsPaises e EViewsM. Fonte identificada na planilha: GACC/Bloomberg.
  São nove parceiros/blocos sem sobreposição (ASEAN é mantida como bloco),
  mais residual. A composição histórica do agregado europeu segue a fonte.
  Os totais chineses dessa planilha são arredondados a US$ 1 milhão.
- **Demais produtos:** contratos HS2 dos pipelines, 17 grupos de `comum.py`.
  Diferença positiva entre capítulos e TOTAL entra em Instrumentos e diversos.
  O mensal usa a base granular X-13 existente em `dados/dessaz/`.

Os valores finais são bilhões da moeda original: **US$** para Brasil, EUA e
China, **euros para UE27**. Não há conversão de moeda. As importações americanas
da base de produtos seguem o tratamento CIF/FOB descrito no pipeline; no ajuste
mensal os meses com apenas CIF são convertidos por `dessaz.py`.

## Dessazonalização e períodos

O mensal por parceiro usa ajuste direto por série, reutilizando `dessaz.py`:
td/Páscoa e feriados brasileiros do BALCOM; td/Páscoa para EUA e UE; td e
Ano Novo Chinês para China. Transformação automática, automdl, AO/LS/TC e D11.
As reservas de modelo são as do projeto. Se as reservas falharem ou gerarem
valores negativos, tenta inícios de ano posteriores, com pelo menos 48 meses.
O trecho anterior ao início admissível permanece original e é marcado
`ajustado=False`. O gráfico mensal exige ajuste em todas as séries exibidas.
Não se usa a participação original para repartir um total ajustado.

O mensal de produtos do Brasil é reestimado até outubro, com as mesmas regras.
Os demais países reutilizam o ajuste granular existente. Totais mensais são
**indiretos**, soma das categorias ajustadas da respectiva análise. Portanto,
parceiros e produtos podem produzir totais mensais ajustados distintos; os
períodos também podem diferir quando há defasagem de publicação.

No acumulado de produtos da China, usa-se a identidade com os acumulados
publicados: `acum(a,m) + acum(a-1,12) - acum(a-1,m)`, incorporando revisões.
Para os parceiros chineses, a planilha só fornece valores mensais, então usa-se
a soma das doze observações mensais. Não se estima produto de outubro a partir
do total de outubro. Cada figura tem o mês efetivo no título e no nome.

Para Brasil/EUA, os doze principais parceiros são escolhidos pela corrente de
comércio dos últimos 12 meses e mantidos fixos no histórico usado no ajuste.
Os demais são somados antes do ajuste. Na UE e China, preserva-se a seleção
das fontes descrita acima. Assim não há sobreposição de blocos ou países.

## Atualização e auditoria

```powershell
python codigos/balanca_sankey_dados.py
python codigos/balanca_sankey.py
python -m unittest discover -s codigos -p test_balanca_sankey.py
```

`--offline` reprocessa os arquivos preservados em `brutos/`. Ambos os scripts
aceitam `--paises brasil eua ue china` para subconjuntos. Os CSVs oficiais locais
do Brasil e a planilha da China precisam ser atualizados pelos fluxos originais.
Para atualizar os produtos de EUA/UE/China, atualizar os respectivos pipelines e
`dessaz.py` antes de preparar a pasta 11. Ao avançar o mês, arquivar os PNGs
anteriores antes de regenerar para manter quatro PNGs correntes por país.

- `fontes.json`: caminhos, URLs, hashes SHA-256 e cobertura por análise.
- `{pais}_parceiros.csv` / `_sa.csv`: partição geográfica original e ajustada.
- `{pais}_produtos.csv` / `_sa.csv`: grupos HS originais e ajustados.
- `{pais}_diagnostico.csv`: status, modelo e início admissível por parceiro.
- `brasil_produtos_diagnostico.csv`: diagnóstico da reestimação dos produtos.
- `valores_graficos.csv`: todos os números exibidos, em bilhões.
- `validacao.json`: períodos, totais, saldo e fechamento das duas colunas.

Validações interrompem o processo em caso de duplicatas, janela incompleta,
valores negativos/ausentes, parcelas acima do total, ajuste indisponível ou
divergência com a CGCE brasileira. Confira também as imagens renderizadas.
Preserve `brutos/` e os CSVs de auditoria.

### Detalhe Produto × País no painel animado

`coleta_cruzado.py` coleta as bases conjuntas dos quatro países e
`balanca_sankey_cruzado.py` as compacta com hashes e validações.
O detalhe mantém fluxo e período selecionados, com valores originais na moeda
da fonte e sem ratear ajustes sazonais. Exige cobertura
integral para 12m; informa indisponibilidade quando falta cobertura ou base.
Importações: países à esquerda → produtos à direita. Exportações: produtos
à esquerda → países à direita. Categorias filtram produto ou parceiro/bloco;
os títulos superiores abrem o fluxo completo. Os 12 maiores países do recorte
ficam individuais, os demais em Outros países; o seletor permite 30 ou todos.
O saldo mantém a reconciliação anterior. Marginais não geram vínculos.
O cruzamento substitui o Sankey na própria tela. Voltar fica abaixo do total
de exportações; Esc retorna também. A linha do tempo atualiza o detalhe e a
volta preserva mês/país/análise. SVG/CSV exportam o cruzamento quando aberto.
## Coleta do cruzamento histórico Produto × Parceiro

Atualização: `python codigos/coleta_cruzado.py --paises brasil ue eua china`.
Use `--eua-comtrade` para a alternativa aos dados diretos do Census.
Credenciais apenas nas variáveis `CENSUS_API_KEY` e `COMTRADE_API_KEY`.
`--offline` reaproveita os caches e não gasta cota. No Comtrade, permite
compactar apenas os meses já coletados; o status continua incompleto se
houver meses faltantes. Não confundir o JSON gerado com cobertura integral.

Os JSONs `{pais}_produto_pais.json` v2 contêm dicionários e células mensais
`[fluxo, produto, pais, bloco, valor_bilhoes]`, com índices nos dicionários.
`coverage` declara pares `[mes, fluxo]` cuja partição foi coletada. Fonte,
unidade, hashes, duplicatas e diferenças da base agregada ficam em `validacao`.
O fechamento usa os totais oficiais da própria fonte; valores publicados sem
detalhamento são identificados, nunca distribuídos entre produtos ou países.
Não se fabricam vínculos a partir das bases marginais de produtos e parceiros.

Brasil e UE são confrontados com todos os produtos comuns da pasta 11;
Brasil também confere os totais com `CGCE` de `balcom_r.xlsx`. Divergências
de versões/fontes no Comtrade são exportadas em `{pais}_cruzado_divergencias.csv`.
Importações do Comtrade são CIF; diferem dos valores de alfândega do Census.
O cruzamento mensal é original, sem ajuste sazonal. O acumulado exige 12 meses
completos. Lacunas não viram zero. Consulte `coleta_cruzado_*_status.json`.

Proteção da cota: `comtrade_cota.py`, 450 tentativas/24h em janela móvel,
SQLite compartilhado por todos os processos do projeto, reserva antes do
envio, sem repetição automática. Uma leitura de cache não consome cota.
O registro não conhece chamadas feitas fora deste projeto. Testes de cota
usam apenas SQLite temporário e transporte falso: `test_comtrade_cota.py`.

O HTML continua autocontido: gzip/base64 descompactado localmente pelo navegador.
O preparo da publicação não copia os brutos, o banco de cota ou credenciais.

Reino Unido/UE27 em 2015–2020: soma dos 27 membros no Comext, com TOTAL
confrontado ao agregado EU27_2020/GB. Não há rateio do total. Eventuais sobras
sem capítulo ficam identificadas como Produto não detalhado, no filtro do
grupo Instrumentos e diversos. Census: consultas por ano, mantendo MONTH
separado e países conferidos contra o mundo para cada HS2/mês. Revisões e
diferenças da base Comtrade anterior ficam em eua_cruzado_divergencias.csv.
