"""
Cliente da API da Binance para o bot de trading
"""
from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceRequestException
import pandas as pd
import numpy as np
import time
import math 
import json

from config import config
from utils.helpers import log_info, log_error, log_trade, log_warning, _determine_precision_from_string # Adicionado log_warning e _determine_precision_from_string

# Variáveis globais
client = None
last_sold_coin = None
last_trade_time = 0


def initialize_client():
    """
    Inicializa o cliente da Binance
    """
    global client
    client = Client(config.BINANCEAPIKEY, config.BINANCESECRETKEY)
    # Testar conexão
    try:
        client.ping()
        log_info("Cliente Binance inicializado e conexão bem-sucedida (ping).")
    except Exception as e:
        log_error(f"Falha ao conectar com a Binance ao inicializar cliente: {e}")
        raise # Re-lança a exceção para que a inicialização do bot falhe
    return client

def get_client():
    return client


def ensure_binance_connection():
    """Garante que o cliente Binance está conectado. Tenta reconectar se necessário."""
    global client
    try:
        if client is None:
            log_warning("Cliente Binance não inicializado. Tentando inicializar...")
            initialize_client()
        else:
            client.ping()
        return True
    except Exception as e:
        log_error(f"Conexão com Binance perdida: {e}")
        log_info("Tentando reconectar à Binance...")
        try:
            initialize_client()
            return True
        except Exception as recon_e:
            log_error(f"Falha ao reconectar à Binance: {recon_e}")
            return False


def get_all_binance_coins():
    """
    Retorna uma lista de todas as moedas disponíveis na Binance que possuem par com USDT
    e têm volume suficiente para trading.
    """
    if not ensure_binance_connection():
        # Retorna lista padrão se não conseguir conectar
        default_coins = ['BTC', 'ETH', 'BNB', 'SOL', 'XRP', 'ADA', 'DOGE', 'SHIB', 'DOT', 'AVAX']
        return default_coins
    try:
        # Obter informações de preço para todos os pares
        tickers = client.get_ticker()
        
        # Filtrar apenas pares com USDT e com volume significativo
        usdt_pairs = []
        for ticker in tickers:
            symbol = ticker['symbol']
            if symbol.endswith('USDT') and \
               not symbol.endswith('UPUSDT') and \
               not symbol.endswith('DOWNUSDT') and \
               not "BEAR" in symbol and \
               not "BULL" in symbol: # Filtros adicionais
                try:
                    volume_24h = float(ticker['quoteVolume'])  # Volume em USDT
                    if volume_24h > config.MIN_VOLUME_FILTER:
                        coin = symbol.replace('USDT', '')
                        usdt_pairs.append(coin)
                except ValueError:
                    log_warning(f"Não foi possível converter quoteVolume para float para o ticker: {ticker['symbol']}")
                    continue
        
        log_info(f"Total de moedas negociáveis (pares USDT com volume > {config.MIN_VOLUME_FILTER}) na Binance: {len(usdt_pairs)}")
        if not usdt_pairs:
            log_warning("Nenhuma moeda encontrada que satisfaça os critérios de filtro. Verifique MIN_VOLUME_FILTER.")
        return usdt_pairs
    except Exception as e:
        log_error(f"Erro ao obter moedas da Binance: {e}")
        # Fallback para uma lista default de moedas populares
        default_coins = ['BTC', 'ETH', 'BNB', 'SOL', 'XRP', 'ADA', 'DOGE', 'SHIB', 'DOT', 'AVAX']
        log_warning(f"Usando lista de moedas padrão devido a erro: {default_coins}")
        return default_coins

def get_all_balances():
    """
    Obtém todos os saldos não-zero da conta.
    
    Returns:
        dict: Dicionário com saldos {símbolo: quantidade}
    """
    try:
        client = get_client()
        account = client.get_account()
        
        balances = {}
        for balance in account['balances']:
            free = float(balance['free'])
            locked = float(balance['locked'])
            total = free + locked
            
            # Ignora saldos muito pequenos (poeira)
            if total > 0.00001:
                balances[balance['asset']] = total
        
        return balances
    except Exception as e:
        log_error(f"Erro ao obter todos os saldos: {e}")
        return {}

