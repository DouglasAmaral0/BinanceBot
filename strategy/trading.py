"""
Implementação das estratégias e lógica de trading
"""
from config import config
import os
from utils.helpers import (
    log_info,
    log_error,
    log_trade,
    log_warning,
    log_performance,
)
from datetime import datetime
from api.binance_client import get_current_price, get_balance, buy_coin, sell_all_coins, get_portfolio_value, sell_coin, get_all_balances
from analysis.technical import dynamic_stop_loss_take_profit
from strategy.selection import choose_best_coin
import json
import time

# Variáveis globais para o estado da negociação
current_coin = None  # Par de moedas atual (ex: 'BTCUSDT')
current_coin_base_asset = None # Ex: 'BTC'
current_coin_purchase_price = 0.0  # Preço de compra REAL da moeda atual
current_coin_quantity_bought = 0.0 # Quantidade REAL comprada
current_coin_total_cost_usdt = 0.0 # Custo total em USDT incluindo taxas da compra
position_open_time = None          # Timestamp de quando a posição foi aberta
highest_price_reached = 0.0 
trades_today = 0
last_trade_date = None
last_trade_timestamp = 0

stop_loss_pct = config.DEFAULT_STOP_LOSS_PCT
take_profit_pct = config.DEFAULT_TAKE_PROFIT_PCT

# Para rastreamento de P&L do ciclo de trade
usdt_balance_before_trade = 0.0

# Controle de performance diária
daily_profit_loss = 0.0
current_day = datetime.utcnow().date()

def can_open_new_trade():
    """
    Verifica se é permitido abrir um novo trade baseado em:
    1. Limite de trades por dia
    2. Tempo mínimo entre trades
    """
    global trades_today, last_trade_date, last_trade_timestamp
    
    current_time = time.time()
    today = datetime.now().date()
    
    # Reset contador se mudou o dia
    if last_trade_date != today:
        trades_today = 0
        last_trade_date = today
        log_info(f"Novo dia: contador de trades resetado")
    
    # Verifica limite diário
    if trades_today >= config.MAX_TRADES_PER_DAY:
        log_warning(f"Limite diário de {config.MAX_TRADES_PER_DAY} trades atingido")
        return False
    
    # Verifica tempo mínimo entre trades
    time_since_last = current_time - last_trade_timestamp
    if last_trade_timestamp > 0 and time_since_last < config.MIN_TIME_BETWEEN_TRADES:
        remaining = (config.MIN_TIME_BETWEEN_TRADES - time_since_last) / 3600
        log_info(f"Tempo mínimo entre trades não atingido. Aguarde {remaining:.1f}h")
        return False
    
    return True

def save_bot_state():
    """
    Salva o estado atual do bot em um arquivo JSON.
    Chame esta função após cada ciclo de trading.
    """
    try:
        
        # Obtém informações globais se disponíveis
        global current_coin, current_coin_purchase_price, stop_loss_pct, take_profit_pct
        
        state = {
            'total_usdt': get_portfolio_value(),
            'balances': get_all_balances(),
            'last_update': datetime.now().isoformat(),
            'trading_info': {
                'current_coin': current_coin if 'current_coin' in globals() else None,
                'purchase_price': current_coin_purchase_price if 'current_coin_purchase_price' in globals() else 0,
                'stop_loss': stop_loss_pct if 'stop_loss_pct' in globals() else config.DEFAULT_STOP_LOSS_PCT,
                'take_profit': take_profit_pct if 'take_profit_pct' in globals() else config.DEFAULT_TAKE_PROFIT_PCT
            },
            'bot_config': {
                'interval_minutes': config.DEFAULT_INTERVAL,
                'max_coins_to_analyze': config.MAX_COINS_TO_ANALYZE,
                'percent_portfolio_per_trade': config.PERCENT_PORTFOLIO_PER_TRADE
            }
        }

        state_dir = '/home/pi/crypto_bot'
        if not os.path.exists(state_dir):
            os.makedirs(state_dir)
        
        filepath = os.path.join(state_dir, 'bot_state.json')
        
        with open(filepath, 'w') as f:
            json.dump(state, f, indent=2)
        
        log_info(f"Estado do bot salvo em {filepath}")
        
    except Exception as e:
        log_error(f"Erro ao salvar estado do bot: {e}")


