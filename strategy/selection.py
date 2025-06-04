"""
Estratégias para seleção de moedas para trading
"""
import time
from concurrent.futures import ThreadPoolExecutor

from config import config
from utils.helpers import log_info, log_error
from api.binance_client import get_all_binance_coins, last_sold_coin, last_trade_time
from api.data_collectors import collect_all_data_for_coin
from analysis.technical import (
    calculate_rsi_for_coin,
    calculate_volatility_for_coin,
    calculate_ma_for_coin,
    calculate_macd_for_coin,
)
from analysis.sentiment import analyze_sentiment_with_llm, get_combined_sentiment_score


def filter_by_rsi(coin_pair, max_rsi=50):
    """
    Filtra moedas com base no RSI, buscando oportunidades de compra.
    
    Args:
        coin_pair (str): Par de moedas (ex: 'BTCUSDT')
        max_rsi (float): Valor máximo de RSI para considerar a moeda
        
    Returns:
        dict: Dados técnicos ou None se a moeda não passar no filtro
    """
    # Calcula RSI
    rsi = calculate_rsi_for_coin(coin_pair)
    if rsi is None:
        return None
        
    # Considera apenas moedas com RSI < max_rsi
    if rsi >= max_rsi:
        log_info(f"{coin_pair}: RSI={rsi:.2f} (>{max_rsi}, não considerado)")
        return None
        
    # Calcula volatilidade
    vol = calculate_volatility_for_coin(coin_pair)
    if vol is None:
        return None

    # Médias móveis e MACD para complementar o filtro
    sma_50 = calculate_ma_for_coin(coin_pair, period=50)
    sma_200 = calculate_ma_for_coin(coin_pair, period=200)
    macd_line, macd_signal, _ = calculate_macd_for_coin(coin_pair)

    # Cálculo do score técnico preliminar
    tech_score = (max_rsi - rsi) + (vol * 1000)
    trend_bonus = 0
    if sma_50 and sma_200:
        if sma_50 > sma_200:
            trend_bonus += 10
        else:
            trend_bonus -= 10
    if macd_line and macd_signal:
        if macd_line > macd_signal:
            trend_bonus += 5
        else:
            trend_bonus -= 5
    tech_score += trend_bonus
    tech_data = {
        'pair': coin_pair,
        'coin': coin_pair.replace('USDT', ''),
        'rsi': rsi,
        'volatility': vol,
        'sma_50': sma_50,
        'sma_200': sma_200,
        'macd': macd_line,
        'tech_score': tech_score
    }
    
    log_info(
        f"{coin_pair}: RSI={rsi:.2f}, Vol={vol*100:.2f}%, SMA50={sma_50:.4f if sma_50 else 'n/a'}, "
        f"SMA200={sma_200:.4f if sma_200 else 'n/a'}, MACD={macd_line:.4f if macd_line else 'n/a'}, "
        f"Tech Score={tech_score:.2f}"
    )
    return tech_data


def analyze_sentiment_for_candidates(candidates, max_workers=5):
    """
    Analisa o sentimento para os candidatos técnicos mais promissores.
    
    Args:
        candidates (list): Lista de dicionários com dados técnicos
        max_workers (int): Número máximo de workers para processamento paralelo
        
    Returns:
        list: Lista de candidatos com dados de sentimento
    """
    results = []
    
    log_info(f"\n=== ANALISANDO SENTIMENTO PARA {len(candidates)} CANDIDATOS ===")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Mapa de futuros para candidatos
        future_to_candidate = {}
        
        # Inicia análise de sentimento para cada candidato
        for candidate in candidates:
            coin = candidate['coin']
            
            # Coleta dados para a moeda
            future = executor.submit(collect_all_data_for_coin, coin)
            future_to_candidate[future] = candidate
        
        # Processa resultados
        for future in future_to_candidate:
            candidate = future_to_candidate[future]
            try:
                # Obtém dados coletados
                collected_data = future.result()
                
                # Analisa sentimento com base nos dados coletados
                sentiment_result = analyze_sentiment_with_llm(candidate['coin'], collected_data)
                
                # Calcula score de sentimento normalizado
                sentiment_score = sentiment_result.get('score', 50)
                buy_recommendation = sentiment_result.get('buy_recommendation', 'NEUTRO')
                
                # Ajusta o peso do sentimento no score final
                # Quanto mais próximo de 100, melhor o sentimento
                sentiment_weight = (sentiment_score - 50) * 2  # Converte a escala de 50-100 para 0-100
                
                # Normaliza o peso do sentimento para ser comparável com o score técnico
                normalized_sentiment = sentiment_weight * 5
                
                # Cálculo do score final (70% técnico + 30% sentimento)
                final_score = (candidate['tech_score'] * 0.7) + (normalized_sentiment * 0.3)
                
                # Bônus para recomendações explícitas de compra
                if buy_recommendation == 'SIM':
                    final_score += 50
                elif buy_recommendation == 'NÃO':
                    final_score -= 50
                
                # Armazena todos os dados
                combined_data = {
                    **candidate,
                    'sentiment_score': sentiment_score,
                    'sentiment': sentiment_result.get('sentiment', 'neutro'),
                    'buy_recommendation': buy_recommendation,
                    'key_factors': sentiment_result.get('key_factors', []),
                    'final_score': final_score
                }
                
                results.append(combined_data)
                
                # Log detalhado
                log_info(f"\n{candidate['pair']}:")
                log_info(f"Score Técnico: {candidate['tech_score']:.2f}")
                log_info(f"Score de Sentimento: {sentiment_score}/100 ({sentiment_result.get('sentiment', 'neutro')})")
                log_info(f"Recomendação: {buy_recommendation}")
                log_info(f"Score Final: {final_score:.2f}")
                
            except Exception as e:
                log_error(f"Erro ao processar {candidate['pair']}: {e}")
    
    return results


