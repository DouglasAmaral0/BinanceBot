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
    MIN_VOLUME_FILTER: float = 8_000_000
    BINANCE_FEE_PERCENT: float = 0.001
    DEFAULT_INTERVAL: int = 30  # minutos
    DEFAULT_STOP_LOSS_PCT: float = 0.10
    DEFAULT_TAKE_PROFIT_PCT: float = 0.25
    COOLDOWN_TIME: int = 1800  # segundos
    MIN_USDT_FOR_TRADE: float = 10.0
    PERCENT_USDT_TO_INVEST_PER_TRADE: float = 1.0
    # Percentual do valor total do portfólio utilizado em cada operação
    PERCENT_PORTFOLIO_PER_TRADE: float = 1.0
    # Perda máxima permitida por dia em USDT antes de pausar as operações
    MAX_DAILY_LOSS_USDT: float = 100
    MAX_COINS_TO_ANALYZE: int = 60
    POSITION_MAX_HOLD_TIME = 42400  # 6 horas
    POSITION_FORCE_SELL_TIME = 172800  # 12 horas
    TRAILING_STOP_DISTANCE = 0.08   # 1.5%
    RSI_BUY_THRESHOLD = 38        # Mais agressivo
    DEFAULT_STOP_LOSS_PCT = 0.09        # 3% para volatilidade
    DEFAULT_TAKE_PROFIT_PCT = 0.20    # 5% target rápido
    USE_TRAILING_STOP = True
    MAX_TRADES_PER_DAY = 3

    # Configurações de LLM
    LLM_MODEL_NAME: str = "openai/gpt-oss-20b"
    LLM_SERVER_URL: str = "http://192.168.1.164:7800"
    LLM_SERVER_TIMEOUT: int = 10000
    LLM_RESPONSE_WAIT: int = 3000
    LLM_REQUEST_RETRIES: int = 3
    LLM_PROMPT_MAX_LENGTH: int = 16000
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
    SENTIMENT_CACHE_DURATION: int = 36000
    
    MAX_TRADES_PER_DAY: int = 5  # Mais trades permitidos
    MIN_TIME_BETWEEN_TRADES: int = 1800  # 30 min entre trades
    
    # EXCLUIR forex mas permitir mais altcoins
    EXCLUDED_SYMBOLS = ['EUR', 'GBP', 'AUD', 'USD', 'CAD']
    EXCLUDED_SUFFIXES = ['UP', 'DOWN', 'BEAR', 'BULL']
    
    # MOEDAS VOLÁTEIS para agressividade (Top 30 + altcoins promissoras)
    PREFERRED_COINS = [
        # Top caps (base sólida)
        'BTC', 'ETH', 'BNB', 'SOL', 'XRP',
        # Alta volatilidade + liquidez
        'AVAX', 'NEAR', 'FTM', 'MATIC', 'ATOM',
        'LINK', 'UNI', 'ALGO', 'SAND', 'MANA',
        'AXS', 'APE', 'OP', 'ARB', 'DOGE',
        # Moonshots (menor alocação mas alto potencial)
        'INJ', 'SEI', 'TIA', 'SUI', 'APT'
    ]
    
    MIN_SIGNALS_REQUIRED: int = 2
    ALLOW_NEUTRAL_TREND: bool = True
    
    MIN_TECH_SCORE: float = 40  # Antes: 60

# Instância padrão
config = Config()
