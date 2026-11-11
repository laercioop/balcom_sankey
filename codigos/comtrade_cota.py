"""Barreira local conservadora para a cota compartilhada do UN Comtrade.

Reserva persistida ANTES da chamada, inclusive falhas/timeouts. No máximo
450 chamadas por janela móvel de 24h (50 de reserva dos 500 informados).
Sem retentativas automáticas. Testes usam transporte falso.
O arquivo não contém chaves; todas as instâncias usam o mesmo SQLite.
"""
import json
import gzip
import os
import sqlite3
import time
import urllib.parse
import urllib.request
from contextlib import closing
from contextlib import contextmanager
from pathlib import Path

LIMITE = 450
JANELA = 24 * 3600
BANCO = Path(__file__).resolve().parents[1] / 'dados/balanca_sankey/brutos/cruzado/comtrade_cota.sqlite'


class CotaExcedida(RuntimeError):
    pass


def reservar(banco=BANCO, agora=None, limite=LIMITE, intervalo=0):
    agora = time.time() if agora is None else agora
    banco = Path(banco)
    banco.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(str(banco), timeout=30)) as db:
        db.execute('CREATE TABLE IF NOT EXISTS chamadas (instante REAL NOT NULL)')
        db.execute('BEGIN IMMEDIATE')
        usados = db.execute('SELECT COUNT(*) FROM chamadas WHERE instante > ?', (agora-JANELA,)).fetchone()[0]
        if usados >= min(limite, LIMITE):
            raise CotaExcedida(f'Comtrade: limite local atingido ({usados}/{min(limite, LIMITE)} em 24h). Retome depois, usando o cache.')
        ultimo = db.execute('SELECT MAX(instante) FROM chamadas').fetchone()[0]
        instante = max(agora, (ultimo or 0)+intervalo) if intervalo else agora
        db.execute('INSERT INTO chamadas VALUES (?)', (instante,))
        db.commit()
    if intervalo:
        time.sleep(max(0, instante-time.time()))
    return usados + 1


@contextmanager
def chamada_exclusiva(banco):
    """Uma única consulta HTTP em voo, inclusive entre processos Windows."""
    import msvcrt
    lock = Path(banco).with_suffix('.http.lock')
    lock.parent.mkdir(parents=True, exist_ok=True)
    with open(lock, 'a+b') as f:
        if f.tell() == 0:
            f.write(b'0')
            f.flush()
        while True:
            try:
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                time.sleep(.25)
        try:
            yield
        finally:
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)


def consultar(params, cache, banco=BANCO, transporte=urllib.request.urlopen):
    if Path(cache).exists():
        return _consultar(params,cache,banco,transporte)
    with chamada_exclusiva(banco):
        return _consultar(params,cache,banco,transporte)


def _consultar(params, cache, banco=BANCO, transporte=urllib.request.urlopen):
    """Apenas endpoint de dados. Nem retentativas nem testes de conectividade."""
    cache = Path(cache)
    if cache.exists():
        raw = cache.read_bytes()
        return json.loads(gzip.decompress(raw) if cache.suffix == '.gz' else raw)
    key = os.environ.get('COMTRADE_API_KEY')
    if not key:
        raise RuntimeError('Configure COMTRADE_API_KEY para coletar o cruzamento.')
    # Uma só agenda global entre países: evita rajadas e HTTP 429, sem gastar
    # chamadas de teste nem repetir a mesma consulta automaticamente.
    reservar(banco, intervalo=2)
    params = dict(params)
    # O cliente oficial usa reportercode (minúsculo); reporterCode é ignorado
    # silenciosamente em algumas rotas e pode retornar um falso vazio.
    if 'reporterCode' in params:
        params['reportercode'] = params.pop('reporterCode')
    url = 'https://comtradeapi.un.org/data/v1/get/C/M/HS?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'Ocp-Apim-Subscription-Key': key, 'User-Agent':'Mozilla/5.0', 'Accept-Encoding':'gzip'})
    try:
        with transporte(req, timeout=180) as r:
            raw = r.read()
            if r.headers.get('Content-Encoding') == 'gzip':
                raw = gzip.decompress(raw)
            obj = json.loads(raw)
    except Exception as exc:
        # Não imprime Request/headers nem chave. A reserva continua consumida.
        detalhe = str(getattr(exc, 'code', type(exc).__name__))
        espera = exc.headers.get('Retry-After') if hasattr(exc, 'headers') else None
        raise RuntimeError(f'Comtrade: chamada falhou ({detalhe}; Retry-After={espera}); reserva consumida, sem repetição automática.') from None
    if obj.get('error'):
        raise RuntimeError('Comtrade: fonte retornou erro; reserva consumida, sem repetição automática.')
    cache.parent.mkdir(parents=True, exist_ok=True)
    tmp = cache.with_suffix('.tmp')
    raw = json.dumps(obj, ensure_ascii=False).encode('utf-8')
    tmp.write_bytes(gzip.compress(raw) if cache.suffix == '.gz' else raw)
    tmp.replace(cache)
    return obj
