from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import redirect, render

from .forms import ContactMessageForm
from .models import (
    Asset,
    ContactMessage,
    HistoricalPrice,
    News,
    PricePrediction,
    Sentiment,
    UserPredictionHistory,
    UserProfile,
)
from .utils import (
    fetch_current_crypto_prices,
    fetch_current_stock_prices,
    fetch_24h_series,
    sparkline_svg_from_prices,
    fetch_news_from_newsdata,
    generate_price_predictions_for_asset,
    generate_sentiments_for_crypto,
)
from django.utils.safestring import mark_safe
import logging

logger = logging.getLogger(__name__)


def home(request):
    from django.utils import timezone
    from datetime import timedelta

    stocks = Asset.objects.filter(asset_type=Asset.STOCK)

    for stock in stocks:
        recent_predictions = PricePrediction.objects.filter(
            asset=stock,
            created_at__gte=timezone.now() - timedelta(hours=1)
        ).exists()

        if not recent_predictions:
            try:
                stock_prices_temp = fetch_current_stock_prices([stock.ticker])
                pdata = stock_prices_temp.get(stock.ticker.upper(), {})
                current_price = pdata.get('price')

                if current_price:
                    predictions = generate_price_predictions_for_asset(
                        stock, float(current_price))
                    for pred_data in predictions:
                        PricePrediction.objects.update_or_create(
                            asset=pred_data['asset'],
                            prediction_date=pred_data['prediction_date'],
                            horizon=pred_data['horizon'],
                            defaults={
                                'predicted_price': pred_data['predicted_price'],
                                'confidence': pred_data['confidence'],
                                'model_version': pred_data['model_version'],
                            }
                        )
                    logger.info('Generated predictions for %s', stock.ticker)
            except Exception as e:
                logger.debug(
                    'Failed to generate predictions for %s: %s', stock.ticker, e)

    highlighted_assets = Asset.objects.prefetch_related('stats').all()[:6]

    favorite_asset_ids = set()
    if request.user.is_authenticated:
        try:
            profile = request.user.profile
            favorite_asset_ids = set(
                profile.favorite_assets.values_list('id', flat=True))
        except UserProfile.DoesNotExist:
            pass

    for asset in highlighted_assets:
        asset.is_favorite = asset.id in favorite_asset_ids
    # Attach current prices for crypto assets (if CMC_API_KEY is set)
    crypto_symbols = [
        a.ticker for a in highlighted_assets if a.asset_type == Asset.CRYPTO]
    crypto_prices = fetch_current_crypto_prices(crypto_symbols)
    # Attach current prices for stock assets (if FINNHUB_API_KEY is set)
    stock_symbols = [
        a.ticker for a in highlighted_assets if a.asset_type == Asset.STOCK]
    stock_prices = fetch_current_stock_prices(stock_symbols)

    latest_predictions = PricePrediction.objects.select_related(
        'asset').order_by('-created_at')[:5]

    for pred in latest_predictions:
        if pred.asset.asset_type == Asset.STOCK:
            pdata = stock_prices.get(pred.asset.ticker.upper(), {})
            current_price = pdata.get('price')
        else:
            pdata = crypto_prices.get(pred.asset.ticker.upper(), {})
            current_price = pdata.get('price')

        if current_price:
            predicted = float(pred.predicted_price)
            current = float(current_price)
            if predicted > current * 1.01:
                pred.direction = 'up'
            elif predicted < current * 0.99:
                pred.direction = 'down'
            else:
                pred.direction = 'neutral'
        else:
            pred.direction = 'neutral'

    for a in highlighted_assets:
        if a.asset_type == Asset.CRYPTO:
            pdata = crypto_prices.get(a.ticker.upper(), {})
            try:
                a.current_price = float(pdata.get('price')) if pdata.get(
                    'price') is not None else None
            except (TypeError, ValueError):
                a.current_price = None
            try:
                a.change_24h = float(pdata.get('percent_change_24h')) if pdata.get(
                    'percent_change_24h') is not None else None
            except (TypeError, ValueError):
                a.change_24h = None
        elif a.asset_type == Asset.STOCK:
            pdata = stock_prices.get(a.ticker.upper(), {})
            try:
                a.current_price = float(pdata.get('price')) if pdata.get(
                    'price') is not None else None
            except (TypeError, ValueError):
                a.current_price = None
            try:
                a.change_24h = float(pdata.get('percent_change')) if pdata.get(
                    'percent_change') is not None else None
            except (TypeError, ValueError):
                a.change_24h = None
        else:
            a.current_price = None
            a.change_24h = None
    return render(
        request,
        'analytics/home.html',
        {
            'latest_predictions': latest_predictions,
            'highlighted_assets': highlighted_assets,
        },
    )


