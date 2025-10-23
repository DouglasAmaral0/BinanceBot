"""
Estratégias para seleção de moedas para trading
"""
import time
from concurrent.futures import ThreadPoolExecutor

from config import config
from utils.helpers import log_info, log_error
from api.data_collectors import collect_all_data_for_coin
from analysis.technical import (
    calculate_rsi_for_coin,
    calculate_volatility_for_coin,
    calculate_ma_for_coin,
    calculate_macd_for_coin,
    calculate_bollinger_bands   # NOVO
)
from analysis.sentiment import analyze_sentiment_with_llm, get_combined_sentiment_score

from api.binance_client import (
    get_all_binance_coins, 
    last_sold_coin, 
    last_trade_time,
    get_24h_volume,          
    get_average_volume,        
    get_volume_ratio,  
    get_volume_analysis,      
    get_historical_data        
)


def filter_by_rsi_enhanced(coin_pair, rsi_buy_threshold=35, rsi_oversold=30):
    """
    Versão melhorada do filtro RSI com zonas dinâmicas e análise de volume.
    """
    # Calcula RSI
    rsi = calculate_rsi_for_coin(coin_pair)
    if rsi is None:
        return None
    
    # Análise de volume usando as novas funções
    volume_score = 0
    volume_analysis = get_volume_analysis(coin_pair)  # Nova função que criamos
    
    if volume_analysis:
        volume_score = volume_analysis.get('volume_score', 0)
        volume_signal = volume_analysis.get('volume_signal', 'NEUTRO')
        
        # Log do sinal de volume
        if volume_signal in ['FORTE_COMPRA', 'COMPRA']:
            log_info(f"{coin_pair}: Sinal de volume positivo: {volume_signal}")
    
    # Calcula volatilidade
    volatility = calculate_volatility_for_coin(coin_pair)
    if volatility is None:
        return None
    
    # Ajusta threshold baseado na volatilidade
    if volatility > 0.03:  # Alta volatilidade (3%+)
        rsi_buy_threshold = min(40, rsi_buy_threshold + 2)  # Mais tolerante
        log_info(f"{coin_pair}: Alta volatilidade detectada, RSI threshold ajustado para {rsi_buy_threshold}")
    
    # Sistema de scoring melhorado
    tech_score = 0
    
    # Score baseado em RSI (quanto menor, melhor para compra)
    if rsi < rsi_oversold:
        tech_score += 100  # Forte sinal de compra
        log_info(f"{coin_pair}: RSI em zona de SOBREVENDA FORTE ({rsi:.2f})")
    elif rsi < rsi_buy_threshold:
        tech_score += 70
    elif rsi < 50:
        tech_score += 40
    else:
        log_info(f"{coin_pair}: RSI={rsi:.2f} (>{50}, não considerado)")
        return None  # RSI muito alto, não considera
    
    # Adiciona score de volatilidade (volatilidade moderada é melhor)
    if 0.01 < volatility < 0.05:  # Volatilidade ideal entre 1% e 5%
        tech_score += volatility * 1500
    elif volatility <= 0.01:  # Muito baixa
        tech_score += volatility * 500
    else:  # Muito alta (>5%)
        tech_score += volatility * 800  # Penaliza um pouco
    
    # Adiciona score de volume
    tech_score += volume_score * 0.5  # Volume tem peso de 50% do seu score
    
    # Médias móveis e MACD para complementar
    sma_50 = calculate_ma_for_coin(coin_pair, period=50)
    sma_200 = calculate_ma_for_coin(coin_pair, period=200)
    macd_line, macd_signal, macd_histogram = calculate_macd_for_coin(coin_pair)
    
    # Bônus por tendência
    trend_bonus = 0
    if sma_50 and sma_200:
        if sma_50 > sma_200:
            trend_bonus += 15  # Golden cross
            log_info(f"{coin_pair}: Golden Cross detectado (SMA50 > SMA200)")
        else:
            trend_bonus -= 10
    
    if macd_line and macd_signal:
        if macd_line > macd_signal and macd_histogram > 0:
            trend_bonus += 10
            log_info(f"{coin_pair}: MACD positivo")
        elif macd_histogram < 0:
            trend_bonus -= 5
    
    tech_score += trend_bonus
    
    # Verificar Bollinger Bands se disponível
    bb_data = calculate_bollinger_bands(get_historical_data(coin_pair))
    bb_position_str = "n/a"
    if bb_data:
        bb_position = bb_data['position']
        bb_position_str = f"{bb_position:.2f}"
        if bb_position < 0.3:  # Próximo da banda inferior
            tech_score += 20
            log_info(f"{coin_pair}: Próximo da Bollinger Band inferior (posição: {bb_position:.2f})")
    
    # Preparar dados para retorno
    tech_data = {
        'pair': coin_pair,
        'coin': coin_pair.replace('USDT', ''),
        'rsi': rsi,
        'volatility': volatility,
        'sma_50': sma_50,
        'sma_200': sma_200,
        'macd': macd_line,
        'macd_signal': macd_signal,
        'volume_score': volume_score,
        'volume_signal': volume_analysis.get('volume_signal', 'DESCONHECIDO') if volume_analysis else 'ERRO',
        'bb_position': bb_data['position'] if bb_data else None,
        'tech_score': tech_score
    }
    
    # Log resumido
    sma_50_str = f"{sma_50:.4f}" if sma_50 is not None else "n/a"
    sma_200_str = f"{sma_200:.4f}" if sma_200 is not None else "n/a"
    macd_str = f"{macd_line:.4f}" if macd_line is not None else "n/a"
    
    log_info(
        f"{coin_pair}: RSI={rsi:.2f}, Vol={volatility*100:.2f}%, "
        f"Volume Score={volume_score:.0f}, BB Pos={bb_position_str}, "
        f"SMA50={sma_50_str}, SMA200={sma_200_str}, MACD={macd_str}, "
        f"Score Final={tech_score:.2f}"
    )
    
    return tech_data


