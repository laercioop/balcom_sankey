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
                        assert page.evaluate("document.querySelectorAll('path[d*=NaN]').length") == 0
                        assert page.evaluate("document.querySelectorAll('path[d*=Infinity]').length") == 0
                        assert page.evaluate("(()=>{const g=geometry(dataset().frames[index]);return Math.abs(sum(g.filter(p=>p.side===0).map(p=>p.v))-sum(g.filter(p=>p.side===1).map(p=>p.v)))})()") < 1e-8
                    assert ('€' if country == 'ue' else 'US$') in page.locator('#unit').inner_text()
                    checked.append(country + '_' + analysis + '_' + mode)
        page.select_option('#country', 'brasil')
        page.select_option('#mode', 'mensal')
        page.click('[data-type="parceiros"]')
        page.screenshot(path=str(OUTPUT / 'preview_desktop.png'), full_page=True)
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
        page.set_viewport_size({'width': 390, 'height': 844})
        page.screenshot(path=str(OUTPUT / 'preview_mobile.png'), full_page=True)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert not errors, errors
        page.close()
        (OUTPUT / 'validacao_navegador.json').write_text(json.dumps({'analises': checked, 'erros_js': errors,
             'exportacoes_svg_csv': True, 'link_preservado': True, 'reproducao': True, 'mobile': True}, indent=2), encoding='utf-8')
        browser.close()
        print('16 análises: navegador, moeda, extremos, exportações, link, reprodução e mobile OK')


if __name__ == '__main__':
    main()
