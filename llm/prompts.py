"""
Templates de prompts para diferentes cenários de análise
"""
from config import config


def create_sentiment_analysis_prompt(coin, text_data):
    """
    Cria um prompt simplificado para análise de sentimento.
    
    Args:
        coin (str): Símbolo da criptomoeda
        text_data (dict): Dados coletados de diferentes fontes
        
    Returns:
        str: Prompt formatado para o LLM
    """
    # Limita o número de exemplos para reduzir o tamanho do prompt
    reddit_sample = ""
    if 'reddit' in text_data and text_data['reddit']:
        reddit_posts = text_data['reddit'][:3]  # Limita a 3 posts
        reddit_sample = "\n".join([
            f"Reddit Post: {p.get('title', 'Sem título')} - " +
            f"{p.get('text', '')[:200]}..." if len(p.get('text', '')) > 200 else p.get('text', '')
            for p in reddit_posts
        ])
    
    news_sample = ""
    if 'news' in text_data and text_data['news']:
        news_articles = text_data['news'][:2]  # Limita a 2 artigos
        news_sample = "\n".join([
            f"Notícia: {n.get('title', 'Sem título')} - " +
            f"{n.get('description', '')[:150]}..." if len(n.get('description', '')) > 150 else n.get('description', '')
            for n in news_articles
        ])
    
    twitter_sample = ""
    if 'twitter' in text_data and text_data['twitter']:
        tweets = text_data['twitter'][:5]  # Limita a 5 tweets
        twitter_sample = "\n".join([
            f"Tweet: {t.get('text', '')[:100]}..." if len(t.get('text', '')) > 100 else t.get('text', '')
            for t in tweets
        ])
    
    # Cria seções separadamente (corrigindo o problema de f-strings aninhadas)
    reddit_section = "=== REDDIT ===\n"
    reddit_section += reddit_sample if reddit_sample else "Sem dados disponíveis."
    
    news_section = "=== NOTÍCIAS ===\n"
    news_section += news_sample if news_sample else "Sem dados disponíveis."
    
    twitter_section = "=== TWITTER ===\n"
    twitter_section += twitter_sample if twitter_sample else "Sem dados disponíveis."
    
    # Template de prompt principal
    prompt = f"""
    Analise o sentimento do mercado sobre a criptomoeda {coin} com base nos dados abaixo.
    
    DADOS DISPONÍVEIS:
    
    {reddit_section}
    
    {news_section}
    
    {twitter_section}
    
    INSTRUÇÕES:
    Forneça sua análise no formato JSON, com os seguintes campos:
    - sentiment: "positivo", "negativo", "neutro", "muito positivo" ou "muito negativo"
    - score: um número de 0 a 100, onde 0 é extremamente negativo e 100 é extremamente positivo
    - buy_recommendation: "SIM", "NÃO" ou "NEUTRO"
    - key_factors: um array com 2-3 frases curtas sobre os fatores-chave que influenciam o sentimento
    - reddit_sentiment: "positivo", "negativo" ou "neutro"
    - news_sentiment: "positivo", "negativo" ou "neutro"
    - twitter_sentiment: "positivo", "negativo" ou "neutro"
    
    Responda APENAS com o JSON, sem explicações adicionais.
    """
    
    # Limita o tamanho do prompt se necessário
    if len(prompt) > config.LLM_PROMPT_MAX_LENGTH:
        excess = len(prompt) - config.LLM_PROMPT_MAX_LENGTH
        # Reduzir o tamanho de cada amostra
        if excess > 0 and reddit_sample:
            reddit_sample = reddit_sample[:len(reddit_sample)-excess//3]
            reddit_section = "=== REDDIT ===\n" + reddit_sample
        
        if excess > 0 and news_sample:
            news_sample = news_sample[:len(news_sample)-excess//3]
            news_section = "=== NOTÍCIAS ===\n" + news_sample
        
        if excess > 0 and twitter_sample:
            twitter_sample = twitter_sample[:len(twitter_sample)-excess//3]
            twitter_section = "=== TWITTER ===\n" + twitter_sample
        
        # Recompõe o prompt com as amostras reduzidas
        prompt = f"""
        Analise o sentimento do mercado sobre a criptomoeda {coin} com base nos dados abaixo.
        
        DADOS DISPONÍVEIS:
        
        {reddit_section}
        
        {news_section}
        
        {twitter_section}
        
        INSTRUÇÕES:
        Forneça sua análise no formato JSON, com os seguintes campos:
        - sentiment: "positivo", "negativo", "neutro", "muito positivo" ou "muito negativo"
        - score: um número de 0 a 100, onde 0 é extremamente negativo e 100 é extremamente positivo
        - buy_recommendation: "SIM", "NÃO" ou "NEUTRO"
        - key_factors: um array com 2-3 frases curtas sobre os fatores-chave que influenciam o sentimento
        - reddit_sentiment: "positivo", "negativo" ou "neutro"
        - news_sentiment: "positivo", "negativo" ou "neutro"
        - twitter_sentiment: "positivo", "negativo" ou "neutro"
        
        Responda APENAS com o JSON, sem explicações adicionais.
        """
    
    return prompt


def create_market_analysis_prompt(coin, price_data, technical_indicators):
    """
    Cria um prompt para análise de mercado com foco em dados técnicos.
    
    Args:
        coin (str): Símbolo da criptomoeda
        price_data (pd.DataFrame): Dados de preço histórico
        technical_indicators (dict): Indicadores técnicos calculados
        
    Returns:
        str: Prompt formatado para o LLM
    """
    # Formata dados de preço
    price_summary = f"Preço atual: {price_data['close'].iloc[-1]:.4f} USDT\n"
    price_summary += f"Variação 24h: {((price_data['close'].iloc[-1] / price_data['close'].iloc[-24] - 1) * 100):.2f}%\n"
    
    # Formata indicadores técnicos
    tech_summary = ""
    if 'rsi' in technical_indicators and technical_indicators['rsi'] is not None:
        tech_summary += f"RSI: {technical_indicators['rsi']:.2f}\n"
    if 'volatility' in technical_indicators and technical_indicators['volatility'] is not None:
        tech_summary += f"Volatilidade: {technical_indicators['volatility']*100:.2f}%\n"
    
    prompt = f"""
    Analise o mercado para a criptomoeda {coin} com base nos dados técnicos abaixo.
    
    DADOS DE PREÇO:
    {price_summary}
    
    INDICADORES TÉCNICOS:
    {tech_summary}
    
    INSTRUÇÕES:
    Forneça sua análise técnica no formato JSON, com os seguintes campos:
    - market_trend: "alta", "baixa" ou "lateral"
    - strength: um número de 0 a 100 que indica a força da tendência
    - rsi_interpretation: interpretação do valor do RSI
    - volatility_interpretation: interpretação da volatilidade
    - short_term_forecast: previsão de curto prazo (24-48h)
    - recommended_action: "comprar", "vender" ou "aguardar"
    - trading_tip: Uma dica de trading específica para esse ativo
    
    Responda APENAS com o JSON, sem explicações adicionais.
    """
    
    return prompt


def create_correlation_analysis_prompt(coin, related_coins_data):
    """
    Cria um prompt para analisar correlações entre diferentes criptomoedas.
    
    Args:
        coin (str): Símbolo da criptomoeda principal
        related_coins_data (dict): Dados de correlação com outras moedas
        
    Returns:
        str: Prompt formatado para o LLM
    """
    correlations_text = "\n".join([
        f"{related_coin}: {correlation:.4f}" 
        for related_coin, correlation in related_coins_data.items()
    ])
    
    prompt = f"""
    Analise a correlação entre {coin} e outras criptomoedas com base nos coeficientes de correlação abaixo.
    
    CORRELAÇÕES:
    {correlations_text}
    
    INSTRUÇÕES:
    Forneça sua análise no formato JSON, com os seguintes campos:
    - highest_correlation: símbolo da moeda com maior correlação positiva
    - lowest_correlation: símbolo da moeda com menor correlação (ou maior correlação negativa)
    - diversification_options: array com símbolos de 2-3 moedas boas para diversificação
    - cluster_analysis: identificação de clusters/grupos de moedas que se movem juntas
    - interpretation: breve interpretação dessas correlações
    
    Responda APENAS com o JSON, sem explicações adicionais.
    """
    
    return prompt