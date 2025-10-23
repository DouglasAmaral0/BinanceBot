"""
Cliente para comunicação com o servidor LLM local
"""
import time
import requests
from requests.exceptions import RequestException, Timeout, ConnectionError

from config import config
from utils.helpers import log_info, log_error



def is_llm_server_online():
    """
    Verifica se o servidor LLM local está online e respondendo.
    
    Returns:
        bool: True se o servidor estiver online, False caso contrário
    """
    try:
        response = requests.get(f"{config.LLM_SERVER_URL}/v1/models", timeout=config.LLM_SERVER_TIMEOUT)
        if response.status_code == 200:
            log_info("Servidor LLM local está online e respondendo.")
            return True
        else:
            log_error(f"Servidor LLM local retornou código de status {response.status_code}")
            return False
    except (RequestException, Timeout, ConnectionError) as e:
        log_error(f"Erro ao conectar ao servidor LLM local: {e}")
        return False


def query_local_llm(messages, temperature=0.2, max_tokens=8192):
    """
    Envia uma solicitação para o servidor LLM local com melhor tratamento de timeouts.
    
    Args:
        messages (list): Lista de mensagens no formato do chat
        temperature (float): Temperatura para a geração de texto
        max_tokens (int): Número máximo de tokens na resposta
        
    Returns:
        dict: Resposta do LLM ou None em caso de erro
    """
    try:
        payload = {
            "model": config.LLM_MODEL_NAME,
            "reasoning": "High",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False  # Garante que não estamos usando streaming
        }
        
        # Aumenta o timeout significativamente para modelos grandes
        timeout_value = config.LLM_RESPONSE_WAIT
        
        log_info(f"Enviando solicitação para LLM com timeout de {timeout_value}s")
        
        # Define headers explícitos
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        session = requests.Session()
        response = session.post(
            f"{config.LLM_SERVER_URL}/v1/chat/completions", 
            json=payload,
            headers=headers,
            timeout=timeout_value
        )
        
        if response.status_code == 200:
            result = response.json()
            log_info("Resposta recebida com sucesso do LLM")
            # Verificação adicional para garantir que temos conteúdo válido
            if (result and 'choices' in result and 
                len(result['choices']) > 0 and 
                'message' in result['choices'][0] and
                'content' in result['choices'][0]['message']):
                return result
            else:
                log_error("Resposta do LLM não contém conteúdo válido")
                return None
        else:
            log_error(f"Erro ao consultar LLM local. Status: {response.status_code}, Resposta: {response.text}")
            return None
    except requests.Timeout:
        log_error(f"Timeout ao consultar LLM local após {timeout_value}s")
        return None
    except requests.ConnectionError:
        log_error("Erro de conexão com o servidor LLM local")
        return None
    except Exception as e:
        log_error(f"Exceção ao consultar LLM local: {e}")
        return None


def query_local_llm_with_retry(messages, temperature=0.2, max_tokens=8192, max_retries=None):
    """
    Tenta consultar o LLM local com mecanismo de retry.
    
    Args:
        messages (list): Lista de mensagens para o LLM
        temperature (float): Temperatura para a geração
        max_tokens (int): Número máximo de tokens na resposta
        max_retries (int, optional): Número máximo de tentativas
        
    Returns:
        dict: Resposta do LLM ou None em caso de falha
    """
    if max_retries is None:
        max_retries = config.LLM_REQUEST_RETRIES

    for attempt in range(max_retries):
        log_info(f"Tentativa {attempt+1}/{max_retries} de consulta ao LLM local")
        result = query_local_llm(messages, temperature, max_tokens)
        
        if result is not None:
            return result
        
        # Espera progressiva entre tentativas (1s, 2s, 4s...)
        if attempt < max_retries - 1:  # Não espera após a última tentativa
            wait_time = 2 ** attempt
            log_info(f"Aguardando {wait_time}s antes da próxima tentativa...")
            time.sleep(wait_time)
    
    log_error(f"Todas as {max_retries} tentativas falharam")
    return None


def list_available_models():
    """
    Lista os modelos disponíveis no servidor LLM.
    
    Returns:
        list: Lista de modelos disponíveis ou None em caso de erro
    """
    try:
        response = requests.get(
            f"{config.LLM_SERVER_URL}/v1/models", 
            timeout=config.LLM_SERVER_TIMEOUT
        )
        
        if response.status_code == 200:
            models_data = response.json()
            if 'data' in models_data:
                log_info("Modelos disponíveis:")
                for model in models_data['data']:
                    log_info(f"- {model.get('id', 'Desconhecido')}")
                return models_data['data']
            else:
                log_error("Formato de resposta inesperado")
                return None
        else:
            log_error(f"Erro ao listar modelos. Status: {response.status_code}")
            return None
    except Exception as e:
        log_error(f"Erro ao listar modelos: {e}")
        return None

def diagnose_llm_server():
    """
    Realiza diagnóstico detalhado do servidor LLM e retorna informações sobre seu estado.
    
    Returns:
        bool: True se o servidor está funcionando corretamente, False caso contrário
    """
    log_info("\n=== DIAGNÓSTICO DO SERVIDOR LLM ===")
    
    try:
        # Verificar se o servidor está online
        log_info("Verificando disponibilidade do servidor...")
        models_response = requests.get(
            f"{config.LLM_SERVER_URL}/v1/models", 
            timeout=config.LLM_SERVER_TIMEOUT
        )
        
        if models_response.status_code == 200:
            models_data = models_response.json()
            log_info("Servidor online! Modelos disponíveis:")
            for model in models_data.get('data', []):
                log_info(f"- {model.get('id', 'Desconhecido')}")
            
            # Testa o servidor com uma consulta simples
            log_info("\nTestando capacidade de resposta com prompt simples...")
            test_messages = [
                {"role": "system", "content": "Você é um assistente útil."},
                {"role": "user", "content": "Responda apenas com a palavra 'OK'"}
            ]
            
            start_time = time.time()
            test_response = query_local_llm(test_messages, max_tokens=10)
            response_time = time.time() - start_time
            
            if test_response and 'choices' in test_response:
                log_info(f"Teste bem-sucedido! Tempo de resposta: {response_time:.2f}s")
                return True
            else:
                log_error(f"Servidor online mas não respondeu ao teste em {response_time:.2f}s")
                log_error("Possível problema de capacidade ou configuração")
                return False
        else:
            log_error(f"Servidor retornou código de status {models_response.status_code}")
            log_error(f"Resposta: {models_response.text}")
            return False
            
    except Timeout:
        log_error(f"Timeout ao tentar conectar no servidor em {config.LLM_SERVER_URL}")
        return False
    except ConnectionError:
        log_error(f"Erro de conexão com o servidor em {config.LLM_SERVER_URL}")
        log_error("Verifique se o servidor está rodando e se a URL está correta")
        return False
    except Exception as e:
        log_error(f"Erro desconhecido durante diagnóstico: {e}")
        return False
    finally:
        log_info("=====================================")