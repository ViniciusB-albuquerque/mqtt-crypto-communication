# Operação Cripto-Sentinela — Desafio do Oráculo

Este documento resume o protocolo esperado pelo Oráculo na avaliação prática da Operação Cripto-Sentinela.

Fonte original: documento `desafio_oraculo.pdf`.

## Objetivo

Testar o ciclo completo de comunicação segura entre uma Unidade Tática (UT) e o Oráculo.

A UT deve:

1. Solicitar um desafio ao Oráculo.
2. Receber uma pergunta criptografada.
3. Verificar a autenticidade da mensagem.
4. Decifrar a pergunta.
5. Calcular a resposta.
6. Enviar a resposta de volta de forma segura.

O fluxo deve garantir:

- confidencialidade;
- integridade;
- autenticidade.

## Identificador da unidade

A unidade deste projeto é:

```text
ut-delta
```

Não alterar `ID_UNIDADE`.

## Passo 1 — Solicitar desafio

Publicar no tópico:

```text
sisdef/direto/oraculo
```

Payload:

```json
{
  "id_unidade": "ut-delta",
  "cmd": "desafio"
}
```

O campo `id_unidade` deve estar em letras minúsculas.

## Passo 2 — Receber e decifrar pergunta

O Oráculo responde no tópico direto da unidade:

```text
sisdef/direto/ut-delta
```

A mensagem recebida segue o formato de pacote seguro.

A ordem correta de processamento é:

1. Verificar a assinatura do Oráculo.
2. Decifrar a chave de sessão com a chave RSA privada da UT.
3. Decifrar a mensagem com AES-GCM usando a chave de sessão.
4. Extrair a pergunta.
5. Calcular a resposta.

Exemplo de pergunta:

```text
Qual o valor de log2(4096)? Responda apenas com o numero.
```

Resposta esperada:

```text
12
```

## Passo 3 — Formatar resposta

A resposta criptografada deve conter apenas a string do número.

Correto:

```text
"12"
```

Incorreto:

```json
{ "resposta": "12" }
```

Não usar JSON como conteúdo cifrado da resposta.

## Passo 4 — Criptografar e assinar resposta

Para responder ao Oráculo:

1. Gerar nova chave de sessão AES.
2. Cifrar apenas a string da resposta com AES-GCM.
3. Cifrar a chave de sessão com a chave pública RSA do Oráculo.
4. Assinar a string da resposta com a chave privada ECDSA da UT.

## Passo 5 — Publicar resposta

Publicar no tópico:

```text
sisdef/direto/oraculo
```

O pacote final deve incluir obrigatoriamente:

```json
{
  "id_unidade": "ut-delta",
  "cmd": "resposta",
  "ciphertext_b64": "...",
  "tag_autenticacao_b64": "...",
  "nonce_b64": "...",
  "chave_sessao_cifrada_b64": "...",
  "assinatura_b64": "..."
}
```

O campo abaixo é obrigatório:

```json
"cmd": "resposta"
```

Sem esse campo, o Oráculo rejeita a mensagem e pode haver penalidade.

## Comandos disponíveis no Oráculo

### Echo

Testa conexão e decriptografia sem desafio ativo.

```json
{
  "cmd": "echo"
}
```

### Desafio

Solicita uma nova pergunta.

```json
{
  "cmd": "desafio"
}
```

### Resposta

Envia resposta ao desafio ativo.

```json
{
  "cmd": "resposta"
}
```

## Sistema de pontuação

Todas as unidades começam com 10 pontos.

A unidade perde pontos apenas quando o Oráculo não consegue processar a mensagem.

Erros que geram penalidade:

- falha na decriptografia;
- assinatura inválida;
- formato incorreto do pacote.

Penalidades:

| Erro | Penalidade |
|---|---:|
| 1º erro de mensagem | -0,2 |
| 2º erro de mensagem | -0,3 |
| 3º erro de mensagem | -0,4 |
| 4º erro em diante | -0,5 por erro |

Erro matemático não gera penalidade de implementação. Se a resposta numérica estiver errada, o erro é registrado, mas não reduz a nota por falha de processamento.

## Passo 6 — Consultar notas

Para consultar notas, publicar no tópico:

```text
sisdef/broadcast/notas
```

Payload:

```json
{
  "cmd": "atualizar_notas"
}
```

O Oráculo publica o placar no mesmo tópico:

```text
sisdef/broadcast/notas
```

A mensagem fica retida com flag `retain`, então pode ser lida ao se inscrever no tópico.

## Cuidados para não quebrar compatibilidade

- Não alterar `ID_UNIDADE`.
- Não alterar o formato do pacote seguro.
- Não enviar resposta como JSON cifrado.
- A resposta cifrada deve ser somente a string numérica.
- Manter `"cmd": "resposta"` no envelope externo.
- Verificar a assinatura do Oráculo antes de processar a pergunta.
- Usar RSA apenas para cifrar a chave de sessão.
- Usar AES-GCM para cifrar o conteúdo.
- Usar ECDSA para assinar o conteúdo da resposta.
- Não publicar MQTT automaticamente sem confirmação quando for uma ação sensível.

## Resumo operacional para implementação

### Solicitar desafio

```json
{
  "id_unidade": "ut-delta",
  "cmd": "desafio"
}
```

Tópico:

```text
sisdef/direto/oraculo
```

### Responder desafio

Conteúdo cifrado:

```text
"12"
```

Envelope externo:

```json
{
  "id_unidade": "ut-delta",
  "cmd": "resposta",
  "ciphertext_b64": "...",
  "tag_autenticacao_b64": "...",
  "nonce_b64": "...",
  "chave_sessao_cifrada_b64": "...",
  "assinatura_b64": "..."
}
```

Tópico:

```text
sisdef/direto/oraculo
```

### Consultar notas

```json
{
  "cmd": "atualizar_notas"
}
```

Tópico:

```text
sisdef/broadcast/notas
```

## Frase do documento original

> “Onde o código é sua arma e a criptografia, sua defesa.”