@login_required
def dashboard(request):
    from .utils import fetch_current_crypto_prices, fetch_current_stock_prices

    profile = getattr(request.user, 'profile', None)
    favorite_assets = profile.favorite_assets.all() if profile else Asset.objects.none()

    personalized_predictions = (
        PricePrediction.objects.select_related('asset')
        .filter(asset__in=favorite_assets)
        .order_by('-prediction_date')[:10]
    )

    recent_views = UserPredictionHistory.objects.filter(
        user=request.user).select_related('prediction', 'prediction__asset')[:10]

    latest_news = News.objects.filter(
        asset__asset_type=Asset.CRYPTO
    ).exclude(source__startswith='https://example.com/').select_related('asset').order_by('-published_at')[:5]

    crypto_symbols = [
        a.ticker for a in favorite_assets if a.asset_type == Asset.CRYPTO]
    stock_symbols = [
        a.ticker for a in favorite_assets if a.asset_type == Asset.STOCK]

    crypto_prices = fetch_current_crypto_prices(
        crypto_symbols) if crypto_symbols else {}
    stock_prices = fetch_current_stock_prices(
        stock_symbols) if stock_symbols else {}

    for asset in favorite_assets:
        if asset.asset_type == Asset.CRYPTO:
            pdata = crypto_prices.get(asset.ticker.upper(), {})
            asset.current_price = float(
                pdata.get('price')) if pdata.get('price') else None
            asset.change_24h = float(pdata.get('percent_change_24h')) if pdata.get(
                'percent_change_24h') else None
        elif asset.asset_type == Asset.STOCK:
            pdata = stock_prices.get(asset.ticker.upper(), {})
            asset.current_price = float(
                pdata.get('price')) if pdata.get('price') else None
            asset.change_24h = float(pdata.get('percent_change')) if pdata.get(
                'percent_change') else None

    for pred in personalized_predictions:
        if pred.asset.asset_type == Asset.STOCK:
            pdata = stock_prices.get(pred.asset.ticker.upper(), {})
            current_price = pdata.get('price')
        else:
            pdata = crypto_prices.get(pred.asset.ticker.upper(), {})
            current_price = pdata.get('price')

        if current_price:
            predicted = float(pred.predicted_price)
            current = float(current_price)
            if predicted > current * 1.01:
                pred.direction = 'up'
            elif predicted < current * 0.99:
                pred.direction = 'down'
            else:
                pred.direction = 'neutral'
        else:
            pred.direction = 'neutral'

    return render(
        request,
        'analytics/dashboard.html',
        {
            'profile': profile,
            'favorite_assets': favorite_assets,
            'personalized_predictions': personalized_predictions,
            'recent_views': recent_views,
            'latest_news': latest_news,
        },
    )


