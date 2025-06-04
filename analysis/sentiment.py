"""
Módulo para análise de sentimento de criptomoedas
"""
import time
import json
import openai

from utils.helpers import log_info, log_error, extract_json_from_text
from config import config
from llm.client import query_local_llm_with_retry, is_llm_server_online
from llm.prompts import create_sentiment_analysis_prompt

# Cache para evitar múltiplas chamadas de API para o mesmo conteúdo
sentiment_cache = {}


def create_default_sentiment_result(coin, sentiment="neutro"):
    """
    Cria um resultado padrão para casos de falha na análise.
    """
    return {
        "sentiment": sentiment,
        "score": 50,
        "buy_recommendation": "NEUTRO",
        "key_factors": [f"Análise de sentimento inconclusiva para {coin}"],
        "reddit_sentiment": sentiment,
        "twitter_sentiment": sentiment,
        "news_sentiment": sentiment,
        "error": "Falha na análise de sentimento"
    }


def validate_sentiment_result(result):
    """
    Valida e corrige o resultado do sentimento para garantir que todos 
    os campos necessários estão presentes e com valores válidos.
    """
    if not isinstance(result, dict):
        return create_default_sentiment_result("desconhecido")
    
    # Garante que todos os campos necessários existem
    default_result = create_default_sentiment_result("desconhecido")
    
    for key in default_result:
        if key not in result:
            result[key] = default_result[key]
    
    # Corrige o campo score se estiver como string
    if isinstance(result["score"], str):
        try:
            result["score"] = int(result["score"])
        except ValueError:
            result["score"] = 50
    
    # Limita o score entre 0 e 100
    result["score"] = max(0, min(100, result["score"]))
    
    # Padroniza valores de buy_recommendation para SIM, NÃO ou NEUTRO
    if result["buy_recommendation"] not in ["SIM", "NÃO", "NEUTRO"]:
        buy_rec = result["buy_recommendation"].upper()
        if "SIM" in buy_rec or "BUY" in buy_rec or "COMPRA" in buy_rec:
            result["buy_recommendation"] = "SIM"
        elif "NÃO" in buy_rec or "NAO" in buy_rec or "NOT" in buy_rec or "NO" in buy_rec:
            result["buy_recommendation"] = "NÃO"
        else:
            result["buy_recommendation"] = "NEUTRO"
    
    # Garante que key_factors é uma lista
    if not isinstance(result["key_factors"], list):
        if isinstance(result["key_factors"], str):
            result["key_factors"] = [result["key_factors"]]
        else:
            result["key_factors"] = ["Fator não especificado"]
    
    return result


def use_openai_for_sentiment(prompt):
    """
    Função de fallback para usar OpenAI quando o LLM local falhar.
    """
    try:
        # Configura a chave da API
        openai.api_key = config.OPENAI_KEY
        
        # Faz a chamada para a API
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Você é um analista de sentimento de mercado especializado em criptomoedas. Forneça análises objetivas baseadas apenas nos dados fornecidos."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=8192
        )
        
        # Extrai o resultado
        result_text = response.choices[0].message.content.strip()
        log_info("Resposta recebida da OpenAI")
        
        # Extrai JSON da resposta
        result = extract_json_from_text(result_text)
        if result is None:
            log_error("Não foi possível extrair JSON da resposta da OpenAI")
            return create_default_sentiment_result("desconhecido", "neutro")
        
        # Valida o resultado
        result = validate_sentiment_result(result)
        
        return result
    except Exception as e:
        log_error(f"Erro no fallback para OpenAI: {e}")
        return create_default_sentiment_result("desconhecido", "neutro")