def _calculate_order_details(order_response, default_fee_percent=config.BINANCE_FEE_PERCENT):
    """Calcula preço médio, quantidade total, custo/receita total e taxas dos fills de uma ordem."""
    total_quantity = 0
    total_quote_qty = 0 # USDT gasto (compra) ou recebido (venda)
    total_commission = 0
    commission_asset = ""

    if order_response and 'fills' in order_response and order_response['fills']:
        for fill in order_response['fills']:
            total_quantity += float(fill['qty'])
            total_quote_qty += float(fill['price']) * float(fill['qty']) # Custo bruto por fill
            total_commission += float(fill['commission'])
            commission_asset = fill['commissionAsset']
        
        if total_quantity > 0:
            avg_price = total_quote_qty / total_quantity
            
            # Converter comissão para USDT se necessário
            fees_paid_usdt = 0
            if commission_asset == 'USDT':
                fees_paid_usdt = total_commission
            elif commission_asset: # Se for na moeda base ou outra
                comm_asset_price = get_current_price(f"{commission_asset}USDT")
                if comm_asset_price and comm_asset_price > 0:
                    fees_paid_usdt = total_commission * comm_asset_price
                else: # Estimativa se não conseguir preço da comissão
                    fees_paid_usdt = total_quote_qty * default_fee_percent 
                    log_warning(f"Não foi possível obter preço para {commission_asset}USDT. Taxa estimada como {default_fee_percent*100}%.")
            else: # Fallback extremo
                 fees_paid_usdt = total_quote_qty * default_fee_percent
                 log_warning(f"Ativo da comissão não especificado. Taxa estimada como {default_fee_percent*100}%.")

            return avg_price, total_quantity, total_quote_qty, fees_paid_usdt
    
    # Fallback se 'fills' não estiver disponível mas a ordem principal tiver os dados agregados
    if order_response:
        executed_qty_str = order_response.get('executedQty', '0')
        cummulative_quote_qty_str = order_response.get('cummulativeQuoteQty', '0')
        
        executed_qty = float(executed_qty_str)
        cummulative_quote_qty = float(cummulative_quote_qty_str)

        if executed_qty > 0:
            avg_price = cummulative_quote_qty / executed_qty
            # Taxas não são explicitamente detalhadas neste nível de resposta, estimar.
            fees_paid_usdt = cummulative_quote_qty * default_fee_percent
            log_warning(f"Usando dados agregados da ordem (sem 'fills') para calcular detalhes. Taxas estimadas.")
            return avg_price, executed_qty, cummulative_quote_qty, fees_paid_usdt

    log_error("Não foi possível determinar detalhes da execução da ordem (sem 'fills' ou dados agregados).")
    return 0, 0, 0, 0


def reset_daily_performance():
    """Reseta o acompanhamento de lucro/prejuízo diário"""
    global daily_profit_loss, current_day
    daily_profit_loss = 0.0
    current_day = datetime.utcnow().date()
    log_info("Performance diária reiniciada")


def update_daily_profit(amount):
    """Atualiza o acumulado diário e loga"""
    global daily_profit_loss
    daily_profit_loss += amount
    log_performance("Lucro/Prejuízo do dia", daily_profit_loss)


def check_daily_loss_limit():
    """Verifica se o limite de perda diária foi atingido"""
    global current_day
    today = datetime.utcnow().date()
    if today != current_day:
        reset_daily_performance()
    if daily_profit_loss <= -config.MAX_DAILY_LOSS_USDT:
        log_warning(
            f"Limite diário de perda atingido ({daily_profit_loss:.2f} USDT). Operações serão pausadas."
        )
        return True
    return False