def asset_catalog(request):
    # Валюта для отображения (по умолчанию USD)
    currency = request.GET.get('currency', 'USD').upper()
    # Разделяем активы
    all_assets = Asset.objects.all()
    stocks = [a for a in all_assets if a.asset_type == Asset.STOCK]
    cryptos = [a for a in all_assets if a.asset_type == Asset.CRYPTO]

    # Получаем цены для крипты
    crypto_symbols = [a.ticker for a in cryptos]
    prices = fetch_current_crypto_prices(crypto_symbols, convert=currency)
    for a in cryptos:
        pdata = prices.get(a.ticker.upper(), {})
        try:
            a.current_price = float(pdata.get('price')) if pdata.get(
                'price') is not None else None
        except (TypeError, ValueError):
            a.current_price = None
        try:
            a.change_24h = float(pdata.get('percent_change_24h')) if pdata.get(
                'percent_change_24h') is not None else None
        except (TypeError, ValueError):
            a.change_24h = None
        # fetch sparkline for crypto
        try:
            series = fetch_24h_series(a.ticker, Asset.CRYPTO, convert=currency)
            logger.debug('Crypto %s 24h series points: %d', a.ticker,
                         len(series) if series is not None else 0)
            if not series:
                try:
                    if a.current_price is not None and a.change_24h is not None:
                        prev = a.current_price / \
                            (1 + (a.change_24h / 100)) if (1 +
                                                           (a.change_24h / 100)) != 0 else None
                        if prev is not None:
                            series = [float(prev), float(a.current_price)]
                    elif a.current_price is not None:
                        series = [float(a.current_price),
                                  float(a.current_price)]
                except Exception:
                    series = []

            if series:
                svg = sparkline_svg_from_prices(series, width=140, height=36)
                a.sparkline_svg = mark_safe(svg)
            else:
                a.sparkline_svg = None
                logger.debug('Crypto %s: no data for sparkline', a.ticker)
        except Exception:
            a.sparkline_svg = None
            logger.exception(
                'Error generating sparkline for crypto %s', a.ticker)

    # Attach current prices for stocks using Finnhub (if FINNHUB_API_KEY is set)
    stock_symbols = [a.ticker for a in stocks]
    stock_prices = fetch_current_stock_prices(stock_symbols)
    for a in stocks:
        pdata = stock_prices.get(a.ticker.upper(), {})
        try:
            a.current_price = float(pdata.get('price')) if pdata.get(
                'price') is not None else None
        except (TypeError, ValueError):
            a.current_price = None
        try:
            a.change_24h = float(pdata.get('percent_change')) if pdata.get(
                'percent_change') is not None else None
        except (TypeError, ValueError):
            a.change_24h = None
        # fetch sparkline for stock
        try:
            series = fetch_24h_series(a.ticker, Asset.STOCK)
            logger.debug('Stock %s 24h series points: %d', a.ticker,
                         len(series) if series is not None else 0)

            if not series:
                logger.debug(
                    'Stock %s: no series from API, trying database fallback', a.ticker)
                try:
                    from django.utils import timezone
                    from datetime import timedelta
                    yesterday = timezone.now() - timedelta(days=1)
                    historical_prices = HistoricalPrice.objects.filter(
                        asset=a,
                        date__gte=yesterday
                    ).order_by('date').values_list('close_price', flat=True)

                    if historical_prices:
                        series = [float(price) for price in historical_prices]
                        logger.info(
                            'Stock %s: using %d historical prices from database',
                            a.ticker, len(series))
                    else:
                        logger.debug(
                            'Stock %s: no historical prices in database, trying quote fallback', a.ticker)
                except Exception as db_error:
                    logger.debug(
                        'Stock %s: database fallback failed: %s', a.ticker, db_error)

            if not series:
                logger.debug(
                    'Stock %s: attempting quote fallback using pdata keys: %s', a.ticker, list(pdata.keys()))
                try:
                    pc = pdata.get('prev_close')
                    price = pdata.get('price')
                    change_24h = a.change_24h
                    logger.debug(
                        'Stock %s: prev_close=%s current_price=%s change_24h=%s', a.ticker, pc, price, change_24h)

                    if price is not None and pc not in (None, 0):
                        prev_price = float(pc)
                        curr_price = float(price)
                        num_points = 24
                        series = []

                        if change_24h is not None and change_24h != 0:
                            total_change = curr_price - prev_price
                            for i in range(num_points):
                                progress = i / (num_points - 1)
                                interpolated = prev_price + \
                                    (total_change * progress)
                                series.append(interpolated)
                        else:
                            for i in range(num_points):
                                progress = i / (num_points - 1)
                                interpolated = prev_price + \
                                    (curr_price - prev_price) * progress
                                series.append(interpolated)

                        logger.warning(
                            'Stock %s: using interpolated quote fallback (%d points) - '
                            'Finnhub /stock/candle endpoint requires paid plan (403 Forbidden)',
                            a.ticker, len(series))
                    elif price is not None:
                        series = [float(price)] * 24
                        logger.warning(
                            'Stock %s: using single price fallback (%d points) - '
                            'Finnhub /stock/candle endpoint requires paid plan', a.ticker)
                except Exception as fallback_error:
                    logger.debug(
                        'Stock %s: quote fallback failed: %s', a.ticker, fallback_error)
                    series = []

            if series:
                svg = sparkline_svg_from_prices(series, width=140, height=36)
                a.sparkline_svg = mark_safe(svg)
                logger.debug(
                    'Stock %s: sparkline generated (len series=%d)', a.ticker, len(series))
            else:
                a.sparkline_svg = None
                logger.warning(
                    'Stock %s: no data for sparkline (API failed, no DB fallback, no quote)', a.ticker)
        except Exception:
            a.sparkline_svg = None
            logger.exception(
                'Error generating sparkline for stock %s', a.ticker)

    # Список поддерживаемых валют (можно расширить)
    currency_choices = ['USD', 'EUR', 'RUB']

    return render(
        request,
        'analytics/assets.html',
        {
            'stocks': stocks,
            'cryptos': cryptos,
            'currency': currency,
            'currency_choices': currency_choices,
        },
    )