def get_historical_data(coin_pair, interval=Client.KLINE_INTERVAL_1HOUR, lookback="3 days ago UTC"): # Lookback aumentado
    """
    Obtém dados históricos para um par de moedas.
    
    Args:
        coin_pair (str): Par de moedas (ex: 'BTCUSDT')
        interval (str): Intervalo de tempo (default: 1 hora)
        lookback (str): Período para olhar para trás (default: 3 dias)
    
    Returns:
        pd.DataFrame: DataFrame com dados históricos
    """
    if not ensure_binance_connection():
        return pd.DataFrame()
    try:
        klines = client.get_historical_klines(coin_pair, interval, lookback)
        
        if not klines:
            log_warning(f"Não foram retornados dados históricos (klines) para {coin_pair} com intervalo {interval} e lookback {lookback}.")
            return pd.DataFrame()

        # Criar DataFrame
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
        ])
        
        # Converter tipos
        numeric_columns = ['open', 'high', 'low', 'close', 'volume', 
                          'quote_asset_volume', 'number_of_trades', # number_of_trades também é numérico
                          'taker_buy_base_asset_volume', 
                          'taker_buy_quote_asset_volume']
        
        for col in numeric_columns:
            df[col] = pd.to_numeric(df[col])
        
        # Converter timestamps para datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df['close_time'] = pd.to_datetime(df['close_time'], unit='ms')
        
        # Definir timestamp como índice
        df.set_index('timestamp', inplace=True)
        
        return df
    except Exception as e:
        log_error(f"Erro ao obter dados históricos para {coin_pair}: {e}")
        return pd.DataFrame()


def get_trade_rules(coin_pair):
    """
    Retorna as regras relacionadas a LOT_SIZE (quantidade mínima, stepSize como string)
    e NOTIONAL (valor mínimo da ordem) para o par de moedas.
    """
    if not ensure_binance_connection():
        return None, None
    try:
        info = client.get_symbol_info(coin_pair)
    except Exception as e:
        log_error(f"Erro ao obter informações do símbolo {coin_pair}: {e}")
        return None, None

    lot_size_rules = {}
    min_notional = None

    if info and "filters" in info:
        for f in info['filters']:
            if f['filterType'] == 'LOT_SIZE':
                lot_size_rules = {
                    'minQty': float(f['minQty']),
                    'maxQty': float(f['maxQty']),
                    'stepSize': f['stepSize']  # Manter como string para precisão
                }
            if f['filterType'] == 'NOTIONAL': # Algumas APIs usam NOTIONAL, outras MIN_NOTIONAL
                 min_notional = float(f.get('minNotional', f.get('notional', 0))) # Prioriza minNotional
            elif f['filterType'] == 'MIN_NOTIONAL': # Garantir que MIN_NOTIONAL seja coberto
                 min_notional = float(f['minNotional'])


    if not lot_size_rules:
        log_warning(f"Regras de LOT_SIZE não encontradas para {coin_pair}.")
    if min_notional is None:
        log_warning(f"Regra de MIN_NOTIONAL não encontrada para {coin_pair}. Usando default 5 USDT.")
        min_notional = 5.0 # Um valor de fallback comum, mas idealmente deveria vir da API.

    return lot_size_rules, min_notional


