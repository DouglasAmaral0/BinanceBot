Bot para compra e venda de Moedas da Binance
Está em fase de Testes, a taxa de RSI, tamanho do Lote e Regras de Histórico precisam ser aperfeiçoadas

Instale as dependências listadas em `requirements.txt` e crie um arquivo `.env`
baseado em `.env.example` com suas chaves de API.

Esse projeto inicialmenete será integrado a um serviço de assistente pessoal, não é necessário a configuração do Sistema e do OS

## Mensagens de falha

O bot registra mensagens de erro sempre que ocorrem problemas ao acessar as APIs
(Binance, Reddit ou News API). Exemplos de mensagens:

- `Falha ao conectar ao Reddit: ...`
- `Erro ao verificar News API: ...`
- `Conexão com Binance perdida: ...`

Essas mensagens ajudam a diagnosticar rapidamente problemas de rede ou de
autenticação.

