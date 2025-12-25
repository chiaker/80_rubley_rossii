# Диаграммы проекта 80_rubley_rossii

## Для просмотра диаграм необходимо установить расширение Mermaid Preview 

## 1. ER Диаграмма (Связи сущностей)

```mermaid
erDiagram
    Asset ||--o{ PricePrediction : "has many"
    Asset ||--o{ HistoricalPrice : "has many"
    Asset ||--o{ News : "related to"
    Asset ||--o{ Sentiment : "has"
    Asset }|--|{ UserProfile : "in favorites"
    
    User ||--|| UserProfile : "has one"
    User ||--o{ UserPredictionHistory : "viewed"
    PricePrediction ||--o{ UserPredictionHistory : "viewed by"

    Asset {
        integer id PK
        string ticker
        string name
        string asset_type
        decimal market_cap
        datetime created_at
    }

    PricePrediction {
        integer id PK
        integer asset_id FK
        string horizon
        decimal predicted_price
        float confidence
        string model_version
        datetime prediction_date
    }

    HistoricalPrice {
        integer id PK
        integer asset_id FK
        datetime date
        decimal close_price
        decimal open_price
        decimal high_price
        decimal low_price
        bigint volume
    }

    News {
        integer id PK
        integer asset_id FK
        string title
        text content
        url source
        datetime published_at
    }

    Sentiment {
        integer id PK
        integer asset_id FK
        float sentiment_score
        string source_type
        datetime analysis_date
    }

    UserProfile {
        integer id PK
        integer user_id FK
        string subscription_plan
        datetime created_at
    }

    UserPredictionHistory {
        integer id PK
        integer user_id FK
        integer prediction_id FK
        datetime viewed_at
    }

    ContactMessage {
        integer id PK
        string name
        string email
        string topic
        text message
        datetime created_at
    }
```

## 2. Архитектура системы

```mermaid
classDiagram
    %% Классы бизнес-логики и сервисов
    class Utils {
        <<Service>>
        +fetch_current_stock_prices(symbols)
        +fetch_current_crypto_prices(symbols)
        +fetch_news_from_newsdata(category)
        +generate_price_predictions_for_asset(asset)
        +sparkline_svg_from_prices(prices)
    }

    class Views {
        <<Controller>>
        +home(request)
        +dashboard(request)
        +asset_catalog(request)
        +analytics_news(request)
    }

    class ManagementCommand {
        <<Background Worker>>
        +handle()
        -update_news()
        -generate_predictions()
    }

    class ExternalAPI {
        <<Interface>>
        +Finnhub
        +CoinMarketCap
        +NewsData
        +GoogleGemini
    }

    %% Связи между компонентами
    Views ..> Utils : uses
    ManagementCommand ..> Utils : uses
    Utils ..> ExternalAPI : calls
    Views ..> Asset : queries
    Views ..> PricePrediction : queries
    ManagementCommand ..> Asset : updates
    ManagementCommand ..> PricePrediction : creates
    ManagementCommand ..> News : creates
```

## 3. Схема Классов БД

```mermaid
classDiagram
    class Asset {
        +Integer id
        +String ticker
        +String name
        +String asset_type
        +Decimal market_cap
        +DateTime created_at
    }

    class PricePrediction {
        +Integer id
        +Integer asset_id
        +String horizon
        +Decimal predicted_price
        +Float confidence
        +String model_version
        +DateTime prediction_date
        +get_direction()
    }

    class HistoricalPrice {
        +Integer id
        +Integer asset_id
        +DateTime date
        +Decimal close_price
        +Decimal open_price
        +Decimal high_price
        +Decimal low_price
        +BigInt volume
    }

    class News {
        +Integer id
        +Integer asset_id
        +String title
        +Text content
        +URL source
        +DateTime published_at
    }

    class UserProfile {
        +Integer id
        +Integer user_id
        +String subscription_plan
        +DateTime created_at
    }

    class Sentiment {
        +Integer id
        +Integer asset_id
        +Float sentiment_score
        +String source_type
        +DateTime analysis_date
    }

    class User {
        +Integer id
        +String username
        +String email
        +String password
    }

    %% Отношения
    Asset "1" -- "*" PricePrediction : has
    Asset "1" -- "*" HistoricalPrice : has history
    Asset "1" -- "*" News : related to
    Asset "1" -- "*" Sentiment : has sentiment
    Asset "*" -- "*" UserProfile : favorites (M2M)
    User "1" -- "1" UserProfile : owns
```
