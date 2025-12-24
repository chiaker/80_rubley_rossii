from typing import List, Optional
import time
import os
import logging
from typing import Dict, Iterable

import requests
from dotenv import load_dotenv

load_dotenv()

logging.getLogger().setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)


def fetch_current_crypto_prices(symbols: Iterable[str], convert: str = 'USD') -> Dict[str, dict]:
    """Fetch current crypto prices from CoinMarketCap for given symbols.

    Returns a mapping symbol -> {price: float, percent_change_24h: float}
    If no API key is configured or request fails, returns an empty dict.
    """
    api_key = os.environ.get('CMC_API_KEY')
    if not api_key:
        logger.debug('CMC_API_KEY not set; skipping price fetch')
        return {}

    symbols = [s.upper() for s in set(symbols) if s]
    if not symbols:
        return {}

    url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest'
    headers = {
        'Accept': 'application/json',
        'Accept-Encoding': 'deflate, gzip',
        'X-CMC_PRO_API_KEY': api_key,
    }
    params = {
        'symbol': ','.join(symbols),
        'convert': convert,
    }

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        payload = resp.json()
        data = payload.get('data', {})
        result = {}
        for sym in symbols:
            item = data.get(sym)
            if not item:
                continue
            quote = item.get('quote', {}).get(convert, {})
            price = quote.get('price')
            change = quote.get('percent_change_24h')
            result[sym] = {
                'price': price,
                'percent_change_24h': change,
            }
        return result
    except Exception as e:
        logger.exception('Failed to fetch prices from CMC: %s', e)
        return {}


def fetch_current_stock_prices(symbols: Iterable[str]) -> Dict[str, dict]:
    """Fetch current stock prices from Finnhub for given symbols.

    Returns a mapping symbol -> {price: float, percent_change: float, timestamp: int}
    If no API key is configured or request fails for a symbol, that symbol is omitted.
    Uses the Finnhub Quote endpoint: /quote?symbol=XXX
    """
    api_key = os.environ.get(
        'FINNHUB_API_KEY') or os.environ.get('FINNHUB_KEY')
    if not api_key:
        logger.debug('FINNHUB_API_KEY not set; skipping stock price fetch')
        return {}

    symbols = [s.upper() for s in set(symbols) if s]
    if not symbols:
        return {}

    base_url = 'https://finnhub.io/api/v1/quote'
    result: Dict[str, dict] = {}
    for sym in symbols:
        params = {'symbol': sym, 'token': api_key}
        try:
            resp = requests.get(base_url, params=params, timeout=8)
            resp.raise_for_status()
            payload = resp.json()
            # Finnhub /quote returns: c (current), h, l, o, pc (prev close), t (timestamp)
            c = payload.get('c')
            pc = payload.get('pc')
            t = payload.get('t')
            if c is None:
                continue
            try:
                price = float(c)
            except (TypeError, ValueError):
                continue

            percent_change = None
            try:
                if pc not in (None, 0):
                    percent_change = float(
                        (price - float(pc)) / float(pc) * 100)
            except Exception:
                percent_change = None

            result[sym] = {
                'price': price,
                'percent_change': percent_change,
                'timestamp': int(t) if isinstance(t, (int, float)) else None,
                'prev_close': pc,
            }
        except Exception as e:
            logger.debug('Failed to fetch Finnhub quote for %s: %s', sym, e)
            continue

    return result


# --- 24h series and sparkline generation ---
_coingecko_map_cache: Dict[str, str] = {}
_coingecko_map_cached_at: Optional[float] = None
# Manual overrides for common symbols -> CoinGecko ids to avoid ambiguous matches
_COINGECKO_MANUAL_OVERRIDES: Dict[str, str] = {
    'btc': 'bitcoin',
    'eth': 'ethereum',
    'usdt': 'tether',
}


def _ensure_coingecko_map() -> None:
    """Populate a simple map symbol -> id from CoinGecko (cached for 1 hour)."""
    global _coingecko_map_cache, _coingecko_map_cached_at
    try:
        if _coingecko_map_cached_at and time.time() - _coingecko_map_cached_at < 3600 and _coingecko_map_cache:
            return
        resp = requests.get(
            'https://api.coingecko.com/api/v3/coins/list', timeout=10)
        resp.raise_for_status()
        items = resp.json()
        m: Dict[str, str] = {}
        for it in items:
            sym = it.get('symbol')
            cid = it.get('id')
            if sym and cid:
                key = sym.lower()
                if key not in m:
                    m[key] = cid
        # merge manual overrides (manual wins)
        for k, v in _COINGECKO_MANUAL_OVERRIDES.items():
            m[k] = v
        _coingecko_map_cache = m
        _coingecko_map_cached_at = time.time()
    except Exception as e:
        logger.debug('Failed to build CoinGecko map: %s', e)


