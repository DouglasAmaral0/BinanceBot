"""
Coletores de dados de fontes externas (Reddit, Twitter, News APIs)
"""
import praw
import tweepy
import requests
from requests.exceptions import RequestException
from prawcore.exceptions import PrawcoreException
from datetime import datetime
import json

from config import config
from utils.helpers import log_info, log_error

# Inicialização da API do Reddit
reddit = praw.Reddit(
    client_id=config.REDDIT_CLIENT_ID,
    client_secret=config.REDDIT_CLIENT_SECRET,
    user_agent=config.REDDIT_USER_AGENT
)

# Twitter API - Comentado até configurar
# twitter_auth = tweepy.OAuth1UserHandler(
#     config.TWITTER_API_KEY, config.TWITTER_API_SECRET,
#     config.TWITTER_ACCESS_TOKEN, config.TWITTER_ACCESS_SECRET
# )
# twitter_api = tweepy.API(twitter_auth)


def init_collectors():
    """
    Inicializa os coletores de dados e verifica se estão funcionando
    """
    # Verificar conexão com Reddit
    try:
        subreddit = reddit.subreddit("CryptoCurrency")
        _ = subreddit.subscribers
        log_info(f"Reddit API inicializada com sucesso. Subscribers: {subreddit.subscribers}")
    except PrawcoreException as e:
        log_error(f"Falha ao conectar ao Reddit: {e}")
    except Exception as e:
        log_error(f"Erro ao inicializar Reddit API: {e}")
    
    # Verificar News API
    try:
        url = f"https://newsapi.org/v2/everything?q=crypto&pageSize=1&apiKey={config.NEWS_API_KEY}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            log_info("News API inicializada com sucesso")
        else:
            log_error(f"Falha ao inicializar News API. Status code: {response.status_code}")
    except RequestException as e:
        log_error(f"Erro ao verificar News API: {e}")
    
    # Verificar Twitter API
    # try:
    #     twitter_user = twitter_api.verify_credentials()
    #     log_info(f"Twitter API inicializada. Usuário: {twitter_user.screen_name}")
    # except Exception as e:
    #     log_error(f"Falha ao inicializar Twitter API: {e}")


def get_reddit_data(coin, limit=20):
    """
    Obtém posts recentes do Reddit para a criptomoeda especificada.
    
    Args:
        coin (str): Nome da criptomoeda (ex: 'BTC', 'ETH')
        limit (int): Número máximo de posts a serem obtidos
        
    Returns:
        list: Lista de dicionários com informações dos posts
    """
    try:
        # Lista de subreddits relevantes
        subreddits = [
            'CryptoCurrency', 
            'CryptoMarkets', 
            f'{coin}', 
            f'{coin}Markets',
            'binance',
            'CryptoMoonShots'
        ]
        
        all_posts = []
        
        for subreddit_name in subreddits:
            try:
                subreddit = reddit.subreddit(subreddit_name)
                search_queries = [coin]
                
                # Se o nome for curto, adicione nomes completos
                if len(coin) <= 4:
                    common_names = {
                        'BTC': 'Bitcoin',
                        'ETH': 'Ethereum',
                        'SOL': 'Solana',
                        'ADA': 'Cardano',
                        'DOT': 'Polkadot',
                        'AVAX': 'Avalanche',
                        'DOGE': 'Dogecoin',
                        'SHIB': 'Shiba Inu',
                        'XRP': 'Ripple',
                        'BNB': 'Binance Coin'
                    }
                    if coin in common_names:
                        search_queries.append(common_names[coin])
                
                for query in search_queries:
                    try:
                        search_results = subreddit.search(query, limit=limit, time_filter='week')

                        for post in search_results:
                            if post.selftext:
                                truncated_text = post.selftext[:1000] if len(post.selftext) > 1000 else post.selftext
                                all_posts.append({
                                    'title': post.title,
                                    'text': truncated_text,
                                    'score': post.score,
                                    'created_utc': post.created_utc,
                                    'url': post.url,
                                    'subreddit': subreddit_name
                                })
                    except PrawcoreException as pe:
                        log_error(f"Erro de conexão ao buscar '{query}' em {subreddit_name}: {pe}")
                        continue
            except PrawcoreException as e:
                log_error(f"Erro ao acessar subreddit {subreddit_name}: {e}")
                continue
            except Exception as e:
                log_error(f"Falha inesperada em subreddit {subreddit_name}: {e}")
                continue
                
        log_info(f"Obtidos {len(all_posts)} posts do Reddit para {coin}")
        return all_posts
    except PrawcoreException as e:
        log_error(f"Erro de conexão com Reddit para {coin}: {e}")
        return []
    except Exception as e:
        log_error(f"Erro ao coletar dados do Reddit para {coin}: {e}")
        return []


