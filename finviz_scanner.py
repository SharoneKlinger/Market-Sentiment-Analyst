import requests
from bs4 import BeautifulSoup
import re
import time
import logging

logger = logging.getLogger(__name__)

FINVIZ_SCREENER_URL = 'https://finviz.com/screener.ashx'

# Finviz requires a browser-like User-Agent or it returns 403
FINVIZ_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    ),
}

# Pre-built filter sets for momentum scanning.
# These narrow the universe before we run the expensive 8-week EMA check.
SCAN_PRESETS = {
    'momentum_leaders': {
        'description': (
            'Mid-cap+ stocks with strong volume trending above the 50-day SMA. '
            'Best for finding institutional-quality names to check against 8w EMA.'
        ),
        'filters': {
            'v': '111',           # overview table
            'f': ','.join([
                'cap_midover',    # market cap >= $2B
                'sh_avgvol_o400', # avg volume > 400K
                'ta_sma50_pa',    # price above SMA50
                'ta_perf_4w10o',  # 4-week performance > 10%
            ]),
        },
    },
    'breakout_candidates': {
        'description': (
            'Stocks near the 50-day SMA with above-average volume — '
            'potential EMA crossover candidates.'
        ),
        'filters': {
            'v': '111',
            'f': ','.join([
                'cap_midover',
                'sh_avgvol_o400',
                'sh_relvol_o1',      # relative volume > 1
                'ta_sma50_cross50a', # price crossed above SMA50
            ]),
        },
    },
    'high_momentum': {
        'description': (
            'Aggressive scan: stocks up 20%+ over 4 weeks with heavy volume. '
            'Finds parabolic movers that may be extended above the 8w EMA.'
        ),
        'filters': {
            'v': '111',
            'f': ','.join([
                'cap_midover',
                'sh_avgvol_o400',
                'ta_perf_4w20o',  # 4-week performance > 20%
                'ta_sma20_pa',    # price above SMA20
            ]),
        },
    },
    'broad': {
        'description': (
            'Broad scan of liquid mid-cap+ stocks. '
            'Largest candidate pool — slower but most comprehensive.'
        ),
        'filters': {
            'v': '111',
            'f': ','.join([
                'cap_midover',
                'sh_avgvol_o200',
            ]),
        },
    },
}


def scrape_finviz_screener(filters=None, preset='momentum_leaders', max_pages=3):
    """
    Scrape the Finviz screener and return a list of ticker symbols.

    Args:
        filters: Dict of raw Finviz URL params. Overrides preset if provided.
        preset: Name of a pre-built filter set from SCAN_PRESETS.
        max_pages: Maximum number of result pages to scrape (20 tickers/page).

    Returns:
        List of ticker symbol strings.
    """
    if filters is None:
        if preset not in SCAN_PRESETS:
            raise ValueError(
                f"Unknown preset '{preset}'. "
                f"Available: {list(SCAN_PRESETS.keys())}"
            )
        filters = SCAN_PRESETS[preset]['filters']

    symbols = []

    for page in range(1, max_pages + 1):
        params = dict(filters)
        # Finviz pagination: r=1, r=21, r=41 ...
        params['r'] = str((page - 1) * 20 + 1)

        response = requests.get(
            FINVIZ_SCREENER_URL,
            params=params,
            headers=FINVIZ_HEADERS,
            timeout=15,
        )
        response.raise_for_status()

        page_symbols = _parse_screener_page(response.text)
        if not page_symbols:
            break

        symbols.extend(page_symbols)
        logger.info("Finviz page %d: found %d symbols", page, len(page_symbols))

        # Be respectful to Finviz servers
        if page < max_pages:
            time.sleep(1)

    return symbols


def _parse_screener_page(html):
    """Extract ticker symbols from a Finviz screener HTML page."""
    soup = BeautifulSoup(html, 'html.parser')
    symbols = []

    # Finviz screener results are in a table. Ticker links point to quote.ashx.
    for link in soup.find_all('a', href=True):
        href = link['href']
        if 'quote.ashx?t=' in href and '&' not in href:
            ticker = link.get_text(strip=True)
            if ticker and re.match(r'^[A-Z]{1,5}$', ticker):
                symbols.append(ticker)

    return symbols


def get_available_presets():
    """Return dict of preset names to their descriptions."""
    return {
        name: config['description']
        for name, config in SCAN_PRESETS.items()
    }