def fetch_24h_series(symbol: str, asset_type: str, convert: str = 'USD') -> List[float]:
    """Return a list of recent prices over the last 24 hours for the given symbol.

    For stocks: uses Finnhub `/stock/candle` at 5-minute resolution.
    For crypto: tries CoinGecko `/coins/{id}/market_chart?days=1` (public).
    Returns a list of floats (ordered oldest->newest). On error returns []
    """
    symbol = (symbol or '').strip()
    if not symbol:
        return []

    # STOCK via Finnhub
    if asset_type == 'STOCK':
        api_key = os.environ.get(
            'FINNHUB_API_KEY') or os.environ.get('FINNHUB_KEY')
        if not api_key:
            logger.warning(
                'FINNHUB_API_KEY not set; cannot fetch stock data for %s', symbol)
            return []
        to_ts = int(time.time())
        from_ts = to_ts - 24 * 3600
        url = 'https://finnhub.io/api/v1/stock/candle'
        params = {'symbol': symbol, 'resolution': '5',
                  'from': from_ts, 'to': to_ts, 'token': api_key}
        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            status = data.get('s')
            if status != 'ok':
                error_msg = data.get('error', 'Unknown error')
                logger.warning(
                    'Finnhub API error for %s: status=%s, error=%s, full_response=%s',
                    symbol, status, error_msg, data)
                return []

            closes = data.get('c', [])
            timestamps = data.get('t', [])

            if not closes:
                logger.warning(
                    'Finnhub returned empty closes array for %s. Response: %s', symbol, data)
                return []

            result = []
            for x in closes:
                try:
                    if x is not None and x != 0:
                        result.append(float(x))
                except (TypeError, ValueError):
                    continue

            if result:
                logger.info(
                    'Finnhub returned %d valid price points for %s (timestamps: %d)',
                    len(result), symbol, len(timestamps) if timestamps else 0)
            else:
                logger.warning(
                    'Finnhub returned closes array but no valid prices for %s. Data: %s',
                    symbol, closes[:10] if len(closes) > 10 else closes)

            return result
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response else None
            if status_code == 403:
                logger.warning(
                    'Finnhub API returned 403 Forbidden for %s. '
                    'The /stock/candle endpoint may require a paid plan. '
                    'Using fallback data instead.',
                    symbol)
            else:
                logger.error(
                    'Finnhub HTTP error for %s: %s, status_code=%s, response=%s',
                    symbol, e, status_code,
                    e.response.text[:200] if e.response else None)
            return []
        except requests.exceptions.RequestException as e:
            logger.error(
                'Finnhub request error for %s: %s', symbol, e)
            return []
        except Exception as e:
            logger.exception(
                'Unexpected error fetching 24h series from Finnhub for %s', symbol)
            return []

    # CRYPTO via CoinGecko
    if asset_type == 'CRYPTO':
        try:
            _ensure_coingecko_map()
            cid = _coingecko_map_cache.get(symbol.lower())
            # apply manual override again just in case
            if symbol.lower() in _COINGECKO_MANUAL_OVERRIDES:
                cid = _COINGECKO_MANUAL_OVERRIDES[symbol.lower()]
                logger.debug(
                    'Applied manual CoinGecko override for %s -> %s', symbol, cid)
            logger.debug(
                'CoinGecko lookup for symbol %s -> id %s', symbol, cid)
            if not cid:
                # try CoinGecko search endpoint as a fallback
                try:
                    sresp = requests.get(
                        'https://api.coingecko.com/api/v3/search', params={'query': symbol}, timeout=8)
                    sresp.raise_for_status()
                    sdata = sresp.json()
                    coins = sdata.get('coins', [])
                    found = None
                    for c in coins:
                        # prefer exact symbol match
                        if c.get('symbol', '').lower() == symbol.lower():
                            found = c.get('id')
                            break
                    if not found and coins:
                        found = coins[0].get('id')
                    if found:
                        cid = found
                        # cache it
                        _coingecko_map_cache[symbol.lower()] = cid
                        logger.debug(
                            'CoinGecko search fallback for %s -> id %s', symbol, cid)
                except Exception as e:
                    logger.debug(
                        'CoinGecko search fallback failed for %s: %s', symbol, e)
            if not cid:
                return []

            def try_fetch_for_cid(the_cid: str):
                url = f'https://api.coingecko.com/api/v3/coins/{the_cid}/market_chart'
                params = {'vs_currency': convert.lower(), 'days': 1}
                r = requests.get(url, params=params, timeout=10)
                r.raise_for_status()
                pl = r.json()
                prs = pl.get('prices', [])
                return prs

            # first attempt with current cid (possibly from manual override)
            try:
                prices = try_fetch_for_cid(cid)
                logger.debug('CoinGecko returned %d price points for %s (id=%s)', len(
                    prices), symbol, cid)
                if prices:
                    return [float(p[1]) for p in prices]
                # if empty, fallthrough to search fallback
                logger.debug(
                    'CoinGecko returned empty series for %s (id=%s), will try search fallback', symbol, cid)
            except requests.HTTPError as he:
                status = he.response.status_code if he.response is not None else None
                logger.debug(
                    'CoinGecko fetch for id=%s failed: %s (status=%s)', cid, he, status)
                # if 404 or empty, try search fallback
            except Exception as e:
                logger.debug('CoinGecko fetch error for id=%s: %s', cid, e)

            # try CoinGecko search endpoint as a fallback
            try:
                sresp = requests.get(
                    'https://api.coingecko.com/api/v3/search', params={'query': symbol}, timeout=8)
                sresp.raise_for_status()
                sdata = sresp.json()
                coins = sdata.get('coins', [])
                found = None
                for c in coins:
                    # prefer exact symbol match
                    if c.get('symbol', '').lower() == symbol.lower():
                        found = c.get('id')
                        break
                if not found and coins:
                    found = coins[0].get('id')
                if found:
                    cid2 = found
                    logger.debug(
                        'CoinGecko search fallback matched %s -> %s', symbol, cid2)
                    try:
                        prices2 = try_fetch_for_cid(cid2)
                        logger.debug('CoinGecko returned %d price points for %s (id=%s) via fallback', len(
                            prices2), symbol, cid2)
                        if prices2:
                            # cache this mapping for next time
                            _coingecko_map_cache[symbol.lower()] = cid2
                            return [float(p[1]) for p in prices2]
                    except Exception as e:
                        logger.debug(
                            'Fallback fetch failed for id=%s: %s', cid2, e)
            except Exception as e:
                logger.debug(
                    'CoinGecko search fallback failed for %s: %s', symbol, e)

            return []
        except Exception as e:
            logger.debug(
                'Failed to fetch 24h series from CoinGecko for %s: %s', symbol, e)
            return []

    return []