def _adjust_quantity_to_step_size(quantity, step_size_str):
    """Ajusta a quantidade PARA BAIXO para o múltiplo mais próximo do step_size e formata com a precisão correta."""
    step_size = float(step_size_str)
    if step_size == 0: 
        log_warning("Step size é 0, retornando quantidade original.")
        return quantity

    precision = _determine_precision_from_string(step_size_str)
    
    # Arredonda a quantidade PARA BAIXO para o múltiplo mais próximo do step_size
    # Ex: quantity=10.123, step_size=0.01 -> floor(1012.3)*0.01 = 1012*0.01 = 10.12
    # Ex: quantity=10.123, step_size=0.1 -> floor(101.23)*0.1 = 101*0.1 = 10.1
    adjusted_qty = math.floor(quantity / step_size) * step_size
    
    # Formata para a precisão correta para evitar problemas de representação de float
    return float(f"{adjusted_qty:.{precision}f}")


def get_current_price(symbol):
    """Obtém o preço atual de um símbolo"""
    if not ensure_binance_connection():
        return None
    try:
        ticker = client.get_symbol_ticker(symbol=symbol)
        return float(ticker['price'])
    except Exception as e:
        log_error(f"Erro ao obter preço atual para {symbol}: {e}")
        return None


def get_account_balance():
    """Retorna o saldo da conta em todas as moedas"""
    if not ensure_binance_connection():
        return []
    try:
        return client.get_account()['balances']
    except Exception as e:
        log_error(f"Erro ao obter balanço da conta: {e}")
        return []


def get_balance(coin):
    """Retorna o saldo livre (free) de uma determinada moeda."""
    if not ensure_binance_connection():
        return 0.0
    try:
        balance_info = client.get_asset_balance(asset=coin)
        if balance_info is None or 'free' not in balance_info:
            log_warning(f"Não foi possível obter saldo para {coin} ou 'free' não está presente.")
            return 0.0
        return float(balance_info['free'])
    except Exception as e:
        log_error(f"Erro ao obter saldo para {coin}: {e}")
        return 0.0


def get_portfolio_value():
    """
    Calcula e retorna o valor total da carteira em USDT.
    Considera todas as moedas disponíveis e também o saldo em USDT.
    """
    total_value_usdt = 0.0
    assets = get_account_balance() # Usa a função robustecida
    
    log_info("\n=== PORTFOLIO ATUAL DETALHADO ===")
    
    # Adiciona USDT primeiro
    usdt_balance = get_balance('USDT')
    if usdt_balance > 0:
        log_info(f"USDT: {usdt_balance:.2f} USDT")
        total_value_usdt += usdt_balance
            
    for asset in assets:
        symbol = asset['asset']
        # 'free' e 'locked' são strings, precisam ser convertidas
        free_amount = float(asset['free'])
        locked_amount = float(asset['locked'])
        total_amount = free_amount + locked_amount
        
        # Ignora USDT (já contabilizado) e ativos com saldo zero ou muito pequeno
        if symbol == 'USDT' or total_amount <= 0.00000001: # Tolerância para poeira
            continue
            
        # Para outras moedas, converte para USDT
        pair_symbol = f"{symbol}USDT"
        current_price = get_current_price(pair_symbol)
        
        if current_price is not None and current_price > 0:
            asset_value_usdt = total_amount * current_price
            if asset_value_usdt > 1.0: # Log apenas valores significativos
                 log_info(f"{symbol}: {total_amount:.8f} (Valor Estimado: {asset_value_usdt:.2f} USDT @ {current_price:.4f} USDT)")
            total_value_usdt += asset_value_usdt
        else:
            if total_amount > 0.00000001: # Log apenas se houver alguma quantidade
                log_info(f"{symbol}: {total_amount:.8f} (Não foi possível obter preço de conversão para USDT ou preço é zero)")
    
    log_info(f"------------------------------------")
    log_info(f"VALOR TOTAL ESTIMADO DA CARTEIRA: {total_value_usdt:.2f} USDT")
    log_info("====================================")
    return total_value_usdt


