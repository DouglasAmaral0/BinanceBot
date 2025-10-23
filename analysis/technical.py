"""
Funções para análise técnica de criptomoedas
"""
import pandas as pd
import numpy as np

from utils.helpers import log_info, log_error
from api.binance_client import get_historical_data


def calculate_rsi(data, period=14, column='close'):
    """
    Calcula o RSI para os dados fornecidos.
    
    Args:
        data: DataFrame com os dados históricos
        period: Período para cálculo do RSI (padrão: 14)
        column: Nome da coluna com os preços (padrão: 'close')
        
    Returns:
        float: Valor do RSI mais recente ou None em caso de erro
    """
    try:
        if len(data) < period + 1:
            log_error(f"Dados insuficientes para calcular RSI. Necessário: {period+1}, Disponível: {len(data)}")
            return None
            
        # Calcular diferenças
        delta = data[column].diff()
        
        # Separar ganhos e perdas
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        # Calcular média móvel de ganhos e perdas
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        
        # Calcular RS e RSI
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        # Retornar o valor mais recente
        return rsi.iloc[-1]
    except Exception as e:
        log_error(f"Erro ao calcular RSI: {e}")
        return None


def calculate_rsi_for_coin(coin_pair, period=14):
    """
    Calcula o RSI para um par de moedas específico.
    
    Args:
        coin_pair: Par de moedas (ex: 'BTCUSDT')
        period: Período para cálculo do RSI
        
    Returns:
        float: Valor do RSI ou None em caso de erro
    """
    try:
        # Obter dados históricos
        df = get_historical_data(coin_pair)
        
        if df.empty:
            log_error(f"Sem dados históricos para {coin_pair}")
            return None
            
        # Calcular RSI
        rsi_value = calculate_rsi(df, period=period)
        
        if rsi_value is not None:
            log_info(f"RSI para {coin_pair}: {rsi_value:.2f}")
            
        return rsi_value
    except Exception as e:
        log_error(f"Erro ao calcular RSI para {coin_pair}: {e}")
        return None


def calculate_sma(data, period=20, column='close'):
    """Calcula a média móvel simples (SMA)"""
    try:
        if len(data) < period:
            log_error(f"Dados insuficientes para calcular SMA{period}.")
            return None
        return data[column].rolling(window=period).mean().iloc[-1]
    except Exception as e:
        log_error(f"Erro ao calcular SMA: {e}")
        return None


def calculate_ema(data, period=20, column='close'):
    """Calcula a média móvel exponencial (EMA)"""
    try:
        if len(data) < period:
            log_error(f"Dados insuficientes para calcular EMA{period}.")
            return None
        return data[column].ewm(span=period, adjust=False).mean().iloc[-1]
    except Exception as e:
        log_error(f"Erro ao calcular EMA: {e}")
        return None


def calculate_macd(data, slow=26, fast=12, signal=9, column='close'):
    """Calcula valores de MACD (linha MACD, linha sinal e histograma)"""
    try:
        if len(data) < slow + signal:
            log_error("Dados insuficientes para calcular MACD.")
            return None, None, None
        ema_fast = data[column].ewm(span=fast, adjust=False).mean()
        ema_slow = data[column].ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return macd_line.iloc[-1], signal_line.iloc[-1], histogram.iloc[-1]
    except Exception as e:
        log_error(f"Erro ao calcular MACD: {e}")
        return None, None, None


def calculate_ma_for_coin(coin_pair, period=20, ma_type='sma'):
    """Calcula média móvel simples ou exponencial para um par"""
    df = get_historical_data(coin_pair)
    if df.empty:
        log_error(f"Sem dados históricos para {coin_pair}")
        return None
    if ma_type == 'ema':
        return calculate_ema(df, period)
    return calculate_sma(df, period)


def calculate_macd_for_coin(coin_pair, slow=26, fast=12, signal=9):
    """Calcula o MACD para um par de moedas"""
    df = get_historical_data(coin_pair)
    if df.empty:
        log_error(f"Sem dados históricos para {coin_pair}")
        return None, None, None
    return calculate_macd(df, slow, fast, signal)