def sparkline_svg_from_prices(prices: List[float], width: int = 120, height: int = 28, stroke: str = '#1ca01c') -> str:
    """Generate a small inline SVG sparkline from a list of prices.

    Returns an SVG string (no markup escaping).
    """
    if not prices:
        # simple empty placeholder
        return f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg"><rect width="100%" height="100%" fill="none"/></svg>'

    pts = [float(x) for x in prices if x is not None]
    if not pts:
        return f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg"></svg>'

    mn = min(pts)
    mx = max(pts)
    span = mx - mn if mx != mn else 1.0
    n = len(pts)
    # If only one data point, duplicate it to create a visible horizontal line
    if n == 1:
        pts = [pts[0], pts[0]]
        n = 2
    step_x = width / max(1, (n - 1))
    points = []
    for i, p in enumerate(pts):
        x = i * step_x
        # invert y: higher price -> lower y
        y = height - ((p - mn) / span) * height
        points.append(f'{x:.2f},{y:.2f}')
    points_str = ' '.join(points)

    # color based on change
    color = stroke
    try:
        change = (pts[-1] - pts[0]) / pts[0] if pts[0] != 0 else 0
        if change > 0:
            color = '#1ca01c'
        elif change < 0:
            color = '#e53935'
        else:
            color = '#888'
    except Exception:
        color = stroke

    svg = (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        'xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="none">'
        f'<polyline fill="none" stroke="{color}" stroke-width="1.5" points="{points_str}" stroke-linecap="round" stroke-linejoin="round" />'
        '</svg>'
    )
    return svg