def buy_coin(coin_pair, available_usdt_to_spend):
    """
    Executa ordem de compra (market) para 'coin_pair' usando available_usdt_to_spend,
    respeitando LOT_SIZE e MIN_NOTIONAL.
    Retorna o objeto da ordem da Binance com informações de 'fills'.
    """
    if not ensure_binance_connection():
        return None
    log_info(f"\nTentando comprar {coin_pair} com aproximadamente {available_usdt_to_spend:.2f} USDT.")
    
    current_price = get_current_price(coin_pair)
    if current_price is None or current_price <= 0:
        log_error(f"Preço inválido ou zero para {coin_pair}. Abortando compra.")
        return None

    lot_size_rules, min_notional_value = get_trade_rules(coin_pair)

    if not lot_size_rules or min_notional_value is None:
        log_error(f"Não foi possível obter regras de negociação para {coin_pair}. Abortando compra.")
        return None

    # Considerar uma pequena margem para slippage e taxas ao calcular a quantidade
    # A Binance geralmente deduz a taxa da moeda comprada ou da moeda cotada (USDT)
    # Se deduzir de USDT, o available_usdt_to_spend já é o limite.
    # Se deduzir da moeda comprada, precisamos comprar um pouco menos para ter USDT para a taxa.
    # A API `order_market_buy` com `quoteOrderQty` (quanto USDT gastar) lida com isso.
    # No entanto, para usar `quantity`, precisamos calcular.
    # Vamos assumir que a taxa é deduzida do USDT, ou seja, available_usdt_to_spend é o máximo.
    # Estimativa da quantidade base (sem considerar taxas ainda, pois `quoteOrderQty` seria melhor)
    # Se usar `quantity`, a taxa será paga pela moeda base ou cotada, dependendo da config.
    # Para simplificar com `quantity`, descontamos a taxa do USDT disponível.
    
    # A Binance permite especificar `quoteOrderQty` para ordens MARKET BUY,
    # o que significa "gastar X USDT". Isso simplifica o cálculo de taxas.
    # Se `quoteOrderQty` for usado, a quantidade (`quantity`) não é especificada.
    # Vamos verificar se a biblioteca python-binance suporta bem.
    # A documentação de Client.order_market_buy sugere que `quantity` é obrigatório.
    # Portanto, precisamos calcular a `quantity`.

    usdt_for_quantity_calc = available_usdt_to_spend * (1 - config.BINANCE_FEE_PERCENT) # Desconta taxa estimada
    
    target_quantity = usdt_for_quantity_calc / current_price
    
    step_size_str = lot_size_rules.get('stepSize', "1") # Default para "1" se não encontrado
    min_qty_val = lot_size_rules.get('minQty', 0.0)

    coin_quantity_adjusted = _adjust_quantity_to_step_size(target_quantity, step_size_str)

    if coin_quantity_adjusted < min_qty_val:
        log_error(f"Quantidade calculada {coin_quantity_adjusted:.8f} está abaixo da mínima permitida {min_qty_val:.8f} para {coin_pair} após ajuste de stepSize. Saldo USDT: {available_usdt_to_spend:.2f}, Preço: {current_price:.6f}")
        return None

    order_value_estimated = coin_quantity_adjusted * current_price
    if order_value_estimated < min_notional_value:
        log_error(f"Valor estimado da ordem {order_value_estimated:.2f} USDT está abaixo do mínimo nocional {min_notional_value:.2f} USDT para {coin_pair}.")
        return None
    
    if coin_quantity_adjusted <= 0:
        log_error(f"Quantidade ajustada para compra é zero ou negativa para {coin_pair}. Abortando.")
        return None

    log_info(f"Calculada quantidade ajustada para compra de {coin_pair}: {coin_quantity_adjusted:.8f}")

    try:
        log_info(f"Enviando ordem MARKET BUY: {coin_quantity_adjusted:.8f} {coin_pair.replace('USDT','')}...")
        # Usando TESTE para evitar ordens reais durante o desenvolvimento.
        # order = client.create_test_order(symbol=coin_pair, side=Client.SIDE_BUY, type=Client.ORDER_TYPE_MARKET, quantity=coin_quantity_adjusted)
        # PARA ORDENS REAIS:
        order = client.order_market_buy(symbol=coin_pair, quantity=coin_quantity_adjusted)
        
        log_info(f"Ordem de compra para {coin_pair} enviada. ID: {order.get('orderId')}")
        # Nota: `order_market_buy` já retorna a ordem preenchida para MARKET.
        # A estrutura da 'order' pode variar um pouco (ex: se tem 'fills' ou não diretamente).
        # Vamos assumir que 'fills' está presente e contém os detalhes da execução.
        
        # Calcular preço médio e taxas dos fills
        # Este cálculo será feito em strategy/trading.py onde a ordem é recebida
        return order # Retorna o objeto da ordem completo
        
    except (BinanceAPIException, BinanceRequestException) as e:
        log_error(f"Erro da API Binance ao comprar {coin_pair}: {e}")
        return None
    except Exception as e:
        log_error(f"Erro ao colocar ordem de compra para {coin_pair} (Qtd: {coin_quantity_adjusted}): {e}")
        if hasattr(e, 'code') and hasattr(e, 'message'):
            log_error(f"Binance API Error Code: {e.code}, Message: {e.message}")
        return None