def calculate_volatility(data, window=23, column='close'):
    """
    Calcula a volatilidade como desvio padrão dos retornos percentuais.
    
    Args:
        data: DataFrame com os dados históricos
        window: Janela para cálculo da volatilidade (padrão: 24 períodos)
        column: Nome da coluna com os preços (padrão: 'close')
        
    Returns:
        float: Valor da volatilidade ou None em caso de erro
    """
    try:
        if len(data) < window + 1:
            log_error(f"Dados insuficientes para calcular volatilidade. Necessário: {window+1}, Disponível: {len(data)}")
            return None
            
        # Calcular retornos percentuais
        returns = data[column].pct_change()
        
        # Pegar os retornos mais recentes dentro da janela
        recent_returns = returns.iloc[-window:]
        
        # Calcular desvio padrão
        volatility = recent_returns.std()
        
        return volatility
    except Exception as e:
        log_error(f"Erro ao calcular volatilidade: {e}")
        return None


def calculate_volatility_for_coin(coin_pair, window=23):
    """
    Calcula a volatilidade para um par de moedas específico.
    
    Args:
        coin_pair: Par de moedas (ex: 'BTCUSDT')
        window: Janela para cálculo da volatilidade
        
    Returns:
        float: Valor da volatilidade ou None em caso de erro
    """
    try:
        # Obter dados históricos
        df = get_historical_data(coin_pair)
        
        if df.empty:
            log_error(f"Sem dados históricos para {coin_pair}")
            return None
            
        # Calcular volatilidade
        volatility = calculate_volatility(df, window=window)
        
        if volatility is not None:
            log_info(f"Volatilidade para {coin_pair}: {volatility:.4f} ({volatility*100:.2f}%)")
            
        return volatility
    except Exception as e:
        log_error(f"Erro ao calcular volatilidade para {coin_pair}: {e}")
        return None


def dynamic_stop_loss_take_profit(coin_pair, base_stop_loss=0.05, base_take_profit=0.10):
    """
    Ajusta stop_loss e take_profit dinamicamente de acordo com a volatilidade.
    
    Args:
        coin_pair: Par de moedas (ex: 'BTCUSDT')
        base_stop_loss: Valor base para stop loss (padrão: 0.05 ou 5%)
        base_take_profit: Valor base para take profit (padrão: 0.10 ou 10%)
        
    Returns:
        tuple: (stop_loss, take_profit) - valores ajustados ou valores base em caso de erro
    """
    # Obter volatilidade
    volatility = calculate_volatility_for_coin(coin_pair, window=24)  # 24 períodos (horas)
    
    if volatility is None:
        log_info(f"Usando valores base para stop loss e take profit para {coin_pair}")
        return base_stop_loss, base_take_profit
    
    # Ajustar os valores com base na volatilidade
    # Exemplo: se volatilidade=0.02 (2%), multiplicamos por 2.5 e 5.0
    new_stop_loss = max(base_stop_loss, 2.5 * volatility)
    new_take_profit = max(base_take_profit, 5.0 * volatility)
    
    log_info(f"Ajuste dinâmico para {coin_pair}:")
    log_info(f"Volatilidade: {volatility*100:.2f}%")
    log_info(f"Stop Loss: {base_stop_loss*100:.2f}% → {new_stop_loss*100:.2f}%")
    log_info(f"Take Profit: {base_take_profit*100:.2f}% → {new_take_profit*100:.2f}%")
    
    return new_stop_loss, new_take_profit

def calculate_bollinger_bands(data, period=20, std_dev=2):
    """
    Calcula Bandas de Bollinger.
    """
    sma = data['close'].rolling(window=period).mean()
    std = data['close'].rolling(window=period).std()
    
    upper_band = sma + (std * std_dev)
    lower_band = sma - (std * std_dev)
    
    current_price = data['close'].iloc[-1]
    
    # Posição relativa (0 = banda inferior, 1 = banda superior)
    position = (current_price - lower_band.iloc[-1]) / (upper_band.iloc[-1] - lower_band.iloc[-1])
    
    return {
        'upper': upper_band.iloc[-1],
        'middle': sma.iloc[-1],
        'lower': lower_band.iloc[-1],
        'position': position,
        'current_price': current_price
    }


