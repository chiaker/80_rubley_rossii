from django.urls import path

from . import views

app_name = 'analytics'

urlpatterns = [
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('assets/', views.asset_catalog, name='assets'),
    path('analytics/', views.analytics_news, name='analytics'),
    path('profile/', views.user_profile, name='profile'),
    path('about/', views.about_contact, name='about'),
    path('signup/', views.signup, name='signup'),
]
