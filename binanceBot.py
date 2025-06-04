"""
Bot de Trading de Criptomoedas com Análise de Sentimento

Este bot utiliza análise técnica (RSI, volatilidade) e análise de sentimento
para selecionar e negociar criptomoedas automaticamente.

Autor: Douglas Amaral
Versão: 1.0.0
"""
import os
import sys
import time
from datetime import datetime

# Adiciona os diretórios ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Importações dos módulos
from config import config
from utils.helpers import log_info, log_error, wait_with_progress
from api.binance_client import initialize_client, get_portfolio_value, sell_all_coins
from api.data_collectors import init_collectors
from llm.client import diagnose_llm_server
from analysis.sentiment import clear_sentiment_cache
from strategy.trading import execute_strategy


def initialize_bot():
    """
    Inicializa todos os componentes do bot.
    
    Returns:
        bool: True se todos os componentes foram inicializados com sucesso
    """
    log_info("\n==== INICIALIZANDO BOT DE TRADING DE CRIPTOMOEDAS ====")
    
    # Inicializa cliente da Binance
    try:
        initialize_client()
        log_info("✓ Cliente Binance inicializado com sucesso")
    except Exception as e:
        log_error(f"✗ Falha ao inicializar cliente Binance: {e}")
        return False
    
    # Inicializa coletores de dados
    try:
        init_collectors()
        log_info("✓ Coletores de dados inicializados")
    except Exception as e:
        log_error(f"✗ Falha ao inicializar coletores de dados: {e}")
        # Não interrompe, pois alguns coletores podem estar desativados
    
    # Verifica servidor LLM
    server_ok = diagnose_llm_server()
    if not server_ok and not config.USE_OPENAI_FALLBACK:
        log_error("✗ Servidor LLM não está respondendo corretamente e fallback está desativado")
        log_info("A análise de sentimento pode não funcionar. Deseja continuar? (S/N)")
        response = input().strip().upper()
        if response != 'S':
            log_info("Encerrando o bot. Verifique o servidor LLM e tente novamente.")
            return False
    elif not server_ok and config.USE_OPENAI_FALLBACK:
        log_info("! Servidor LLM não está respondendo, mas o fallback para OpenAI está ativado")
    else:
        log_info("✓ Servidor LLM verificado e funcionando")
    
    # Exibe configurações atuais
    log_info("\n==== CONFIGURAÇÕES ATUAIS ====")
    log_info(f"Intervalo entre verificações: {config.DEFAULT_INTERVAL} minutos")
    log_info(f"Stop Loss padrão: {config.DEFAULT_STOP_LOSS_PCT*100:.1f}%")
    log_info(f"Take Profit padrão: {config.DEFAULT_TAKE_PROFIT_PCT*100:.1f}%")
    log_info(f"Cooldown após venda: {config.COOLDOWN_TIME/3600:.1f} horas")
    log_info(f"Modelo LLM: {config.LLM_MODEL_NAME}")
    log_info(f"Fallback para OpenAI: {'Ativado' if config.USE_OPENAI_FALLBACK else 'Desativado'}")
    log_info("\n==== VENDE TODAS AS MOEDAS NA INCIALIZAÇÃO ====")
    sell_all_coins()
    # Exibe portfolio atual
    log_info("\n==== PORTFOLIO INICIAL ====")
    
    total_value = get_portfolio_value()
    
    log_info("\n==== INICIALIZAÇÃO CONCLUÍDA ====")
    return True


def main(interval=None):
    """
    Loop principal do bot de trading.
    
    Args:
        interval (int, optional): Intervalo em minutos entre as execuções.
            Se None, usa o valor padrão da configuração.
    """
    if interval is None:
        interval = config.DEFAULT_INTERVAL
    
    # Inicializa o bot
    if not initialize_bot():
        log_error("Falha na inicialização. Encerrando...")
        return
    
    # Contador para controle de análises completas de sentimento
    cycle_counter = 0
    
    # Loop principal
    try:
        while True:
            log_info(f"\n==== INICIANDO CICLO DE TRADING {cycle_counter + 1} ====")
            log_info(f"Data/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Executa a estratégia
            try:
                execute_strategy()
            except Exception as e:
                log_error(f"Erro ao executar estratégia: {e}")
            
            # Incrementa contador de ciclos
            cycle_counter += 1
            
            # Limpa o cache periodicamente
            if cycle_counter % 12 == 0:  # A cada 12 ciclos
                clear_sentiment_cache()
            
            # Aguarda até o próximo ciclo
            log_info(f"\nCiclo completado. Próxima execução em {interval} minutos.")
            wait_with_progress(interval)
    
    except KeyboardInterrupt:
        log_info("\n==== BOT INTERROMPIDO PELO USUÁRIO ====")
    except Exception as e:
        log_error(f"\n==== ERRO FATAL: {e} ====")
    finally:
        log_info("\n==== ENCERRANDO BOT DE TRADING ====")
        log_info("Portfolio final:")
        get_portfolio_value()


if __name__ == "__main__":
    # Permite passar o intervalo como argumento de linha de comando
    if len(sys.argv) > 1:
        try:
            interval = int(sys.argv[1])
            main(interval)
        except ValueError:
            log_error(f"Intervalo inválido: {sys.argv[1]}. Usando padrão: {config.DEFAULT_INTERVAL} minutos.")
            main()
    else:
        main()