def sell_coin(coin_pair, quantity_to_sell):
    """
    Executa ordem de venda (market) para 'coin_pair' na quantidade informada,
    respeitando LOT_SIZE e MIN_NOTIONAL.
    """
    global last_sold_coin, last_trade_time

    if not ensure_binance_connection():
        return None

    log_info(f"\nTentando vender {quantity_to_sell:.8f} de {coin_pair}.")
    
    current_price = get_current_price(coin_pair)
    if current_price is None or current_price <= 0:
        log_error(f"Preço inválido ou zero para {coin_pair}. Abortando venda.")
        return None

    lot_size_rules, min_notional_value = get_trade_rules(coin_pair)

    if not lot_size_rules or min_notional_value is None:
        log_error(f"Não foi possível obter regras de negociação para {coin_pair}. Abortando venda.")
        return None

    step_size_str = lot_size_rules.get('stepSize', "1")
    min_qty_val = lot_size_rules.get('minQty', 0.0)

    # Ajusta a quantidade PARA BAIXO para o stepSize. Se a quantidade já for um múltiplo, não muda.
    coin_quantity_adjusted = _adjust_quantity_to_step_size(quantity_to_sell, step_size_str)

    if coin_quantity_adjusted < min_qty_val:
        log_warning(f"Quantidade ajustada para venda {coin_quantity_adjusted:.8f} de {coin_pair} é menor que a quantidade mínima ({min_qty_val:.8f}). Verificando se a quantidade original {quantity_to_sell:.8f} é suficiente para o mínimo nocional.")
        # Se a quantidade ajustada for zero, mas a original não, e a original atender ao min_notional, pode ser um problema de poeira.
        # Neste caso, se a quantidade ajustada for zero, provavelmente não vale a pena vender.
        if coin_quantity_adjusted <= 0: # Se ajustado para zero, não pode vender
             log_error(f"Quantidade ajustada para venda de {coin_pair} é zero após stepSize. Quantidade original: {quantity_to_sell:.8f}. Abortando venda.")
             return None

    order_value_estimated = coin_quantity_adjusted * current_price
    if order_value_estimated < min_notional_value:
        log_error(f"Valor estimado da ordem de venda {order_value_estimated:.2f} USDT para {coin_quantity_adjusted:.8f} {coin_pair} está abaixo do mínimo nocional {min_notional_value:.2f} USDT. Abortando venda.")
        return None

    if coin_quantity_adjusted <= 0:
        log_error(f"Quantidade ajustada para venda é zero ou negativa para {coin_pair}. Abortando.")
        return None
        
    log_info(f"Calculada quantidade ajustada para venda de {coin_pair}: {coin_quantity_adjusted:.8f}")

    try:
        log_info(f"Enviando ordem MARKET SELL: {coin_quantity_adjusted:.8f} {coin_pair.replace('USDT','')}...")
        # Usando TESTE para evitar ordens reais durante o desenvolvimento. Remova para ordens reais.
        # order = client.create_test_order(symbol=coin_pair, side=Client.SIDE_SELL, type=Client.ORDER_TYPE_MARKET, quantity=coin_quantity_adjusted)
        # PARA ORDENS REAIS:
        order = client.order_market_sell(symbol=coin_pair, quantity=coin_quantity_adjusted)

        log_info(f"Ordem de venda para {coin_pair} enviada. ID: {order.get('orderId')}")
        
        # Atualiza variáveis globais APÓS sucesso da ordem
        last_sold_coin = coin_pair
        last_trade_time = time.time()
        
        # Calcular e logar taxas e valor líquido
        # Este cálculo será feito em strategy/trading.py onde a ordem é recebida
        return order # Retorna o objeto da ordem completo

    except (BinanceAPIException, BinanceRequestException) as e:
        log_error(f"Erro da API Binance ao vender {coin_pair}: {e}")
        return None
    except Exception as e:
        log_error(f"Erro ao colocar ordem de venda para {coin_pair} (Qtd: {coin_quantity_adjusted}): {e}")
        if hasattr(e, 'code') and hasattr(e, 'message'):
            log_error(f"Binance API Error Code: {e.code}, Message: {e.message}")
        return None


