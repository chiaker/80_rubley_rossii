from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import redirect, render

from .forms import ContactMessageForm
from .models import (
    Asset,
    ContactMessage,
    News,
    PricePrediction,
    Sentiment,
    UserPredictionHistory,
)
from .utils import fetch_current_crypto_prices


def home(request):
    latest_predictions = PricePrediction.objects.select_related(
        'asset').order_by('-created_at')[:5]
    highlighted_assets = Asset.objects.prefetch_related('stats').all()[:6]
    # Attach current prices for crypto assets (if CMC_API_KEY is set)
    crypto_symbols = [a.ticker for a in highlighted_assets if a.asset_type == Asset.CRYPTO]
    prices = fetch_current_crypto_prices(crypto_symbols)
    for a in highlighted_assets:
        if a.asset_type == Asset.CRYPTO:
            pdata = prices.get(a.ticker.upper(), {})
            a.current_price = pdata.get('price')
            a.change_24h = pdata.get('percent_change_24h')
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
    profile = getattr(request.user, 'profile', None)
    favorite_assets = profile.favorite_assets.all() if profile else Asset.objects.none()
    personalized_predictions = (
        PricePrediction.objects.select_related('asset')
        .filter(asset__in=favorite_assets)
        .order_by('-prediction_date')
    )
    recent_views = UserPredictionHistory.objects.filter(user=request.user).select_related('prediction', 'prediction__asset')[
        :10
    ]
    return render(
        request,
        'analytics/dashboard.html',
        {
            'profile': profile,
            'favorite_assets': favorite_assets,
            'personalized_predictions': personalized_predictions,
            'recent_views': recent_views,
        },
    )


def asset_catalog(request):
    assets = Asset.objects.select_related('stats').all()
    crypto_symbols = [a.ticker for a in assets if a.asset_type == Asset.CRYPTO]
    prices = fetch_current_crypto_prices(crypto_symbols)
    for a in assets:
        if a.asset_type == Asset.CRYPTO:
            pdata = prices.get(a.ticker.upper(), {})
            a.current_price = pdata.get('price')
            a.change_24h = pdata.get('percent_change_24h')
        else:
            a.current_price = None
            a.change_24h = None

    return render(
        request,
        'analytics/assets.html',
        {
            'assets': assets,
        },
    )


def analytics_news(request):
    news_feed = News.objects.select_related(
        'asset').order_by('-published_at')[:10]
    sentiment_feed = Sentiment.objects.select_related(
        'asset').order_by('-analysis_date')[:10]
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
