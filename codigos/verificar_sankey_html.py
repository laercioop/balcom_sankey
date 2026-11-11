"""Teste de navegador das 16 análises, exportação e links do HTML da pasta 12."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'graficos/12_sankey_animado'


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True)
        page = browser.new_page(viewport={'width': 1440, 'height': 1250}, reduced_motion='reduce')
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto((OUTPUT / 'index.html').as_uri())
        page.wait_for_function('CROSS !== null',timeout=120000)
        assert page.locator('#drawing path').count() > 0
        checked = []
        for country in ['brasil', 'eua', 'ue', 'china']:
            page.select_option('#country', country)
            for mode in ['mensal', '12m']:
                page.select_option('#mode', mode)
                for analysis in ['parceiros', 'produtos']:
                    page.click('[data-type="' + analysis + '"]')
                    for index in [0, int(page.locator('#slider').get_attribute('max'))]:
                        page.select_option('#month', str(index))
                        assert page.locator('#time-current').inner_text() == page.locator('#period').inner_text()
                        assert page.locator('#slider').get_attribute('aria-valuetext') == page.locator('#period').inner_text()
                        assert page.evaluate("document.querySelectorAll('path[d*=NaN]').length") == 0
                        assert page.evaluate("document.querySelectorAll('path[d*=Infinity]').length") == 0
                        assert page.evaluate("(()=>{const g=geometry(dataset().frames[index]);return Math.abs(sum(g.filter(p=>p.side===0).map(p=>p.v))-sum(g.filter(p=>p.side===1).map(p=>p.v)))})()") < 1e-8
                    assert ('€' if country == 'ue' else 'US$') in page.locator('#unit').inner_text()
                    # Clique real no saldo: o detalhamento precisa reconciliar os
                    # déficits e superávits de todas as categorias com o líquido.
                    balance = page.locator('#drawing .category[aria-hidden="false"][aria-label$="comercial"]')
                    balance.locator('rect').first.click()
                    assert page.locator('#zoom').is_visible()
                    assert page.locator('#zoom-content tbody tr').count() == page.evaluate('dataset().frames[index].exp.filter((v,i)=>v!==dataset().frames[index].imp[i]).length'), (country, mode, analysis, page.locator('#zoom-title').inner_text(), page.locator('#zoom-content').inner_text())
                    totals = page.locator('.zoom-summary strong').all_text_contents()
                    assert totals[0] == page.locator('#exp').inner_text()
                    assert totals[1] == page.locator('#imp').inner_text()
                    assert totals[2].replace('-', '') == page.locator('#balance').inner_text()
                    page.keyboard.press('Escape')
                    assert not page.locator('#zoom').is_visible()
                    checked.append(country + '_' + analysis + '_' + mode)
        page.select_option('#country', 'brasil')
        page.select_option('#mode', 'mensal')
        page.click('[data-type="parceiros"]')
        page.screenshot(path=str(OUTPUT / 'preview_desktop.png'), full_page=True)
        page.locator('#drawing .category').first.focus()
        page.keyboard.press('Enter')
        assert page.locator('#cross-chart').count() == 1
        assert not page.locator('#zoom').is_visible()
        assert not page.locator('#chart').is_visible()
        page.click('#back')
        assert page.locator('#chart').is_visible()
        # Produto/fluxo/mês devem ser preservados; origem à esquerda, destino à direita.
        page.click('[data-type="produtos"]')
        page.select_option('#month', page.locator('#slider').get_attribute('max'))
        fuel = page.evaluate('dataset().names.indexOf("Combustíveis")')
        for side in [0, 1]:
            offset = page.evaluate('dataset().names.length+2') * side + fuel
            page.locator('#drawing .category').nth(offset).locator('rect').first.click()
            assert page.locator('#cross-chart').get_attribute('data-flow') == ('imp' if side else 'exp')
            assert page.locator('#cross-chart').get_attribute('data-month') == page.evaluate('dataset().frames[index].date')
            assert page.locator('#cross-chart').get_attribute('aria-label').startswith('País de origem' if side else 'Produto')
            assert page.evaluate('(s)=>Math.abs(Number(document.querySelector("#cross-chart").dataset.total)-sum(crossRows(s,dataset().names.indexOf("Combustíveis")).rows.map(r=>r.valor)))', side) < 1e-9
            if side:
                page.screenshot(path=str(OUTPUT / 'preview_combustiveis_importacoes.png'), full_page=True)
            assert not page.locator('#chart').is_visible()
            assert not page.locator('#zoom').is_visible()
            before = page.locator('#month').input_value()
            page.click('#prev')
            assert page.locator('#cross-chart').get_attribute('data-month') == page.evaluate('dataset().frames[index].date')
            page.click('#next')
            assert page.locator('#month').input_value() == before
            page.click('#back')
            assert page.locator('#month').input_value() == before
            assert page.locator('#chart').is_visible()
        for side in [0, 1]:
            page.locator('.flow-heading').nth(side).focus()
            page.keyboard.press('Enter')
            assert page.locator('#cross-chart').count() == 1
            assert page.evaluate('(s)=>Math.abs(Number(document.querySelector("#cross-chart").dataset.total)-sum(crossRows(s,null).rows.map(r=>r.valor)))', side) < 1e-9
            page.keyboard.press('Escape')
        page.evaluate('openCross(null,0)')
        total_before=page.locator('#cross-chart').get_attribute('data-total')
        page.select_option('#cross-limit','0')
        assert page.locator('#cross-chart').get_attribute('data-total')==total_before
        assert page.locator('#cross-chart text').count()>50
        with page.expect_download() as exported:
            page.click('#download-csv')
        import csv,io
        csv_rows=list(csv.reader(io.StringIO(Path(exported.value.path()).read_text(encoding='utf-8-sig')),delimiter=';'))
        assert len(csv_rows)-1==page.evaluate('crossRows(0,null).rows.length')
        page.select_option('#cross-limit','12')
        page.keyboard.press('Escape')
        page.select_option('#mode', '12m')
        page.evaluate('openCross(null,1)')
        assert page.locator('#cross-chart').count() == 1
        page.keyboard.press('Escape')
        page.select_option('#country', 'eua')
        # A divulgação do agregado por parceiro pode anteceder o cruzamento.
        available = page.evaluate("dataset().frames.map((f,j)=>({f,j})).filter(({f})=>{const c=CROSS[country];return c&&c.version===2&&c.coverage.some(r=>r[0]===f.date&&r[1]==='exp')}).at(-1)?.j")
        assert available is not None
        page.select_option('#mode', 'mensal')
        available = page.evaluate("dataset().frames.map((f,j)=>({f,j})).filter(({f})=>CROSS[country].coverage.some(r=>r[0]===f.date&&r[1]==='exp')).at(-1).j")
        page.select_option('#month',str(available))
        page.evaluate('openCross(null,0)')
        assert page.locator('#cross-chart').count() == 1
        page.keyboard.press('Escape')
        # Quatro países, ambos os lados e tipos: primeiro/último mês cobertos.
        cross_checked = []
        for selected in ['brasil','eua','ue','china']:
            page.select_option('#country', selected)
            for selected_mode in ['mensal','12m']:
                page.select_option('#mode',selected_mode)
                for analysis in ['parceiros','produtos']:
                    page.click('[data-type="'+analysis+'"]')
                    for side in [0,1]:
                        covered = page.evaluate("(side)=>{const c=CROSS[country],fl=side?'imp':'exp',months=new Set(c.coverage.filter(r=>r[1]===fl).map(r=>r[0]));return dataset().frames.map((f,j)=>({f,j})).filter(({f})=>{let cursor=mode==='12m'?f.start:f.date;while(cursor<=f.date){if(!months.has(cursor))return false;const [y,m]=cursor.split('-').map(Number);cursor=m===12?(y+1)+'-01':y+'-'+String(m+1).padStart(2,'0')}return true}).map(x=>x.j)}",side)
                        assert covered, (selected,selected_mode,analysis,side)
                        for frame in sorted(set([covered[0],covered[-1]])):
                            page.select_option('#month',str(frame))
                            page.evaluate('(side)=>openCross(null,side)',side)
                            assert page.locator('#cross-chart').count()==1
                            assert page.evaluate('(side)=>Math.abs(Number(document.querySelector("#cross-chart").dataset.total)-sum(crossRows(side,null).rows.map(r=>r.valor)))',side)<1e-8
                            page.keyboard.press('Escape')
                        cross_checked.append([selected,selected_mode,analysis,side])
        page.select_option('#country', 'brasil')
        page.select_option('#mode', 'mensal')
        page.select_option('#month', '0')
        page.evaluate('openCross(null,0)')
        assert page.locator('#cross-chart').count() == 1
        page.keyboard.press('Escape')
        page.select_option('#month', page.locator('#slider').get_attribute('max'))
        page.locator('#drawing .category[aria-hidden="false"][aria-label$="comercial"]').locator('rect').first.click()
        page.screenshot(path=str(OUTPUT / 'preview_zoom.png'), full_page=True)
        page.click('#zoom-close')
        with page.expect_download() as d:
            page.click('#download-svg')
        assert d.value.suggested_filename.endswith('.svg')
        with page.expect_download() as d:
            page.click('#download-csv')
        assert d.value.suggested_filename.endswith('.csv')
        url = page.url
        page.reload()
        page.wait_for_function('CROSS !== null',timeout=120000)
        assert page.url == url
        page.select_option('#speed', '500')
        page.select_option('#month', '0')
        page.click('#play')
        page.wait_for_timeout(1200)
        assert int(page.locator('#slider').input_value()) > 0
        page.click('#play')
        for speed, minimum in [('250', 1), ('125', 2)]:
            page.select_option('#speed', speed)
            page.select_option('#month', '0')
            page.click('#play')
            page.wait_for_timeout(650)
            page.click('#play')
            assert int(page.locator('#slider').input_value()) >= minimum
            assert page.locator('#time-current').inner_text() == page.locator('#period').inner_text()
        page.set_viewport_size({'width': 390, 'height': 844})
        page.screenshot(path=str(OUTPUT / 'preview_mobile.png'), full_page=True)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.locator('#drawing .category').first.locator('rect').first.click()
        page.screenshot(path=str(OUTPUT / 'preview_zoom_mobile.png'), full_page=True)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.click('#back')
        # Exercise real motion as well as the reduced-motion checks above.
        page.emulate_media(reduced_motion='no-preference')
        page.reload()
        page.wait_for_function('CROSS !== null',timeout=120000)
        page.set_viewport_size({'width': 1440, 'height': 1250})
        page.select_option('#month', page.locator('#slider').get_attribute('max'))
        page.evaluate('openCross(0,0)')
        assert page.locator('.sankey-transition-layer').count() == 1
        assert page.locator('#cross-chart').count() == 1
        assert page.locator('#chart').count() == 1
        page.wait_for_timeout(550)
        assert page.locator('.sankey-transition-layer').count() == 0
        page.click('#back')
        page.wait_for_timeout(550)
        assert page.locator('#chart').is_visible()
        # Rapid reversal and a new analysis must leave no stale snapshot/styles.
        page.evaluate('openCross(0,1);closeCross();openCross(null,0)')
        page.wait_for_timeout(550)
        assert page.locator('#cross-chart').count() == 1
        assert page.locator('.sankey-transition-layer').count() == 0
        page.evaluate("closeCross();selectType('produtos')")
        assert page.locator('#chart').is_visible()
        assert page.locator('.sankey-transition-layer').count() == 0
        assert page.evaluate('document.querySelector(".chart").getAnimations().length') == 0
        page.set_viewport_size({'width': 390, 'height': 844})
        page.evaluate('openCross(0,0)')
        page.wait_for_timeout(550)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.keyboard.press('Escape')
        page.wait_for_timeout(550)
        assert page.locator('#chart').is_visible()
        assert not errors, errors
        page.close()
        (OUTPUT / 'validacao_navegador.json').write_text(json.dumps({'analises': checked, 'erros_js': errors,
             'exportacoes_svg_csv': True, 'link_preservado': True, 'reproducao': True, 'mobile': True,
             'zoom_saldo_16_analises': True, 'zoom_categoria_teclado': True, 'zoom_mobile': True,
             'cruzamento_fluxo_mes_produto': True, 'titulos_cruzamento_teclado': True,
             'cobertura_cruzamento_estrita': True, 'cruzamentos_extremos': cross_checked,
             'detalhe_substitui_grafico': True, 'voltar_preserva_selecao': True,
             'transicao_detalhe_desktop_mobile': True, 'transicao_navegacao_rapida': True,
             'velocidades_4x_8x': True, 'periodo_acima_bolinha': True}, indent=2), encoding='utf-8')
        browser.close()
        print('16 análises: navegador, moeda, extremos, exportações, link, reprodução e mobile OK')


if __name__ == '__main__':
    main()