def check_stop_loss_and_take_profit(coin_pair_to_check):
    """
    Verifica se o preço atual atingiu os níveis de stop loss ou take profit.
    
    Args:
        coin_pair_to_check (str): Par de moedas atual
        
    Returns:
        str or None: "STOP_LOSS", "TAKE_PROFIT" se acionado, ou None
    """
    global current_coin_purchase_price # Usar o preço real de compra

    if current_coin_purchase_price == 0: # Não comprou nada ainda ou erro
        log_warning("Verificação de SL/TP chamada, mas current_coin_purchase_price é 0.")
        return None
        
    actual_market_price = get_current_price(coin_pair_to_check)
    if actual_market_price is None:
        log_error(f"Não foi possível obter o preço de mercado atual para {coin_pair_to_check} ao verificar SL/TP.")
        return None

    sl_price = current_coin_purchase_price * (1 - stop_loss_pct)
    tp_price = current_coin_purchase_price * (1 + take_profit_pct)
    
    percentage_change = ((actual_market_price - current_coin_purchase_price) / current_coin_purchase_price * 100)

    log_info(f"Status para {coin_pair_to_check}: Preço Compra: {current_coin_purchase_price:.6f}, Atual: {actual_market_price:.6f} (Variação: {percentage_change:.2f}%)")
    log_info(f"SL: {stop_loss_pct*100:.2f}% (Ativará em <= {sl_price:.6f}), TP: {take_profit_pct*100:.2f}% (Ativará em >= {tp_price:.6f})")

    if actual_market_price <= sl_price:
        log_info(f"!!! ATIVANDO STOP LOSS para {coin_pair_to_check} !!!")
        log_info(f"Preço atual: {actual_market_price:.6f}, Preço de compra: {current_coin_purchase_price:.6f}")
        log_info(f"Queda de {abs(percentage_change):.2f}%, Stop Loss em: -{stop_loss_pct*100:.2f}%")
        return "STOP_LOSS"
    
    elif actual_market_price >= tp_price:
        log_info(f"!!! ATIVANDO TAKE PROFIT para {coin_pair_to_check} !!!")
        log_info(f"Preço atual: {actual_market_price:.6f}, Preço de compra: {current_coin_purchase_price:.6f}")
        log_info(f"Ganho de {percentage_change:.2f}%, Take Profit em: +{take_profit_pct*100:.2f}%")
        return "TAKE_PROFIT"
    
    return None


