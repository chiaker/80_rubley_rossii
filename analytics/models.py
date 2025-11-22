from django.conf import settings
from django.db import models


class Asset(models.Model):
    STOCK = 'STOCK'
    CRYPTO = 'CRYPTO'
    ASSET_TYPES = [
        (STOCK, 'Stock'),
        (CRYPTO, 'Cryptocurrency'),
    ]

    ticker = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100)
    asset_type = models.CharField(max_length=10, choices=ASSET_TYPES)
    market_cap = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['ticker']

    def __str__(self):
        return f'{self.ticker} – {self.name}'


class HistoricalPrice(models.Model):
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='prices')
    date = models.DateTimeField()
    open_price = models.DecimalField(max_digits=20, decimal_places=8)
    high_price = models.DecimalField(max_digits=20, decimal_places=8)
    low_price = models.DecimalField(max_digits=20, decimal_places=8)
    close_price = models.DecimalField(max_digits=20, decimal_places=8)
    volume = models.BigIntegerField()

    class Meta:
        ordering = ['-date']
        unique_together = ('asset', 'date')

    def __str__(self):
        return f'{self.asset.ticker} @ {self.date:%Y-%m-%d}'


class PricePrediction(models.Model):
    HORIZON_CHOICES = [
        ('1D', '1 Day'),
        ('7D', '7 Days'),
        ('30D', '30 Days'),
    ]

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='predictions')
    prediction_date = models.DateTimeField()
    horizon = models.CharField(max_length=3, choices=HORIZON_CHOICES)
    predicted_price = models.DecimalField(max_digits=20, decimal_places=8)
    confidence = models.FloatField()
    model_version = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-prediction_date', 'asset']

    def __str__(self):
        return f'{self.asset.ticker} {self.horizon} прогноз'


class AssetStats(models.Model):
    asset = models.OneToOneField(Asset, on_delete=models.CASCADE, related_name='stats')
    volatility = models.FloatField(null=True, blank=True)
    rsi = models.FloatField(null=True, blank=True)
    moving_average_50 = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    moving_average_200 = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Статистика {self.asset.ticker}'


class News(models.Model):
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, null=True, blank=True, related_name='news')
    title = models.CharField(max_length=200)
    content = models.TextField()
    source = models.URLField(max_length=500)
    published_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-published_at']

    def __str__(self):
        return self.title


class Sentiment(models.Model):
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='sentiments')
    sentiment_score = models.FloatField()
    analysis_date = models.DateTimeField()
    source_type = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-analysis_date']

    def __str__(self):
        return f'Настроения {self.asset.ticker}'


class UserProfile(models.Model):
    PLAN_FREE = 'free'
    PLAN_PREMIUM = 'premium'
    PLAN_CHOICES = [
        (PLAN_FREE, 'Free'),
        (PLAN_PREMIUM, 'Premium'),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    subscription_plan = models.CharField(max_length=50, choices=PLAN_CHOICES, default=PLAN_FREE)
    favorite_assets = models.ManyToManyField(Asset, related_name='fans', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Профиль {self.user.username}'


class UserPredictionHistory(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='prediction_views')
    prediction = models.ForeignKey(PricePrediction, on_delete=models.CASCADE, related_name='views')
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-viewed_at']

    def __str__(self):
        return f'{self.user} → {self.prediction}'


class ContactMessage(models.Model):
    name = models.CharField(max_length=150)
    email = models.EmailField()
    topic = models.CharField(max_length=150)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.topic} от {self.name}'

# Create your models here.
