from dataclasses import dataclass

@dataclass
class Config:
    """Configurações gerais do bot"""
    # Chaves da Binance
    BINANCEAPIKEY: str = ""
    BINANCESECRETKEY: str = ""
    BINANCETESTSECRETKEY: str = ""
    BINANCETESTAPIKEY: str = ""

    # Parâmetros de negociação
    MIN_VOLUME_FILTER: float = 1_000_000
    BINANCE_FEE_PERCENT: float = 0.001
    DEFAULT_INTERVAL: int = 15  # minutos
    DEFAULT_STOP_LOSS_PCT: float = 0.05
    DEFAULT_TAKE_PROFIT_PCT: float = 0.10
    COOLDOWN_TIME: int = 3600  # segundos
    MIN_USDT_FOR_TRADE: float = 10.0
    PERCENT_USDT_TO_INVEST_PER_TRADE: float = 0.95
    MAX_COINS_TO_ANALYZE: int = 20

    # Configurações de LLM
    LLM_MODEL_NAME: str = "local-llm"
    LLM_SERVER_URL: str = "http://localhost:8000"
    LLM_SERVER_TIMEOUT: int = 10
    LLM_RESPONSE_WAIT: int = 30
    LLM_REQUEST_RETRIES: int = 3
    LLM_PROMPT_MAX_LENGTH: int = 4000
    USE_OPENAI_FALLBACK: bool = False

    # Chaves de serviços externos
    OPENAI_KEY: str = ""
    NEWS_API_KEY: str = ""
    REDDIT_CLIENT_ID: str = ""
    REDDIT_CLIENT_SECRET: str = ""
    REDDIT_USER_AGENT: str = "crypto-bot"
    TWITTER_API_KEY: str = ""
    TWITTER_API_SECRET: str = ""
    TWITTER_ACCESS_TOKEN: str = ""
    TWITTER_ACCESS_SECRET: str = ""

    # Configurações de análise de sentimento
    SENTIMENT_CACHE_DURATION: int = 3600

# Instância padrão
config = Config()