def detect_support_resistance(data, window=20):
    """
    Detecta níveis de suporte e resistência.
    """
    highs = data['high'].rolling(window=window).max()
    lows = data['low'].rolling(window=window).min()
    
    current_price = data['close'].iloc[-1]
    
    # Encontra suporte mais próximo
    recent_lows = lows.tail(window).unique()
    support = max([l for l in recent_lows if l < current_price], default=0)
    
    # Encontra resistência mais próxima  
    recent_highs = highs.tail(window).unique()
    resistance = min([h for h in recent_highs if h > current_price], default=float('inf'))
    
    # Score baseado na proximidade do suporte
    if support > 0:
        distance_from_support = (current_price - support) / current_price
        if distance_from_support < 0.02:  # Muito próximo do suporte
            return 90
        elif distance_from_support < 0.05:
            return 70
        else:
            return 50
    return 40


def calculate_volume_profile(coin_pair, periods=24):
    """
    Analisa o perfil de volume.
    """
    data = get_historical_data(coin_pair, interval='1h', limit=periods*2)
    if data.empty:
        return None
    
    recent_volume = data['volume'].tail(periods).mean()
    previous_volume = data['volume'].head(periods).mean()
    
    # Ratio de volume (recente vs anterior)
    volume_ratio = recent_volume / previous_volume if previous_volume > 0 else 1
    
    # Detecta aumento súbito de volume
    last_3_hours = data['volume'].tail(3).mean()
    avg_volume = data['volume'].mean()
    
    volume_spike = last_3_hours / avg_volume if avg_volume > 0 else 1
    
    return {
        'ratio': volume_ratio,
        'spike': volume_spike,
        'is_increasing': volume_ratio > 1.2,
        'has_spike': volume_spike > 2.0
    }
def smart_exit_conditions(coin_pair, entry_price, current_price, time_held):
    """
    Condições de saída mais inteligentes baseadas em múltiplos fatores.
    """
    pnl = (current_price - entry_price) / entry_price
    
    # Condições de saída rápida (scalping)
    if time_held < 3600:  # Menos de 1 hora
        if pnl > 0.015:  # 1.5% de lucro rápido
            return "QUICK_PROFIT"
    
    # Saída por reversão de indicadores
    rsi = calculate_rsi_for_coin(coin_pair)
    if rsi and rsi > 70 and pnl > 0:
        return "RSI_OVERBOUGHT"
    
    # Saída por perda de momentum
    macd_line, signal_line, _ = calculate_macd_for_coin(coin_pair)
    if macd_line and signal_line:
        if macd_line < signal_line and pnl > 0.005:
            return "MOMENTUM_LOSS"
    
    # Saída por quebra de suporte
    bb_data = calculate_bollinger_bands(get_historical_data(coin_pair))
    if bb_data and current_price < bb_data['middle'] and pnl < -0.02:
        return "SUPPORT_BREAK"
    
    return None


def check_technical_indicators(coin_pair):
    """
    Verifica indicadores técnicos para um par de moedas.
    
    Args:
        coin_pair: Par de moedas (ex: 'BTCUSDT')
        
    Returns:
        dict: Dicionário com os indicadores técnicos
    """
    # Calcular RSI
    rsi = calculate_rsi_for_coin(coin_pair)
    
    # Calcular volatilidade
    volatility = calculate_volatility_for_coin(coin_pair)
    
    # Calcular stop loss e take profit dinâmicos
    stop_loss, take_profit = dynamic_stop_loss_take_profit(coin_pair)
    
    # Interpretar RSI
    rsi_signal = None
    if rsi is not None:
        if rsi < 30:
            rsi_signal = "compra"  # Sobrevendido
        elif rsi > 70:
            rsi_signal = "venda"   # Sobrecomprado
        else:
            rsi_signal = "neutro"
    
    # Calcular "tech score" - métrica técnica combinada
    tech_score = None
    if rsi is not None and volatility is not None:
        # Quanto menor o RSI (até certo ponto) e maior a volatilidade, melhor o score
        if rsi < 50:
            tech_score = (50 - rsi) + (volatility * 1000)
    
    # Montar resultados
    results = {
        "rsi": rsi,
        "rsi_signal": rsi_signal,
        "volatility": volatility,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "tech_score": tech_score
    }
    
    return results