def initialize_trade(coin_pair_to_buy):
    """
    Inicializa uma nova operação de compra para o par de moedas.
    
    Args:
        coin_pair_to_buy (str): Par de moedas a ser comprado
        
    Returns:
        bool: True se a compra foi bem-sucedida, False caso contrário
    """
    global current_coin, current_coin_base_asset, current_coin_purchase_price, current_coin_quantity_bought, current_coin_total_cost_usdt
    global stop_loss_pct, take_profit_pct
    global usdt_balance_before_trade

    log_info(f"\n--- INICIALIZANDO TRADE PARA {coin_pair_to_buy} ---")
    
    # Configura stop loss e take profit dinâmicos
    current_stop_loss_pct, current_take_profit_pct = dynamic_stop_loss_take_profit(
        coin_pair_to_buy, 
        config.DEFAULT_STOP_LOSS_PCT, 
        config.DEFAULT_TAKE_PROFIT_PCT
    )
    stop_loss_pct = current_stop_loss_pct # Atualiza globais
    take_profit_pct = current_take_profit_pct
    
    # Obtém saldo em USDT
    usdt_balance = get_balance('USDT')
    if usdt_balance < config.MIN_USDT_FOR_TRADE: # Usar um valor configurável
        log_error(f"Saldo USDT ({usdt_balance:.2f}) insuficiente. Mínimo necessário: {config.MIN_USDT_FOR_TRADE} USDT")
        return False
    
    portfolio_value = get_portfolio_value()
    usdt_to_invest = portfolio_value * config.PERCENT_PORTFOLIO_PER_TRADE
    usdt_to_invest = min(usdt_to_invest, usdt_balance)
    if usdt_to_invest < config.MIN_USDT_FOR_TRADE:
        log_error(
            f"Valor a investir ({usdt_to_invest:.2f}) é menor que o mínimo de {config.MIN_USDT_FOR_TRADE} USDT."
        )
        return False

    usdt_balance_before_trade = get_balance('USDT') # Registra saldo USDT ANTES da compra
    log_info(f"Saldo USDT antes da compra: {usdt_balance_before_trade:.2f} USDT.")
    log_info(f"Iniciando compra de {coin_pair_to_buy} com aproximadamente {usdt_to_invest:.2f} USDT...")
    
    buy_order_response = buy_coin(coin_pair_to_buy, usdt_to_invest)
    
    if buy_order_response:
        avg_price, total_qty, gross_cost_usdt, fees_paid_usdt_buy = _calculate_order_details(buy_order_response)

        if avg_price > 0 and total_qty > 0:
            current_coin = coin_pair_to_buy
            current_coin_base_asset = coin_pair_to_buy.replace('USDT','')
            current_coin_purchase_price = avg_price
            current_coin_quantity_bought = total_qty
            current_coin_total_cost_usdt = gross_cost_usdt + fees_paid_usdt_buy # Custo real incluindo taxas

            log_trade("BUY", current_coin, current_coin_quantity_bought, current_coin_purchase_price, 
                      gross_cost_usdt, fees_paid_usdt_buy, current_coin_total_cost_usdt)
            log_info(f"Stop Loss definido em: {stop_loss_pct*100:.2f}%, Take Profit em: {take_profit_pct*100:.2f}%")
            
            log_info("Valor da carteira APÓS a compra:")
            get_portfolio_value() # Log do portfólio após a compra
            save_bot_state() 
            return True
        else:
            log_error(f"Falha ao processar detalhes da ordem de compra para {coin_pair_to_buy}. Resposta da ordem: {buy_order_response}")
            return False
    else:
        log_error(f"Falha na execução da ordem de compra para {coin_pair_to_buy}.")
        return False
    
def check_position_timeout(coin_pair_to_check):
    """
    Verifica se a posição excedeu o tempo máximo de holding.
    
    Args:
        coin_pair_to_check (str): Par de moedas atual
        
    Returns:
        str or None: "TIMEOUT_SOFT", "TIMEOUT_HARD" se acionado, ou None
    """
    global position_open_time, current_coin_purchase_price
    
    if position_open_time is None:
        return None
    
    time_held = time.time() - position_open_time
    hours_held = time_held / 3600
    
    # Obter preço atual
    current_price = get_current_price(coin_pair_to_check)
    if current_price is None:
        return None
    
    # Calcular P&L atual
    pnl_percentage = ((current_price - current_coin_purchase_price) / current_coin_purchase_price) * 100
    
    log_info(f"Posição aberta há {hours_held:.1f} horas. P&L atual: {pnl_percentage:.2f}%")
    
    # Timeout suave - vende se estiver em lucro após X horas
    if time_held >= config.POSITION_MAX_HOLD_TIME:
        if pnl_percentage > 0:
            log_info(f"!!! TIMEOUT SUAVE ATIVADO - Vendendo com lucro de {pnl_percentage:.2f}% após {hours_held:.1f}h !!!")
            return "TIMEOUT_SOFT"
        else:
            log_info(f"Timeout suave atingido mas posição em prejuízo ({pnl_percentage:.2f}%). Aguardando...")
    
    # Timeout forçado - vende independentemente após Y horas
    if time_held >= config.POSITION_FORCE_SELL_TIME:
        log_info(f"!!! TIMEOUT FORÇADO - Vendendo após {hours_held:.1f}h com P&L de {pnl_percentage:.2f}% !!!")
        return "TIMEOUT_HARD"
    
    return None