def choose_best_coin():
    """
    Seleciona a melhor moeda para trading com base em análise técnica e de sentimento.
    
    Returns:
        str: Par de trading da melhor moeda (ex: 'BTCUSDT') ou None se nenhuma for adequada
    """
    best_coin = None
    current_time = time.time()
    
    # Obter lista de moedas disponíveis
    all_coins = get_all_binance_coins()
    
    # Limita a quantidade de moedas para análise
    if len(all_coins) > config.MAX_COINS_TO_ANALYZE:
        log_info(f"Limitando análise às {config.MAX_COINS_TO_ANALYZE} moedas mais populares entre {len(all_coins)} disponíveis")
        popular_coins = ['BTC', 'ETH', 'BNB', 'SOL', 'XRP', 'ADA', 'DOGE', 'SHIB', 'DOT', 'AVAX',
                         'MATIC', 'LTC', 'LINK', 'UNI', 'ATOM', 'XLM', 'NEAR', 'ETC', 'ALGO', 'FTM']
        
        # Adiciona as moedas populares primeiro, se existirem na lista
        prioritized_coins = []
        for coin in popular_coins:
            if coin in all_coins:
                prioritized_coins.append(coin)
                
        # Adiciona outras moedas até completar o máximo
        other_coins = [c for c in all_coins if c not in prioritized_coins]
        coins_to_analyze = prioritized_coins + other_coins[:config.MAX_COINS_TO_ANALYZE - len(prioritized_coins)]
    else:
        coins_to_analyze = all_coins
    
    log_info(f"\n=== ANÁLISE DE SELEÇÃO DE MOEDA ===")
    log_info(f"Analisando {len(coins_to_analyze)} moedas")

    # Filtra moedas com base em RSI e volatilidade
    rsi_candidates = []
    
    for coin in coins_to_analyze:
        pair = f"{coin}USDT"
        
        # Respeita cooldown da última venda
        if pair == last_sold_coin and (current_time - last_trade_time) < config.COOLDOWN_TIME:
            log_info(f"Pulando {pair} devido ao período de cooldown ({((current_time - last_trade_time)/3600):.1f}h de {(config.COOLDOWN_TIME/3600):.1f}h)")
            continue

        # Filtra por RSI
        tech_data = filter_by_rsi(pair)
        if tech_data:
            rsi_candidates.append(tech_data)
    
    # Se não houver candidatos, retorna None
    if not rsi_candidates:
        log_info("Nenhum candidato encontrado com base em RSI e volatilidade")
        return None
        
    # Ordena candidatos por score técnico
    rsi_candidates.sort(key=lambda x: x['tech_score'], reverse=True)
    
    # Seleciona os top 5 para análise de sentimento
    sentiment_candidates = rsi_candidates[:5]
    
    log_info("\n=== TOP 5 CANDIDATOS PARA ANÁLISE DE SENTIMENTO ===")
    for i, candidate in enumerate(sentiment_candidates, 1):
        log_info(f"{i}. {candidate['pair']}: RSI={candidate['rsi']:.2f}, Vol={candidate['volatility']*100:.2f}%, Score={candidate['tech_score']:.2f}")
    
    # Analisa sentimento para os candidatos
    final_candidates = analyze_sentiment_for_candidates(sentiment_candidates)
    
    # Se houver candidatos finais, seleciona o melhor
    if final_candidates:
        # Ordena por score final
        final_candidates.sort(key=lambda x: x['final_score'], reverse=True)
        best_candidate = final_candidates[0]
        best_coin = best_candidate['pair']
        
        log_info(f"\nMelhor moeda selecionada: {best_coin} com Score Final={best_candidate['final_score']:.2f}")
        log_info(f"RSI: {best_candidate['rsi']:.2f}, Volatilidade: {best_candidate['volatility']*100:.2f}%")
        log_info(f"Sentimento: {best_candidate['sentiment_score']}/100, Recomendação: {best_candidate['buy_recommendation']}")
        
        if 'key_factors' in best_candidate and best_candidate['key_factors']:
            log_info("Fatores-chave:")
            for factor in best_candidate['key_factors']:
                log_info(f"- {factor}")
    else:
        log_info("\nNenhuma moeda adequada encontrada após análise de sentimento.")
    
    log_info("==================================")
    return best_coin