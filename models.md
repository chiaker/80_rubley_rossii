### Модель: Asset

- ticker (CharField) - Краткий код актива (например, BTC, AAPL), max_length=10, unique=True.
- name (CharField) - Полное название актива (например, Bitcoin), max_length=100.
asset_type (CharField) - Тип актива (Stock или Cryptocurrency), max_length=10,
- choices=[('STOCK', 'Stock'), ('CRYPTO', 'Cryptocurrency')].
- market_cap (DecimalField) - Рыночная капитализация, max_digits=20, decimal_places=2, null=True.
- created_at (DateTimeField) - Дата добавления актива, auto_now_add=True.

Описание: Хранит информацию об активах (акции, криптовалюты), используется в каталогах и прогнозах.

### Модель: HistoricalPrice

- asset (ForeignKey) - Связь с активом, ForeignKey к Asset, on_delete=models.CASCADE.
- date (DateTimeField) - Дата и время цены.
- open_price (DecimalField) - Цена открытия, max_digits=20, decimal_places=8.
- high_price (DecimalField) - Максимальная цена, max_digits=20, decimal_places=8.
- low_price (DecimalField) - Минимальная цена, max_digits=20, decimal_places=8.
- close_price (DecimalField) - Цена закрытия, max_digits=20, decimal_places=8.
- volume (BigIntegerField) - Объем торгов.

Описание: Хранит исторические данные OHLCV (open, high, low, close, volume) для построения графиков и обучения моделей.

### Модель: PricePrediction

- asset (ForeignKey) - Связь с активом, ForeignKey к Asset, on_delete=models.CASCADE.
- prediction_date (DateTimeField) - Дата прогноза.
- horizon (CharField) - Горизонт прогноза (1D, 7D, 30D), max_length=3, choices=[('1D', '1 Day'), ('7D', '7 Days'), ('30D', '30 Days')].
- predicted_price (DecimalField) - Спрогнозированная цена, max_digits=20, decimal_places=8.
- confidence (FloatField) - Доверительная вероятность (0–1).
- model_version (CharField) - Версия модели (например, LSTM_v1), max_length=50.
- created_at (DateTimeField) - Дата добавления прогноза, auto_now_add=True.

Описание: Хранит прогнозы цен, отображается в панели прогнозов и истории.

### Модель: AssetStats

- asset (OneToOneField) - Связь с активом, OneToOneField к Asset, on_delete=models.CASCADE.
- volatility (FloatField) - Волатильность актива, null=True.
- rsi (FloatField) - Индекс относительной силы (RSI), null=True.
- moving_average_50 (DecimalField) - Скользящая средняя (50 дней), max_digits=20, decimal_places=8, null=True.
- moving_average_200 (DecimalField) - Скользящая средняя (200 дней), max_digits=20, decimal_places=8, null=True.
- last_updated (DateTimeField) - Дата обновления статистики, auto_now=True.

Описание: Хранит технические индикаторы для аналитики активов.

### Модель: News

- asset (ForeignKey) - Связь с активом, ForeignKey к Asset, on_delete=models.CASCADE, null=True.
- title (CharField) - Заголовок новости, max_length=200.
- content (TextField) - Текст новости.
- source (URLField) - Источник новости (например, Reuters, X), max_length=500.
- published_at (DateTimeField) - Дата публикации новости.
- created_at (DateTimeField) - Дата добавления, auto_now_add=True.

Описание: Хранит новости для раздела аналитики, связана с активами.

### Модель: Sentiment

- asset (ForeignKey) - Связь с активом, ForeignKey к Asset, on_delete=models.CASCADE.
- sentiment_score (FloatField) - Индекс настроений (0–1).
- analysis_date (DateTimeField) - Дата анализа.
- source_type (CharField) - Источник данных (например, X, News), max_length=50.
- created_at (DateTimeField) - Дата добавления, auto_now_add=True.

Описание: Хранит результаты анализа настроений для активов.

### Модель: UserProfile

- user (OneToOneField) - Связь с пользователем, OneToOneField к User, on_delete=models.CASCADE.
- subscription_plan (CharField) - Тип подписки (free, premium), max_length=50, default='free'.
- favorite_assets (ManyToManyField) - Избранные активы, ManyToManyField к Asset.
- created_at (DateTimeField) - Дата создания профиля, auto_now_add=True.

Описание: Хранит настройки пользователя и избранные активы.

### Модель: UserPredictionHistory

- user (ForeignKey) - Связь с пользователем, ForeignKey к User, on_delete=models.CASCADE.
- prediction (ForeignKey) - Связ    ь с прогнозом, ForeignKey к PricePrediction, on_delete=models.CASCADE.
- viewed_at (DateTimeField) - Дата просмотра прогноза, auto_now_add=True.

Описание: Отслеживает, какие прогнозы смотрел пользователь.