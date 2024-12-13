from binance.client import Client
import os
import sys
import time
import pandas as pd
import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import config.config as config

apiKey = config.BINACEAPIKEY
apiSecret = config.BINANCESECRETKEY

client = Client(apiKey, apiSecret)

coins = ['TRX', 'ADA', 'SOL', 'ATA', 'DODO', 'SHIB', 'DOGE', 'APE', 'ETH']
coinsPairs = [f'{coin}USDT' for coin in coins]

# Variáveis globais
currentCoin = None
currentCoinPrice = 0.0
stop_loss_pct = 0.05
take_profit_pct = 0.10
last_sold_coin = None 
cooldown_time = 2 * 60 * 60 
last_trade_time = 0

def getBalance(coin):
    balance = client.get_asset_balance(asset=coin)
    print('Coin:', coin, 'Balance:', balance)
    return float(balance['free'])

# Função para obter regras de tamanho mínimo de lote
def getLotSizeRules(coinPair):
    info = client.get_symbol_info(coinPair)
    for filter in info['filters']:
        if filter['filterType'] == 'LOT_SIZE':
            return {
                'minQty': float(filter['minQty']),
                'stepSize': float(filter['stepSize'])
            }

# Função para obter dados históricos
def getHistoricalData(coinPair):
    klines = client.get_historical_klines(coinPair, Client.KLINE_INTERVAL_1HOUR, "1 day ago UTC")
    closes = [float(candle[4]) for candle in klines]
    return pd.DataFrame(closes, columns=['close'])

# Função para calcular o RSI
def calculateRSI(coinPair, period=14):
    df = getHistoricalData(coinPair)
    
    if len(df) < period:
        print(f"Insufficient data to calculate RSI for {coinPair}")
        return None
    
    df['diff'] = df['close'].diff()
    df['gain'] = np.where(df['diff'] > 0, df['diff'], 0)
    df['loss'] = np.where(df['diff'] < 0, -df['diff'], 0)
    avg_gain = df['gain'].rolling(window=period).mean()
    avg_loss = df['loss'].rolling(window=period).mean()
    rs = avg_gain / avg_loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    print('RSI:', coinPair, df['RSI'].iloc[-1])
    return df['RSI'].iloc[-1]

def sellCoin(coinPair, quantity):
    lotSizeRules = getLotSizeRules(coinPair)
    quantity = quantity - (quantity % lotSizeRules['stepSize'])
    
    if quantity < lotSizeRules['minQty']:
        print(f"Quantity {quantity} of {coinPair} is below the allowed. Skipping sale")
        return None
    
    quantity = round(quantity, 5)
    order = client.order_market_sell(symbol=coinPair, quantity=quantity)
    return order

def buyCoin(coinPair, availableUSDT):
    coinPrice = float(client.get_symbol_ticker(symbol=coinPair)['price'])
    availableUSDTCommission = availableUSDT * 0.999
    
    coinQuantity = availableUSDTCommission / coinPrice
    lotSizeRules = getLotSizeRules(coinPair)
    coinQuantity = coinQuantity - (coinQuantity % lotSizeRules['stepSize'])
    
    if coinQuantity < lotSizeRules['minQty']:
        print(f"Quantity {coinQuantity} of {coinPair} is below the allowed. Skipping purchase.")
        return None
    
    coinQuantity = round(coinQuantity, 5)
    print(f"Quantity {coinQuantity} of {coinPair} was purchased")
    order = client.order_market_buy(symbol=coinPair, quantity=coinQuantity)
    return order

def checkStopLossAndTakeProfit(actualPrice):
    global currentCoinPrice
    
    if actualPrice <= currentCoinPrice * (1 - stop_loss_pct):
        print(f"Activating Stop Loss, selling {currentCoin}")
        sellAllCoin()
        return True
    
    elif actualPrice >= currentCoinPrice * (1 + take_profit_pct):
        print(f"Activating Take Profit! Selling {currentCoin}")
        sellAllCoin()
        return True
    
    return False

def sellAllCoin():
    global last_sold_coin, last_trade_time
    USDTBalance = 0
    for coinPair in coinsPairs:
        coin = coinPair.replace("USDT", "")
        coinBalance = getBalance(coin)
        
        if coinBalance > 0:
            print(f"Selling {coinBalance} of {coin}")
            sellOrder = sellCoin(coinPair, coinBalance)
            if sellOrder:
                USDTBalance += coinBalance * float(client.get_symbol_ticker(symbol=coinPair)['price'])
                print('USDTBalance', USDTBalance)
                last_sold_coin = coinPair
                last_trade_time = time.time()
    
    return USDTBalance

def chooseRSICoin():
    bestRSI = 100
    bestCoin = None
    current_time = time.time()
    
    for coinPair in coinsPairs:
        if coinPair == last_sold_coin and (current_time - last_trade_time) < cooldown_time:
            print(f"Skipping {coinPair} due to cooldown period.")
            continue
        
        rsi = calculateRSI(coinPair)
        if rsi is None:
            print(f"Insufficient data for {coinPair}. Ignoring this coin.")
            continue
        if rsi < bestRSI:  
            bestRSI = rsi
            bestCoin = coinPair
    return bestCoin

def executeStrategy():
    global currentCoin, currentCoinPrice
    if not currentCoin:
        print("First execution: Buying the most devalued coin.")
        sellAllCoin()
        currentCoin = chooseRSICoin()
        if currentCoin is not None:  
            currentCoinPrice = float(client.get_symbol_ticker(symbol=currentCoin)['price'])
            USDTBalance = getBalance('USDT')
            buyCoin(currentCoin, USDTBalance)
    
    else:
        actualPrice = float(client.get_symbol_ticker(symbol=currentCoin)['price'])
        print(f"Actual price of {currentCoin}: {actualPrice}, Buy price: {currentCoinPrice}")
        if checkStopLossAndTakeProfit(actualPrice):
            currentCoin = None

def main(timeInterval=120):
    while True:
        executeStrategy()
        print(f"Waiting {timeInterval} minutes for next check...")
        time.sleep(timeInterval * 60)

if __name__ == "__main__":
    main()
