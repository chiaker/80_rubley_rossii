from django.contrib import admin

from .models import (
    Asset,
    AssetStats,
    ContactMessage,
    HistoricalPrice,
    News,
    PricePrediction,
    Sentiment,
    UserPredictionHistory,
    UserProfile,
)


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ('ticker', 'name', 'asset_type', 'market_cap', 'created_at')
    search_fields = ('ticker', 'name')
    list_filter = ('asset_type',)


@admin.register(HistoricalPrice)
class HistoricalPriceAdmin(admin.ModelAdmin):
    list_display = ('asset', 'date', 'close_price', 'volume')
    search_fields = ('asset__ticker',)
    list_filter = ('asset',)
    date_hierarchy = 'date'


@admin.register(PricePrediction)
class PricePredictionAdmin(admin.ModelAdmin):
    list_display = ('asset', 'horizon', 'predicted_price', 'confidence', 'model_version', 'prediction_date')
    search_fields = ('asset__ticker', 'model_version')
    list_filter = ('horizon', 'model_version')
    date_hierarchy = 'prediction_date'


@admin.register(AssetStats)
class AssetStatsAdmin(admin.ModelAdmin):
    list_display = ('asset', 'volatility', 'rsi', 'moving_average_50', 'moving_average_200', 'last_updated')
    search_fields = ('asset__ticker',)


@admin.register(News)
class NewsAdmin(admin.ModelAdmin):
    list_display = ('title', 'asset', 'published_at', 'source')
    search_fields = ('title', 'content', 'asset__ticker')
    date_hierarchy = 'published_at'


@admin.register(Sentiment)
class SentimentAdmin(admin.ModelAdmin):
    list_display = ('asset', 'sentiment_score', 'analysis_date', 'source_type')
    list_filter = ('source_type',)
    date_hierarchy = 'analysis_date'


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'subscription_plan', 'created_at')
    list_filter = ('subscription_plan',)
    search_fields = ('user__username',)


@admin.register(UserPredictionHistory)
class UserPredictionHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'prediction', 'viewed_at')
    search_fields = ('user__username', 'prediction__asset__ticker')
    date_hierarchy = 'viewed_at'


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('topic', 'name', 'email', 'created_at')
    search_fields = ('topic', 'name', 'email')
    date_hierarchy = 'created_at'