def analytics_news(request):
    from django.utils import timezone
    from datetime import timedelta, datetime

    news_feed = News.objects.select_related(
        'asset').order_by('-published_at')[:10]

    crypto_assets = Asset.objects.filter(asset_type=Asset.CRYPTO)

    News.objects.filter(source__startswith='https://example.com/').delete()

    news_feed = News.objects.filter(
        asset__asset_type=Asset.CRYPTO
    ).select_related('asset').order_by('-published_at')[:10]

    if not news_feed.exists() or news_feed.first().published_at < timezone.now() - timedelta(hours=6):
        logger.info(
            'No crypto news in database or news are old, fetching from NewsData API')

        crypto_keywords = ['bitcoin', 'btc', 'ethereum', 'eth', 'crypto', 'cryptocurrency',
                           'blockchain', 'defi', 'nft', 'altcoin', 'binance', 'coinbase']

        news_data = []

        for lang in ['ru', 'en']:
            logger.info('Fetching news for language: %s', lang)
            lang_news = fetch_news_from_newsdata(
                category=None, language=lang, limit=30)

            if lang_news:
                filtered_news = []
                for item in lang_news:
                    item_lang = item.get('language', '').lower()
                    if item_lang and item_lang not in ['ru', 'en']:
                        continue

                    title_lower = item.get('title', '').lower()
                    description_lower = (
                        item.get('description', '') or item.get('content', '') or '').lower()
                    keywords = [k.lower()
                                for k in (item.get('keywords', []) or [])]

                    all_text = f"{title_lower} {description_lower} {' '.join(keywords)}"

                    if any(keyword in all_text for keyword in crypto_keywords):
                        filtered_news.append(item)
                    elif not item_lang or item_lang in ['ru', 'en']:
                        filtered_news.append(item)

                if filtered_news:
                    news_data.extend(filtered_news)
                    logger.info('Filtered %d crypto news for language %s', len(
                        filtered_news), lang)

        news_data = news_data[:20]

        if not news_data:
            logger.warning(
                'NewsData API returned no crypto news, creating sample crypto news')
            sample_assets = crypto_assets[:3] if crypto_assets.exists() else []
            sample_news = [
                {
                    'title': 'Bitcoin показывает рост на фоне институционального интереса',
                    'content': '',
                    'link': 'https://example.com/crypto1',
                    'pubDate': timezone.now().isoformat(),
                },
                {
                    'title': 'Ethereum обновление привлекает внимание инвесторов',
                    'content': '',
                    'link': 'https://example.com/crypto2',
                    'pubDate': (timezone.now() - timedelta(hours=2)).isoformat(),
                },
                {
                    'title': 'Рынок криптовалют демонстрирует волатильность',
                    'content': '',
                    'link': 'https://example.com/crypto3',
                    'pubDate': (timezone.now() - timedelta(hours=5)).isoformat(),
                },
            ]
            for i, news_item in enumerate(sample_news):
                asset = sample_assets[i] if i < len(sample_assets) else None
                News.objects.create(
                    title=news_item['title'],
                    content=news_item['content'],
                    source=news_item['link'],
                    published_at=timezone.now() - timedelta(hours=i*2),
                    asset=asset,
                )
            news_feed = News.objects.filter(
                asset__asset_type=Asset.CRYPTO
            ).select_related('asset').order_by('-published_at')[:10]
        else:
            for news_item in news_data:
                try:
                    title = news_item.get('title', '')[:200]
                    content = news_item.get(
                        'content', '') or news_item.get('description', '')
                    source = news_item.get('link', '')
                    pub_date_str = news_item.get('pubDate', '')

                    if not title or not source:
                        continue

                    try:
                        if pub_date_str:
                            try:
                                pub_date = datetime.fromisoformat(
                                    pub_date_str.replace('Z', '+00:00'))
                            except ValueError:
                                try:
                                    from email.utils import parsedate_to_datetime
                                    pub_date = parsedate_to_datetime(
                                        pub_date_str)
                                except Exception:
                                    pub_date = timezone.now()

                            if timezone.is_naive(pub_date):
                                pub_date = timezone.make_aware(pub_date)
                        else:
                            pub_date = timezone.now()
                    except Exception:
                        pub_date = timezone.now()

                    keywords = news_item.get('keywords', []) or []
                    asset = None

                    if keywords:
                        for keyword in keywords[:3]:
                            try:
                                asset = Asset.objects.filter(
                                    ticker__iexact=keyword.upper(),
                                    asset_type=Asset.CRYPTO
                                ).first()
                                if asset:
                                    break
                            except Exception:
                                continue

                    if not asset and crypto_assets.exists():
                        asset = crypto_assets.first()

                    news_obj, created = News.objects.get_or_create(
                        title=title,
                        source=source,
                        defaults={
                            'content': '',
                            'published_at': pub_date,
                            'asset': asset,
                        }
                    )
                    if created:
                        logger.debug('Saved news from API: %s', title[:50])
                except Exception as e:
                    logger.debug('Failed to save news item: %s', e)
                    continue

            news_feed = News.objects.filter(
                asset__asset_type=Asset.CRYPTO
            ).exclude(source__startswith='https://example.com/').select_related('asset').order_by('-published_at')[:10]

            if not news_feed.exists():
                logger.warning('No news saved from API, using fallback')
                news_feed = News.objects.filter(
                    asset__asset_type=Asset.CRYPTO
                ).select_related('asset').order_by('-published_at')[:10]

    sentiment_feed = Sentiment.objects.filter(
        asset__asset_type=Asset.CRYPTO
    ).select_related('asset').order_by('-analysis_date')[:10]

    if not sentiment_feed.exists():
        logger.info('No sentiments in database, generating random sentiments')
        generate_sentiments_for_crypto()
        sentiment_feed = Sentiment.objects.filter(
            asset__asset_type=Asset.CRYPTO
        ).select_related('asset').order_by('-analysis_date')[:10]
    return render(
        request,
        'analytics/analytics.html',
        {
            'news_feed': news_feed,
            'sentiment_feed': sentiment_feed,
        },
    )