# Adicionar trailing stop
def update_trailing_stop():
    """
    Atualiza o stop loss dinamicamente baseado no preço máximo atingido.
    """
    global stop_loss_pct, current_coin, current_coin_purchase_price, highest_price_reached
    
    if not config.USE_TRAILING_STOP or current_coin is None:
        return
    
    current_price = get_current_price(current_coin)
    if current_price is None:
        return
    
    # Inicializa o preço máximo se ainda não existir
    if 'highest_price_reached' not in globals():
        globals()['highest_price_reached'] = current_coin_purchase_price
    
    # Atualiza o preço máximo
    if current_price > highest_price_reached:
        old_highest = highest_price_reached
        highest_price_reached = current_price
        
        # Calcula novo stop loss (X% abaixo do máximo)
        new_stop_price = highest_price_reached * (1 - config.TRAILING_STOP_DISTANCE)
        
        # Só atualiza se o novo stop for maior que o anterior
        if new_stop_price > current_coin_purchase_price * (1 - stop_loss_pct):
            old_stop_pct = stop_loss_pct
            stop_loss_pct = 1 - (new_stop_price / current_coin_purchase_price)
            
            log_info(f"📈 Trailing Stop Atualizado!")
            log_info(f"   Novo máximo: {highest_price_reached:.6f} (anterior: {old_highest:.6f})")
            log_info(f"   Stop Loss: {old_stop_pct*100:.2f}% → {stop_loss_pct*100:.2f}%")
            log_info(f"   Stop ativará em: {new_stop_price:.6f}")


# Modificar a função initialize_trade para registrar o tempo
def initialize_trade_with_timeout(coin_pair_to_buy):
    """
    Versão modificada de initialize_trade que registra o tempo de abertura.
    """
    global position_open_time, highest_price_reached
    
    if not can_open_new_trade():
        log_info("Não é permitido abrir novo trade no momento")
        return False
    
    # Chama a função original (você pode integrar diretamente)
    result = initialize_trade(coin_pair_to_buy)
    
    if result:
        position_open_time = time.time()
        highest_price_reached = current_coin_purchase_price
        log_info(f"⏰ Timer de posição iniciado. Timeout suave em {config.POSITION_MAX_HOLD_TIME/3600:.1f}h, forçado em {config.POSITION_FORCE_SELL_TIME/3600:.1f}h")
    
    return result