def get_twitter_data(coin, count=30):
    """
    Obtém tweets recentes sobre a criptomoeda especificada.
    Nota: Esta função está preparada mas comentada até a configuração da API do Twitter.
    
    Args:
        coin (str): Nome da criptomoeda (ex: 'BTC', 'ETH')
        count (int): Número máximo de tweets a serem obtidos
        
    Returns:
        list: Lista de dicionários com informações dos tweets
    """
    # Função comentada até a configuração da API do Twitter
    return []
    
    # try:
    #     # Mapeia símbolos de moedas para termos de busca completos
    #     extended_terms = {
    #         'BTC': 'Bitcoin OR BTC',
    #         'ETH': 'Ethereum OR ETH',
    #         'SOL': 'Solana OR SOL',
    #         'DOGE': 'Dogecoin OR DOGE',
    #         'ADA': 'Cardano OR ADA',
    #         'DOT': 'Polkadot OR DOT',
    #         'SHIB': 'ShibaInu OR SHIB',
    #         'AVAX': 'Avalanche OR AVAX',
    #         'BNB': 'Binance OR BNB',
    #         'XRP': 'Ripple OR XRP'
    #     }
    #     
    #     # Usa o termo estendido se disponível, senão usa apenas o símbolo
    #     search_term = extended_terms.get(coin, coin)
    #     search_term = f"{search_term} crypto"
    #     
    #     tweets = twitter_api.search_tweets(
    #         q=search_term,
    #         count=count,
    #         lang='en',
    #         result_type='mixed',  # mixed, recent, popular
    #         tweet_mode='extended'
    #     )
    #     
    #     tweet_data = []
    #     for tweet in tweets:
    #         tweet_data.append({
    #             'text': tweet.full_text,
    #             'created_at': tweet.created_at,
    #             'retweet_count': tweet.retweet_count,
    #             'favorite_count': tweet.favorite_count,
    #             'user_followers': tweet.user.followers_count
    #         })
    #     
    #     log_info(f"Obtidos {len(tweet_data)} tweets para {coin}")
    #     return tweet_data
    # except Exception as e:
    #     log_error(f"Erro ao coletar dados do Twitter para {coin}: {e}")
    #     return []


def get_crypto_news(coin, limit=5):
    """
    Obtém notícias recentes sobre a criptomoeda.
    
    Args:
        coin (str): Nome da criptomoeda
        limit (int): Número máximo de notícias
        
    Returns:
        list: Lista de artigos de notícias
    """
    try:
        # Mapeia símbolos para nomes completos para melhorar a busca
        coin_names = {
            'BTC': 'Bitcoin',
            'ETH': 'Ethereum',
            'SOL': 'Solana',
            'DOGE': 'Dogecoin',
            'ADA': 'Cardano',
            'XRP': 'Ripple',
            'BNB': 'Binance'
        }
        
        search_term = coin_names.get(coin, coin)
        
        # Use News API
        url = f"https://newsapi.org/v2/everything?q={search_term} crypto&sortBy=publishedAt&pageSize={limit}&apiKey={config.NEWS_API_KEY}"
        
        response = requests.get(url, timeout=10)
        data = response.json()
        
        articles = []
        if 'articles' in data:
            for article in data['articles']:
                articles.append({
                    'title': article['title'],
                    'description': article['description'] if 'description' in article else '',
                    'url': article['url'],
                    'publishedAt': article['publishedAt'],
                    'source': article['source']['name'] if 'source' in article and 'name' in article['source'] else 'Unknown'
                })
        
        log_info(f"Obtidas {len(articles)} notícias para {coin}")
        return articles
    except RequestException as e:
        log_error(f"Erro de requisição ao coletar notícias para {coin}: {e}")
        return []
    except Exception as e:
        log_error(f"Erro ao coletar notícias para {coin}: {e}")
        return []


def collect_all_data_for_coin(coin):
    """
    Coleta todos os dados disponíveis para uma moeda específica.
    
    Args:
        coin (str): Símbolo da criptomoeda
        
    Returns:
        dict: Dicionário com todos os dados coletados
    """
    log_info(f"Coletando dados para {coin}...")
    
    # Coleta dados de diferentes fontes
    reddit_data = get_reddit_data(coin)
    news_data = get_crypto_news(coin)
    twitter_data = get_twitter_data(coin)  # Retornará lista vazia até configurar
    
    # Combina todos os dados
    all_data = {
        'reddit': reddit_data,
        'news': news_data,
        'twitter': twitter_data,
        'collected_at': datetime.now().isoformat()
    }
    
    # Verifica se temos dados suficientes para análise
    data_count = len(reddit_data) + len(news_data) + len(twitter_data)
    log_info(f"Total de {data_count} itens coletados para {coin}")
    
    return all_data