@login_required
def user_profile(request):
    profile = getattr(request.user, 'profile', None)
    recent_predictions = (
        PricePrediction.objects.select_related('asset')
        .filter(asset__in=profile.favorite_assets.all())[:5]
        if profile
        else PricePrediction.objects.none()
    )
    return render(
        request,
        'analytics/profile.html',
        {
            'profile': profile,
            'recent_predictions': recent_predictions,
        },
    )


def about_contact(request):
    if request.method == 'POST':
        form = ContactMessageForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(
                request, 'Сообщение отправлено, мы свяжемся с вами.')
            return redirect('analytics:about')
    else:
        form = ContactMessageForm()

    return render(
        request,
        'analytics/about.html',
        {
            'form': form,
        },
    )


@login_required
def toggle_favorite(request, asset_id):
    """Добавляет или удаляет актив из избранного."""
    try:
        asset = Asset.objects.get(pk=asset_id)
    except Asset.DoesNotExist:
        messages.error(request, 'Актив не найден.')
        return redirect('analytics:assets')

    profile, created = UserProfile.objects.get_or_create(user=request.user)

    if asset in profile.favorite_assets.all():
        profile.favorite_assets.remove(asset)
        messages.success(request, f'{asset.ticker} удален из избранного.')
    else:
        profile.favorite_assets.add(asset)
        messages.success(request, f'{asset.ticker} добавлен в избранное.')

    next_url = request.GET.get('next', 'analytics:assets')
    return redirect(next_url)


def signup(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Регистрация прошла успешно.')
            return redirect('analytics:dashboard')
    else:
        form = UserCreationForm()

    return render(
        request,
        'registration/signup.html',
        {
            'form': form,
        },
    )
