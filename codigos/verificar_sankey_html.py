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
        page.select_option('#mode', '12m')
        page.evaluate('openCross(null,1)')
        assert 'não cobre todo este período' in page.locator('#cross-content').inner_text()
        assert page.locator('#cross-chart').count() == 0
        page.keyboard.press('Escape')
        page.select_option('#country', 'eua')
        page.evaluate('openCross(null,0)')
        assert 'ainda não está disponível' in page.locator('#cross-content').inner_text()
        page.keyboard.press('Escape')
        page.select_option('#country', 'brasil')
        page.select_option('#mode', 'mensal')
        page.select_option('#month', '0')
        page.evaluate('openCross(null,0)')
        assert 'não cobre todo este período' in page.locator('#cross-content').inner_text()
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
        assert not errors, errors
        page.close()
        (OUTPUT / 'validacao_navegador.json').write_text(json.dumps({'analises': checked, 'erros_js': errors,
             'exportacoes_svg_csv': True, 'link_preservado': True, 'reproducao': True, 'mobile': True,
             'zoom_saldo_16_analises': True, 'zoom_categoria_teclado': True, 'zoom_mobile': True,
             'cruzamento_fluxo_mes_produto': True, 'titulos_cruzamento_teclado': True,
             'cobertura_cruzamento_estrita': True,
             'detalhe_substitui_grafico': True, 'voltar_preserva_selecao': True,
             'velocidades_4x_8x': True, 'periodo_acima_bolinha': True}, indent=2), encoding='utf-8')
        browser.close()
        print('16 análises: navegador, moeda, extremos, exportações, link, reprodução e mobile OK')


if __name__ == '__main__':
    main()