def sell_all_coins():
    """
    Vende todo o saldo livre das moedas na carteira que tenham par com USDT e valor suficiente.
    Retorna o total de USDT obtido (bruto, antes de taxas da operação de venda).
    """
    if not ensure_binance_connection():
        return 0.0

    usdt_obtained_gross = 0
    sold_any = False

    account_balances = get_account_balance()
    if not account_balances:
        log_info("Nenhum saldo encontrado na conta para verificar/vender.")
        return 0.0

    log_info("\nVerificando moedas para vender (sell_all_coins)...")
    for balance_item in account_balances:
        coin_symbol = balance_item['asset']
        coin_free_balance = float(balance_item['free'])
        
        if coin_symbol == 'USDT' or coin_free_balance <= 0:
            continue
            
        trading_pair = f"{coin_symbol}USDT"
        
        try:
            # Verifica se o par existe e tem preço
            current_price = get_current_price(trading_pair)
            if current_price is None or current_price <= 0:
                log_info(f"Pulando {coin_symbol}: não foi possível obter preço válido para {trading_pair}.")
                continue

            # Verifica se o valor total da moeda é significativo para venda
            total_value_of_coin_usdt = coin_free_balance * current_price
            
            # Obter min_notional para o par
            _, min_notional_for_pair = get_trade_rules(trading_pair)
            if min_notional_for_pair is None: 
                log_warning(f"Não foi possível obter min_notional para {trading_pair}, usando default 5 USDT para verificação.")
                min_notional_for_pair = 5.0 # Fallback

            if total_value_of_coin_usdt < min_notional_for_pair:
                log_info(f"Pulando venda de {coin_symbol} ({coin_free_balance:.8f}): valor total ({total_value_of_coin_usdt:.2f} USDT) abaixo do mínimo nocional ({min_notional_for_pair:.2f} USDT).")
                continue
                
            log_info(f"Tentando vender {coin_free_balance:.8f} de {coin_symbol} (par {trading_pair})...")
            sell_order_response = sell_coin(trading_pair, coin_free_balance) # sell_coin já lida com stepSize e logs
            
            if sell_order_response and 'fills' in sell_order_response and sell_order_response['fills']:
                sold_any = True
                for fill in sell_order_response['fills']:
                    price = float(fill['price'])
                    qty = float(fill['qty'])
                    usdt_obtained_gross += price * qty
                log_info(f"Venda de {coin_symbol} bem-sucedida. USDT Bruto obtido nesta venda: {sum(float(f['price'])*float(f['qty']) for f in sell_order_response['fills']):.2f}")
            elif sell_order_response: # Caso não tenha 'fills' mas a ordem foi aceita
                sold_any = True
                # Estimativa se não houver fills (menos preciso)
                executed_qty = float(sell_order_response.get('executedQty', 0))
                cummulative_quote_qty = float(sell_order_response.get('cummulativeQuoteQty', 0))
                if executed_qty > 0 and cummulative_quote_qty > 0:
                     usdt_obtained_gross += cummulative_quote_qty
                     log_info(f"Venda de {coin_symbol} (estimativa) bem-sucedida. USDT Bruto obtido: {cummulative_quote_qty:.2f}")
                else:
                    log_warning(f"Venda de {coin_symbol} pode ter ocorrido, mas sem detalhes de 'fills' ou 'cummulativeQuoteQty'. Ordem: {sell_order_response}")
            else:
                log_error(f"Falha ao vender {coin_symbol}.")

        except Exception as e:
            log_error(f"Erro ao processar/vender {coin_symbol} em sell_all_coins: {e}")
    
    if sold_any:
        log_info(f"Processo de sell_all_coins concluído. Total USDT bruto obtido (estimado): {usdt_obtained_gross:.2f}")
    else:
        log_info("Nenhuma moeda foi vendida durante sell_all_coins.")
    return usdt_obtained_gross

