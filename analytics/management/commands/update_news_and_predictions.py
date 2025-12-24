from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import logging

from analytics.models import Asset, News, PricePrediction
from analytics.utils import fetch_news_from_newsdata, generate_price_predictions_for_asset, fetch_current_stock_prices

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Обновляет новости из NewsData API и генерирует предсказания цен для акций'

    def handle(self, *args, **options):
        self.stdout.write('Начинаю обновление новостей и предсказаний...')
        
        news_data = fetch_news_from_newsdata(category='business', language='ru', limit=30)
        news_count = 0
        
        for news_item in news_data:
            try:
                title = news_item.get('title', '')[:200]
                content = news_item.get('content', '') or news_item.get('description', '')
                source = news_item.get('link', '')
                pub_date_str = news_item.get('pubDate', '')
                
                if not title or not source:
                    continue
                
                try:
                    if pub_date_str:
                        try:
                            from datetime import datetime
                            pub_date = datetime.fromisoformat(pub_date_str.replace('Z', '+00:00'))
                        except ValueError:
                            try:
                                from email.utils import parsedate_to_datetime
                                pub_date = parsedate_to_datetime(pub_date_str)
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
                                ticker__iexact=keyword.upper()
                            ).first()
                            if asset:
                                break
                        except Exception:
                            continue
                
                news_obj, created = News.objects.get_or_create(
                    title=title,
                    source=source,
                    defaults={
                        'content': content[:5000] if content else '',
                        'published_at': pub_date,
                        'asset': asset,
                    }
                )
                
                if created:
                    news_count += 1
                    
            except Exception as e:
                logger.debug('Failed to save news item: %s', e)
                continue
        
        self.stdout.write(self.style.SUCCESS(f'Добавлено {news_count} новых новостей'))
        
        stocks = Asset.objects.filter(asset_type=Asset.STOCK)
        stock_symbols = [s.ticker for s in stocks]
        stock_prices = fetch_current_stock_prices(stock_symbols)
        predictions_count = 0
        
        for stock in stocks:
            try:
                pdata = stock_prices.get(stock.ticker.upper(), {})
                current_price = pdata.get('price')
                
                if not current_price:
                    continue
                
                predictions = generate_price_predictions_for_asset(stock, float(current_price))
                
                for pred_data in predictions:
                    pred_obj, created = PricePrediction.objects.update_or_create(
                        asset=pred_data['asset'],
                        prediction_date=pred_data['prediction_date'],
                        horizon=pred_data['horizon'],
                        defaults={
                            'predicted_price': pred_data['predicted_price'],
                            'confidence': pred_data['confidence'],
                            'model_version': pred_data['model_version'],
                        }
                    )
                    
                    if created:
                        predictions_count += 1
                        
            except Exception as e:
                logger.debug('Failed to generate predictions for %s: %s', stock.ticker, e)
                continue
        
        self.stdout.write(self.style.SUCCESS(f'Сгенерировано {predictions_count} новых предсказаний'))
        self.stdout.write(self.style.SUCCESS('Обновление завершено успешно!'))

