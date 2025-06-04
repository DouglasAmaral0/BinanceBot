"""
Funções auxiliares e utilitárias para o bot
"""
import time
import json
from datetime import datetime
import math # Adicionado


def log_info(message):
    """
    Função para log padronizado de informações
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S') # StringFormatTime.
    print(f"[{timestamp}] [INFO] {message}")


def log_warning(message):
    """
    Função para log padronizado de avisos
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] [WARNING] {message}")


def log_error(message):
    """
    Função para log padronizado de erros
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] [ERROR] {message}")


def log_trade(action, symbol, quantity, price, total_value, fees_paid=0.0, net_value=0.0):
    """
    Função para log padronizado de operações de trading
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if action.upper() == "BUY":
        print(f"[{timestamp}] [TRADE] {action} {quantity:.8f} {symbol} @ {price:.8f} = {total_value:.2f} USDT. Custo com taxas: {net_value:.2f} USDT. Taxas: {fees_paid:.4f} USDT")
    elif action.upper() == "SELL":
        print(f"[{timestamp}] [TRADE] {action} {quantity:.8f} {symbol} @ {price:.8f} = {total_value:.2f} USDT. Recebido líquido: {net_value:.2f} USDT. Taxas: {fees_paid:.4f} USDT")
    else:
        print(f"[{timestamp}] [TRADE] {action} {quantity} {symbol} @ {price} = {total_value:.2f} USDT")


def log_performance(label, value):
    """Loga métricas de performance como lucro ou perda acumulada"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] [PERF] {label}: {value:.2f} USDT")


def format_percentage(value, precision=2):
    """
    Formata um valor como percentagem
    """
    return f"{value * 100:.{precision}f}%" #Precision é referente a quantidade de casas decimais


def wait_with_progress(minutes):
    """
    Espera o número especificado de minutos, mostrando progresso a cada minuto
    """
    log_info(f"Aguardando {minutes} minutos...")
    start_time = time.time()
    end_time = start_time + (minutes * 60)
    
    next_minute_log_time = start_time + 60
    # Correção para logar o primeiro minuto corretamente e evitar log imediato se o intervalo for < 1 min
    if minutes >= 1:
        log_info(f"Progresso: 0/{minutes} minutos ({minutes} restantes)")

    while time.time() < end_time:
        time.sleep(1)
        current_time = time.time()
        if current_time >= next_minute_log_time and minutes >=1:
            minutes_passed = int((current_time - start_time) / 60)
            minutes_remaining = minutes - minutes_passed
            log_info(f"Progresso: {minutes_passed}/{minutes} minutos ({minutes_remaining} restantes)")
            next_minute_log_time = start_time + ( (minutes_passed + 1) * 60) # Garante que o próximo log seja no próximo minuto exato
    
    log_info(f"Espera de {minutes} minutos concluída.")


def extract_json_from_text(text):
    """
    Tenta extrair JSON de um texto, mesmo se houver texto adicional antes ou depois.
    Retorna None se não conseguir encontrar JSON válido.
    """
    log_info(f"JSON Text {text}")
    try:
        # Tenta analisar o texto diretamente como JSON
        return json.loads(text)
    except json.JSONDecodeError:
        # Se falhar, tenta encontrar delimitadores JSON
        json_start = text.find('{')
        json_end = text.rfind('}') + 1
        
        if json_start >= 0 and json_end > json_start:
            json_str = text[json_start:json_end]
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                return None
        return None


def is_valid_coin(coin_symbol):
    """
    Verifica se um símbolo de moeda parece válido
    """
    if not coin_symbol:
        return False
    
    # Verifica formato básico (letras maiúsculas, 2-10 caracteres)
    if not (2 <= len(coin_symbol) <= 10 and coin_symbol.isupper()):
        return False
    
    # Lista de moedas conhecidamente inválidas ou que devem ser evitadas
    invalid_coins = ['UPUSDT', 'DOWNUSDT', 'BEAR', 'BULL'] # Aumentar a lista depois
    for invalid in invalid_coins:
        if invalid in coin_symbol:
            return False
    
    return True


def create_trading_pair(coin, quote_currency='USDT'):
    """
    Cria um par de trading formatado corretamente
    """
    return f"{coin}{quote_currency}" #Sempre finaliza com USDT, pelo menos para a Binance


def _determine_precision_from_string(value_str):
    """
    Determina o número de casas decimais a partir de uma string representando um número.
    Ex: "0.001" -> 3, "1" -> 0, "0.100" -> 1 (considerando trailing zeros como não significativos para precisão mínima)
    """
    if '.' in value_str:
        # Remove zeros à direita após o ponto decimal para obter a precisão real
        decimal_part = value_str.split('.')[1].rstrip('0')
        return len(decimal_part)
    return 0