# Adicionar estas funções em api/binance_client.py

def get_24h_ticker(symbol):
    """
    Obtém dados de ticker das últimas 24h incluindo volume.
    
    Args:
        symbol (str): Par de trading (ex: 'BTCUSDT')
        
    Returns:
        dict: Dados do ticker ou None em caso de erro
    """
    try:
        ticker = client.get_ticker(symbol=symbol)
        return ticker
    except Exception as e:
        log_error(f"Erro ao obter ticker 24h para {symbol}: {e}")
        return None


def get_24h_volume(symbol):
    """
    Obtém o volume de trading das últimas 24 horas.
    
    Args:
        symbol (str): Par de trading (ex: 'BTCUSDT')
        
    Returns:
        float: Volume em USDT ou None em caso de erro
    """
    try:
        ticker = get_24h_ticker(symbol)
        if ticker:
            # Volume em quote asset (USDT)
            volume_usdt = float(ticker.get('quoteVolume', 0))
            log_info(f"Volume 24h para {symbol}: {volume_usdt:,.2f} USDT")
            return volume_usdt
        return None
    except Exception as e:
        log_error(f"Erro ao obter volume 24h para {symbol}: {e}")
        return None


def get_average_volume(symbol, days=7, interval='1d'):
    """
    Calcula o volume médio dos últimos X dias.
    
    Args:
        symbol (str): Par de trading (ex: 'BTCUSDT')
        days (int): Número de dias para calcular a média
        interval (str): Intervalo dos candles ('1d' para diário)
        
    Returns:
        float: Volume médio em USDT ou None em caso de erro
    """
    try:
        # Busca dados históricos
        klines = client.get_historical_klines(
            symbol, 
            interval,
            f"{days + 1} days ago UTC"
        )
        
        if not klines:
            log_error(f"Sem dados históricos de volume para {symbol}")
            return None
        
        # Extrai volumes (índice 7 é o volume em quote asset)
        volumes = [float(k[7]) for k in klines[:-1]]  # Remove o dia atual incompleto
        
        if volumes:
            avg_volume = sum(volumes) / len(volumes)
            log_info(f"Volume médio {days}d para {symbol}: {avg_volume:,.2f} USDT")
            return avg_volume
        
        return None
    except Exception as e:
        log_error(f"Erro ao calcular volume médio para {symbol}: {e}")
        return None