def execute_strategy_enhanced():
    """
    Versão aprimorada de execute_strategy com timeout e trailing stop.
    """
    global current_coin, current_coin_base_asset, current_coin_purchase_price, current_coin_quantity_bought, current_coin_total_cost_usdt
    global usdt_balance_before_trade, position_open_time, highest_price_reached

    
    if check_daily_loss_limit():
        return False
    
    action_taken = False
    
    if not current_coin:
        log_info("Não há moeda atual. Buscando a melhor oportunidade...")
        chosen_coin_pair = choose_best_coin()
        
        if chosen_coin_pair:
            if initialize_trade_with_timeout(chosen_coin_pair):
                action_taken = True
        else:
            log_info("Nenhuma moeda adequada encontrada para compra neste momento.")
    else:
        # Atualiza trailing stop se ativado
        update_trailing_stop()
        
        # Verifica timeout PRIMEIRO (tem prioridade sobre stop loss/take profit)
        timeout_trigger = check_position_timeout(current_coin)
        
        if timeout_trigger:
            trigger_reason = timeout_trigger
        else:
            # Verifica stop loss e take profit normalmente
            trigger_reason = check_stop_loss_and_take_profit(current_coin)
        
        if trigger_reason:
            log_info(f"💰 Decisão de vender {current_coin} devido a: {trigger_reason}")
            
            # Executa a venda (código existente)
            quantity_to_sell = get_balance(current_coin_base_asset)
            if quantity_to_sell == 0 and current_coin_quantity_bought > 0:
                quantity_to_sell = current_coin_quantity_bought
            
            if quantity_to_sell > 0:
                sell_order_response = sell_coin(current_coin, quantity_to_sell)
                
                if sell_order_response:
                    avg_sell_price, total_qty_sold, gross_usdt_received, fees_paid_usdt_sell = _calculate_order_details(sell_order_response)
                    net_usdt_received = gross_usdt_received - fees_paid_usdt_sell

                    log_trade("SELL", current_coin, total_qty_sold, avg_sell_price, 
                              gross_usdt_received, fees_paid_usdt_sell, net_usdt_received)

                    # Calcular P&L do Trade
                    # Custo da compra já inclui taxas (current_coin_total_cost_usdt)
                    # Receita da venda já é líquida (net_usdt_received)
                    
                    # P&L baseado no custo da moeda comprada e receita da venda
                    profit_or_loss_coin_trade = net_usdt_received - current_coin_total_cost_usdt
                    
                    # P&L baseado na variação do saldo total de USDT (mais abrangente)
                    usdt_balance_after_trade = get_balance('USDT')
                    profit_or_loss_usdt_balance = usdt_balance_after_trade - usdt_balance_before_trade
                    
                    log_info(f"\n--- RESULTADO DO TRADE PARA {current_coin} ---")
                    log_info(f"Custo Total da Compra (c/ taxas): {current_coin_total_cost_usdt:.2f} USDT")
                    log_info(f"Receita Líquida da Venda (c/ taxas): {net_usdt_received:.2f} USDT")
                    log_info(f"Lucro/Prejuízo (Moeda Específica): {profit_or_loss_coin_trade:.2f} USDT")
                    log_info(f"----------------------------------------------")
                    log_info(f"Saldo USDT (Antes da Compra): {usdt_balance_before_trade:.2f} USDT")
                    log_info(f"Saldo USDT (Após a Venda): {usdt_balance_after_trade:.2f} USDT")
                    log_info(f"Lucro/Prejuízo (Variação Saldo USDT): {profit_or_loss_usdt_balance:.2f} USDT")
                    update_daily_profit(profit_or_loss_usdt_balance)
                    log_info(f"--- FIM DO RESULTADO DO TRADE ---\n")

                    # Resetar estado para a próxima trade
                    current_coin = None
                    current_coin_base_asset = None
                    current_coin_purchase_price = 0.0
                    current_coin_quantity_bought = 0.0
                    current_coin_total_cost_usdt = 0.0
                    usdt_balance_before_trade = 0.0 # Reset
                    action_taken = True
                    position_open_time = None
                    highest_price_reached = 0
                    log_info("Moeda vendida! Pronto para selecionar nova moeda na próxima execução.")
                    log_info("Valor da carteira APÓS a venda:")
                    get_portfolio_value()
                    save_bot_state()

                else:
                    log_error(f"Falha ao executar ordem de venda para {current_coin}. Mantendo posição.")
               
    
    return action_taken