def analyze_sentiment_with_llm(coin, text_data):
    """
    Analisa o sentimento dos textos coletados usando LLM local ou OpenAI como fallback.
    
    Args:
        coin (str): Nome da criptomoeda
        text_data (dict): Dicionário com textos do Reddit, Twitter e notícias
        
    Returns:
        dict: Resultados da análise de sentimento
    """
    # Chave para cache
    cache_key = f"{coin}_{int(time.time() / 3600)}"  # Chave baseada na moeda e na hora atual
    
    # Verifica se já existe no cache e se ainda é válido
    if cache_key in sentiment_cache:
        cache_time, cached_result = sentiment_cache[cache_key]
        if time.time() - cache_time < config.SENTIMENT_CACHE_DURATION:
            log_info(f"Usando resultado de sentimento em cache para {coin}")
            return cached_result
    
    # Verifica se o servidor LLM está online
    use_local_llm = is_llm_server_online()
    
    try:
        if use_local_llm:
            log_info("Usando servidor de LLM local")
            
            # Cria o prompt para análise de sentimento
            prompt = create_sentiment_analysis_prompt(coin, text_data)
            
            messages = [
                {"role": "system", "content": "Você é um analista de mercado de criptomoedas. Sua tarefa é fornecer análise de sentimento objetiva baseada nos dados fornecidos."},
                {"role": "user", "content": prompt}
            ]
            
            # Usa o mecanismo de retry
            response_data = query_local_llm_with_retry(messages, temperature=0.2, max_tokens=8192)
            
            if response_data and 'choices' in response_data and len(response_data['choices']) > 0:
                result_text = response_data['choices'][0]['message']['content'].strip()
                log_info(f"Resposta do LLM recebida para {coin}")
            else:
                if config.USE_OPENAI_FALLBACK:
                    log_info("Fallback para OpenAI após falha no LLM local")
                    return use_openai_for_sentiment(prompt)
                else:
                    raise Exception("Falha na resposta do LLM local e o fallback está desativado")
        else:
            # Fallback para OpenAI
            if config.USE_OPENAI_FALLBACK:
                log_info("Usando OpenAI como fallback porque o servidor LLM local está offline")
                prompt = create_sentiment_analysis_prompt(coin, text_data)
                return use_openai_for_sentiment(prompt)
            else:
                raise Exception("Servidor LLM local está offline e o fallback está desativado")
        
        # Processamento do resultado
        try:
            # Tenta extrair JSON da resposta
            result = extract_json_from_text(result_text)
            if result is None:
                log_error(f"Não foi possível extrair JSON da resposta para {coin}")
                result = create_default_sentiment_result(coin, "neutro")
            
            # Validação do resultado para garantir todos os campos necessários
            result = validate_sentiment_result(result)
            
            # Adiciona ao cache
            sentiment_cache[cache_key] = (time.time(), result)
            
            return result
        except json.JSONDecodeError as e:
            log_error(f"Erro ao decodificar JSON: {e}")
            return create_default_sentiment_result(coin, "neutro")
        
    except Exception as e:
        log_error(f"Erro na análise de sentimento para {coin}: {e}")
        return create_default_sentiment_result(coin, "neutro")


def clear_sentiment_cache(max_age=None):
    """
    Limpa o cache de sentimento, removendo entradas antigas.
    
    Args:
        max_age (int, optional): Idade máxima em segundos. Se None, usa a duração padrão do cache.
    """
    if max_age is None:
        max_age = config.SENTIMENT_CACHE_DURATION
    
    current_time = time.time()
    old_keys = [k for k, (t, _) in sentiment_cache.items() if current_time - t > max_age]
    
    for k in old_keys:
        del sentiment_cache[k]
    
    log_info(f"Cache de sentimento limpo. Removidas {len(old_keys)} entradas antigas.")


def get_combined_sentiment_score(sentiment_result):
    """
    Combina o resultado da análise de sentimento em um score ponderado.
    
    Args:
        sentiment_result (dict): Resultado da análise de sentimento
        
    Returns:
        float: Score ponderado
    """
    # Extrair o score bruto
    raw_score = sentiment_result.get('score', 50)
    
    # Ajustar com base na recomendação de compra
    buy_recommendation = sentiment_result.get('buy_recommendation', 'NEUTRO')
    
    # Normalizar o score para escala -50 a +50 (onde 0 é neutro)
    normalized_score = (raw_score - 50) * 2
    
    # Adicionar bônus/penalidade para recomendações explícitas
    if buy_recommendation == 'SIM':
        normalized_score += 50
    elif buy_recommendation == 'NÃO':
        normalized_score -= 50
    
    return normalized_score