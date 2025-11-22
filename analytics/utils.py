import os
import logging
from typing import Dict, Iterable

import requests

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