def fetch_news_from_newsdata(category: str = None, language: str = None, limit: int = 10) -> List[Dict]:
    """Получает новости из NewsData API.

    Args:
        category: Категория новостей (business, finance, technology и т.д.) - опционально
        language: Язык новостей (ru, en) - опционально
        limit: Максимальное количество новостей

    Returns:
        Список словарей с новостями
    """
    api_key = os.environ.get(
        'NEWSDATA_API_KEY', 'pub_f60d281bd4a24ec0aabe5d4638f59007')
    if not api_key:
        logger.warning('NEWSDATA_API_KEY not set')
        return []

    url = 'https://newsdata.io/api/1/news'
    params = {
        'apikey': api_key,
    }

    if category:
        params['category'] = category

    if language:
        params['language'] = language

    try:
        resp = requests.get(url, params=params, timeout=10)

        if resp.status_code == 422:
            logger.warning(
                'NewsData API returned 422 - trying without category/language parameters')
            params_simple = {'apikey': api_key}
            resp = requests.get(url, params=params_simple, timeout=10)

        resp.raise_for_status()
        data = resp.json()

        logger.debug('NewsData API response: status=%s, totalResults=%s',
                     data.get('status'), data.get('totalResults'))

        if data.get('status') != 'success':
            error_msg = data.get('message', 'Unknown error')
            logger.warning('NewsData API returned status: %s, message: %s',
                           data.get('status'), error_msg)
            return []

        results = data.get('results', [])

        if not results:
            logger.warning(
                'NewsData API returned empty results. Response keys: %s', list(data.keys()))
            return []

        if language:
            filtered_results = [
                r for r in results if r.get('language') == language]
            if not filtered_results and results:
                logger.info(
                    'No news in language %s, returning all results', language)
                filtered_results = results
            results = filtered_results

        logger.info('NewsData API returned %d news articles (filtered from %d total)',
                    len(results), len(data.get('results', [])))
        return results[:limit]
    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code if e.response else None
        error_text = ''
        if e.response:
            try:
                error_data = e.response.json()
                error_text = error_data.get('message', e.response.text[:200])
            except Exception:
                error_text = e.response.text[:200] if e.response.text else ''

        logger.error('NewsData HTTP error: %s, status_code=%s, error=%s',
                     e, status_code, error_text)
        return []
    except Exception as e:
        logger.exception('Failed to fetch news from NewsData: %s', e)
        return []


def generate_price_predictions_for_asset(asset, current_price: float = None) -> List[Dict]:
    """Генерирует предсказания цен для актива через рандомайзер.

    Args:
        asset: Объект Asset
        current_price: Текущая цена актива (если None, будет использована последняя известная цена)

    Returns:
        Список словарей с предсказаниями для разных горизонтов
    """
    import random
    from decimal import Decimal
    from datetime import datetime, timedelta
    from django.utils import timezone

    if current_price is None:
        try:
            from .models import HistoricalPrice
            latest_price = HistoricalPrice.objects.filter(
                asset=asset).order_by('-date').first()
            if latest_price:
                current_price = float(latest_price.close_price)
            else:
                current_price = 100.0
        except Exception:
            current_price = 100.0

    predictions = []
    horizons = ['1D', '7D', '30D']
    horizon_days = {'1D': 1, '7D': 7, '30D': 30}

    for horizon in horizons:
        direction = random.choice(['up', 'down'])
        change_percent = random.uniform(0.5, 5.0)

        if direction == 'up':
            predicted_price = current_price * (1 + change_percent / 100)
        else:
            predicted_price = current_price * (1 - change_percent / 100)

        confidence = random.uniform(0.65, 0.95)

        prediction_date = timezone.now(
        ) + timedelta(days=horizon_days[horizon])

        predictions.append({
            'asset': asset,
            'prediction_date': prediction_date,
            'horizon': horizon,
            'predicted_price': Decimal(str(round(predicted_price, 2))),
            'confidence': round(confidence, 2),
            'model_version': 'v1.0-random',
        })

    return predictions


def generate_sentiments_for_crypto():
    """Генерирует случайные настроения для всех криптовалют.

    Создает записи Sentiment для каждой криптовалюты с случайными значениями.
    """
    import random
    from django.utils import timezone
    from .models import Asset, Sentiment

    crypto_assets = Asset.objects.filter(asset_type=Asset.CRYPTO)

    if not crypto_assets.exists():
        logger.warning('No crypto assets found for sentiment generation')
        return

    source_types = ['Twitter', 'Reddit', 'News', 'Forum', 'Telegram']

    for asset in crypto_assets:
        try:
            sentiment_score = random.uniform(-1.0, 1.0)

            Sentiment.objects.create(
                asset=asset,
                sentiment_score=round(sentiment_score, 3),
                analysis_date=timezone.now(),
                source_type=random.choice(source_types),
            )
            logger.debug('Generated sentiment for %s: %.3f',
                         asset.ticker, sentiment_score)
        except Exception as e:
            logger.debug(
                'Failed to generate sentiment for %s: %s', asset.ticker, e)
            continue

    logger.info('Generated sentiments for %d crypto assets',
                crypto_assets.count())