def get_volume_ratio(symbol, days=7):
    """
    Calcula a razão entre o volume atual e o volume médio.
    
    Args:
        symbol (str): Par de trading (ex: 'BTCUSDT')
        days (int): Dias para calcular a média
        
    Returns:
        float: Razão volume_atual/volume_médio ou None
    """
    try:
        current_volume = get_24h_volume(symbol)
        avg_volume = get_average_volume(symbol, days)
        
        if current_volume and avg_volume and avg_volume > 0:
            ratio = current_volume / avg_volume
            
            # Log informativo sobre o volume
            if ratio > 2.0:
                log_info(f">>> VOLUME ALTO: {symbol} com {ratio:.2f}x a média ({days}d)")
            elif ratio > 1.5:
                log_info(f"Volume elevado: {symbol} com {ratio:.2f}x a média")
            elif ratio < 0.5:
                log_info(f"Volume baixo: {symbol} com {ratio:.2f}x a média")
            
            return ratio
        
        return None
    except Exception as e:
        log_error(f"Erro ao calcular ratio de volume para {symbol}: {e}")
        return None


def get_volume_analysis(symbol):
    """
    Análise completa de volume para um símbolo.
    
    Args:
        symbol (str): Par de trading (ex: 'BTCUSDT')
        
    Returns:
        dict: Análise completa de volume
    """
    try:
        ticker = get_24h_ticker(symbol)
        if not ticker:
            return None
        
        # Volume 24h
        volume_24h = float(ticker.get('quoteVolume', 0))
        
        # Variação de preço 24h
        price_change_percent = float(ticker.get('priceChangePercent', 0))
        
        # Volume médio 7 dias
        avg_volume_7d = get_average_volume(symbol, 7)
        
        # Volume médio 3 dias (mais recente)
        avg_volume_3d = get_average_volume(symbol, 3)
        
        # Análise
        analysis = {
            'volume_24h': volume_24h,
            'avg_volume_7d': avg_volume_7d,
            'avg_volume_3d': avg_volume_3d,
            'price_change_24h': price_change_percent,
            'volume_score': 0
        }
        
        # Calcula score de volume
        if avg_volume_7d and avg_volume_7d > 0:
            ratio_7d = volume_24h / avg_volume_7d
            
            # Score baseado no ratio e direção do preço
            if ratio_7d > 2.0 and price_change_percent > 0:
                analysis['volume_score'] = 100  # Volume alto com preço subindo = muito bom
                analysis['volume_signal'] = 'FORTE_COMPRA'
            elif ratio_7d > 1.5:
                analysis['volume_score'] = 70
                analysis['volume_signal'] = 'COMPRA'
            elif ratio_7d > 1.0:
                analysis['volume_score'] = 50
                analysis['volume_signal'] = 'NEUTRO'
            else:
                analysis['volume_score'] = 30
                analysis['volume_signal'] = 'FRACO'
            
            analysis['volume_ratio_7d'] = ratio_7d
        
        # Tendência de volume (3d vs 7d)
        if avg_volume_3d and avg_volume_7d and avg_volume_7d > 0:
            trend_ratio = avg_volume_3d / avg_volume_7d
            if trend_ratio > 1.2:
                analysis['volume_trend'] = 'CRESCENTE'
            elif trend_ratio < 0.8:
                analysis['volume_trend'] = 'DECRESCENTE'
            else:
                analysis['volume_trend'] = 'ESTÁVEL'
        
        return analysis
        
    except Exception as e:
        log_error(f"Erro na análise de volume para {symbol}: {e}")
        return None


def check_volume_breakout(symbol, threshold=2.0):
    """
    Verifica se há um breakout de volume.
    
    Args:
        symbol (str): Par de trading
        threshold (float): Multiplicador para considerar breakout
        
    Returns:
        bool: True se houver breakout de volume
    """
    try:
        ratio = get_volume_ratio(symbol)
        if ratio and ratio > threshold:
            log_info(f">>> BREAKOUT DE VOLUME detectado em {symbol}: {ratio:.2f}x a média!")
            return True
        return False
    except Exception as e:
        log_error(f"Erro ao verificar breakout de volume: {e}")
        return False