# === NOVO: Sistema de Scoring Multicritério ===

def calculate_comprehensive_score(coin_pair):
    """
    Sistema de scoring que combina múltiplos indicadores.
    """
    score_components = {}
    total_score = 0
    
    # 1. RSI Score (peso: 25%)
    rsi = calculate_rsi_for_coin(coin_pair)
    if rsi:
        if rsi < 30:
            score_components['rsi'] = 100
        elif rsi < 40:
            score_components['rsi'] = 70
        elif rsi < 50:
            score_components['rsi'] = 40
        else:
            score_components['rsi'] = 0
    
    # 2. MACD Score (peso: 20%)
    macd_line, signal_line, histogram = calculate_macd_for_coin(coin_pair)
    if macd_line and signal_line:
        if histogram > 0 and macd_line > signal_line:
            score_components['macd'] = 80
        elif macd_line > signal_line:
            score_components['macd'] = 60
        else:
            score_components['macd'] = 20
    
    # 3. Volume Score (peso: 15%)
    volume_ratio = get_volume_ratio(coin_pair)  # Volume atual vs média
    if volume_ratio:
        if volume_ratio > 2.0:
            score_components['volume'] = 100
        elif volume_ratio > 1.5:
            score_components['volume'] = 70
        elif volume_ratio > 1.0:
            score_components['volume'] = 40
        else:
            score_components['volume'] = 20
    
    # 4. Bollinger Bands Score (peso: 15%)
    bb_position = calculate_bollinger_position(coin_pair)
    if bb_position:
        if bb_position < 0.2:  # Próximo da banda inferior
            score_components['bollinger'] = 90
        elif bb_position < 0.4:
            score_components['bollinger'] = 60
        else:
            score_components['bollinger'] = 30
    
    # 5. Support/Resistance Score (peso: 15%)
    sr_score = analyze_support_resistance(coin_pair)
    if sr_score:
        score_components['support'] = sr_score
    
    # 6. Momentum Score (peso: 10%)
    momentum = calculate_momentum(coin_pair, period=10)
    if momentum:
        if momentum > 0:
            score_components['momentum'] = 70
        else:
            score_components['momentum'] = 30
    
    # Calcular score ponderado
    weights = {
        'rsi': 0.25,
        'macd': 0.20,
        'volume': 0.15,
        'bollinger': 0.15,
        'support': 0.15,
        'momentum': 0.10
    }
    
    for component, value in score_components.items():
        if component in weights:
            total_score += value * weights[component]
    
    return total_score, score_components

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
    
    sma_50_str = f"{sma_50:.4f}" if sma_50 is not None else "n/a"
    sma_200_str = f"{sma_200:.4f}" if sma_200 is not None else "n/a"
    macd_str = f"{macd_line:.4f}" if macd_line is not None else "n/a"

    
    log_info(
        f"{coin_pair}: RSI={rsi:.2f}, Vol={vol*100:.2f}%, "
        f"SMA50={sma_50_str}, SMA200={sma_200_str}, MACD={macd_str}, "
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
        tech_data = filter_by_rsi_enhanced(pair)
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