from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Config:
    """Configurações gerais do bot"""
    # Chaves da Binance
    BINANCEAPIKEY: str = os.getenv("BINANCE_API_KEY", "")
    BINANCESECRETKEY: str = os.getenv("BINANCE_SECRET_KEY", "")
    BINANCETESTSECRETKEY: str = os.getenv("BINANCE_TEST_SECRET_KEY", "")
    BINANCETESTAPIKEY: str = os.getenv("BINANCE_TEST_API_KEY", "")

    # Parâmetros de negociação
    MIN_VOLUME_FILTER: float = 1_000_000
    BINANCE_FEE_PERCENT: float = 0.001
    DEFAULT_INTERVAL: int = 15  # minutos
    DEFAULT_STOP_LOSS_PCT: float = 0.05
    DEFAULT_TAKE_PROFIT_PCT: float = 0.10
    COOLDOWN_TIME: int = 3600  # segundos
    MIN_USDT_FOR_TRADE: float = 10.0
    PERCENT_USDT_TO_INVEST_PER_TRADE: float = 0.95
    # Percentual do valor total do portfólio utilizado em cada operação
    PERCENT_PORTFOLIO_PER_TRADE: float = 0.10
    # Perda máxima permitida por dia em USDT antes de pausar as operações
    MAX_DAILY_LOSS_USDT: float = 50.0
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
    OPENAI_KEY: str = os.getenv("OPENAI_KEY", "")
    NEWS_API_KEY: str = os.getenv("NEWS_API_KEY", "")
    REDDIT_CLIENT_ID: str = os.getenv("REDDIT_CLIENT_ID", "")
    REDDIT_CLIENT_SECRET: str = os.getenv("REDDIT_CLIENT_SECRET", "")
    REDDIT_USER_AGENT: str = os.getenv("REDDIT_USER_AGENT", "crypto-bot")
    TWITTER_API_KEY: str = os.getenv("TWITTER_API_KEY", "")
    TWITTER_API_SECRET: str = os.getenv("TWITTER_API_SECRET", "")
    TWITTER_ACCESS_TOKEN: str = os.getenv("TWITTER_ACCESS_TOKEN", "")
    TWITTER_ACCESS_SECRET: str = os.getenv("TWITTER_ACCESS_SECRET", "")

    # Configurações de análise de sentimento
    SENTIMENT_CACHE_DURATION: int = 3600

# Instância padrão
config = Config()