def execute_strategy():
    """
    Executa a estratégia de trading:
    1) Se não tivermos uma moeda, escolhe a melhor com base em análise técnica e sentimento
    2) Se já tivermos uma moeda, verifica stop loss e take profit e realiza venda se necessário
    
    Returns:
        bool: True se alguma ação foi tomada, False caso contrário
    """
    global current_coin, current_coin_base_asset, current_coin_purchase_price, current_coin_quantity_bought, current_coin_total_cost_usdt
    global usdt_balance_before_trade

    if check_daily_loss_limit():
        return False
    
    action_taken = False

    if not current_coin:
        log_info("Não há moeda atual. Buscando a melhor oportunidade...")
        
        # Garante que não há saldos significativos de outras moedas (exceto USDT) antes de uma nova compra.
        # Isso é opcional e depende da estratégia de querer limpar tudo ou permitir múltiplas posições (não implementado).
        # sell_all_coins() # Pode ser muito agressivo se houver poeira ou outras posições intencionais.
        # Por ora, vamos focar em uma moeda por vez. Se `current_coin` é None, assume-se que a posição anterior foi fechada.

        chosen_coin_pair = choose_best_coin() # Retorna par ex: 'BTCUSDT'
        
        if chosen_coin_pair:
            if initialize_trade(chosen_coin_pair):
                action_taken = True
            else:
                log_warning(f"Falha ao inicializar trade para {chosen_coin_pair}. Tentando na próxima vez.")
        else:
            log_info("Nenhuma moeda adequada encontrada para compra neste momento.")
    else:
        # Já temos uma moeda, verifica stop loss e take profit
        log_info(f"Verificando condições para {current_coin} (Comprado a {current_coin_purchase_price:.6f}, Qtd: {current_coin_quantity_bought:.8f}):")
        
        trigger_reason = check_stop_loss_and_take_profit(current_coin)
        
        if trigger_reason:
            log_info(f"Decisão de vender {current_coin} devido a: {trigger_reason}")
            
            # Vender a quantidade específica que temos
            quantity_to_sell = get_balance(current_coin_base_asset) # Pega o saldo atual da moeda base
            if quantity_to_sell == 0 and current_coin_quantity_bought > 0:
                 log_warning(f"Saldo de {current_coin_base_asset} é zero, mas esperava-se {current_coin_quantity_bought}. Usando quantidade registrada.")
                 quantity_to_sell = current_coin_quantity_bought # Fallback para a quantidade comprada registrada
            
            if quantity_to_sell > 0:
                log_info(f"Saldo atual de {current_coin_base_asset} para vender: {quantity_to_sell:.8f}")
                sell_order_response = sell_coin(current_coin, quantity_to_sell)

                if sell_order_response:
                    avg_sell_price, total_qty_sold, gross_usdt_received, fees_paid_usdt_sell = _calculate_order_details(sell_order_response)
                    net_usdt_received = gross_usdt_received - fees_paid_usdt_sell

                    log_trade("SELL", current_coin, total_qty_sold, avg_sell_price, 
                              gross_usdt_received, fees_paid_usdt_sell, net_usdt_received)

                    # Calcular P&L do Trade
                    # Custo da compra já inclui taxas (current_coin_total_cost_usdt)
                    # Receita da venda já é líquida (net_usdt_received)
                    
                    # P&L baseado no custo da moeda comprada e receita da venda
                    profit_or_loss_coin_trade = net_usdt_received - current_coin_total_cost_usdt
                    
                    # P&L baseado na variação do saldo total de USDT (mais abrangente)
                    usdt_balance_after_trade = get_balance('USDT')
                    profit_or_loss_usdt_balance = usdt_balance_after_trade - usdt_balance_before_trade
                    
                    log_info(f"\n--- RESULTADO DO TRADE PARA {current_coin} ---")
                    log_info(f"Custo Total da Compra (c/ taxas): {current_coin_total_cost_usdt:.2f} USDT")
                    log_info(f"Receita Líquida da Venda (c/ taxas): {net_usdt_received:.2f} USDT")
                    log_info(f"Lucro/Prejuízo (Moeda Específica): {profit_or_loss_coin_trade:.2f} USDT")
                    log_info(f"----------------------------------------------")
                    log_info(f"Saldo USDT (Antes da Compra): {usdt_balance_before_trade:.2f} USDT")
                    log_info(f"Saldo USDT (Após a Venda): {usdt_balance_after_trade:.2f} USDT")
                    log_info(f"Lucro/Prejuízo (Variação Saldo USDT): {profit_or_loss_usdt_balance:.2f} USDT")
                    update_daily_profit(profit_or_loss_usdt_balance)
                    log_info(f"--- FIM DO RESULTADO DO TRADE ---\n")

                    # Resetar estado para a próxima trade
                    current_coin = None
                    current_coin_base_asset = None
                    current_coin_purchase_price = 0.0
                    current_coin_quantity_bought = 0.0
                    current_coin_total_cost_usdt = 0.0
                    usdt_balance_before_trade = 0.0 # Reset
                    action_taken = True
                    
                    log_info("Moeda vendida! Pronto para selecionar nova moeda na próxima execução.")
                    log_info("Valor da carteira APÓS a venda:")
                    get_portfolio_value()
                    save_bot_state()
                else:
                    log_error(f"Falha ao executar ordem de venda para {current_coin}. Mantendo posição.")
            else:
                log_warning(f"Tentativa de venda de {current_coin}, mas saldo de {current_coin_base_asset} é zero ou inválido. Resetando estado.")
                # Resetar estado mesmo se a venda falhar por saldo zero, para evitar loops
                current_coin = None # Força a reavaliação no próximo ciclo
    
    return action_taken