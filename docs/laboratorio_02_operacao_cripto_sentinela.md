# Laboratório 02 — Operação Cripto-Sentinela

Este documento organiza a descrição geral do Laboratório 02 da disciplina Tecnologias de Registro Distribuído — DLT.

O objetivo é servir como referência para leitura por ferramentas como Codex, agentes de implementação e documentação do projeto.

## Contexto

Neste laboratório, o conhecimento teórico de criptografia construído em sala de aula é aplicado em um cenário prático chamado **Operação Cripto-Sentinela**.

Os estudantes deixam de atuar apenas como alunos e passam a representar membros do **Comando de Defesa Cibernética (CDCiber)**.

A missão é proteger um sistema de comunicação contra uma ameaça cibernética, aplicando conceitos de:

- chaves assimétricas;
- RSA;
- ECDSA;
- criptografia simétrica;
- AES-GCM;
- hashing;
- assinaturas digitais;
- comunicação segura;
- revogação de unidades.

O documento completo do laboratório foi disponibilizado pelo professor no GitHub:

```text
https://github.com/ccufcg/dlt-operacao-crypto-sentinela
```

## Missão da Unidade Tática

Cada grupo implementa uma **Unidade Tática (UT)**.

A UT deve construir um protocolo de comunicação seguro capaz de garantir:

- **Confidencialidade** contra espionagem;
- **Integridade** contra manipulação de dados;
- **Autenticidade** para confirmar a identidade dos aliados.

## Tecnologias e conceitos esperados

A implementação deve usar os conceitos vistos em sala de aula:

### RSA

Usado no contexto de criptografia assimétrica.

No laboratório, RSA deve ser usado principalmente para proteger a **chave de sessão AES**, e não para cifrar mensagens inteiras.

Uso esperado:

1. Gerar uma chave de sessão AES.
2. Cifrar a mensagem com AES-GCM.
3. Cifrar a chave de sessão com a chave pública RSA do destinatário.
4. O destinatário usa sua chave privada RSA para recuperar a chave de sessão.

### AES-GCM

Usado como criptografia simétrica autenticada.

Deve proteger o conteúdo da mensagem com:

- confidencialidade;
- integridade;
- autenticação do ciphertext por meio da tag de autenticação.

Campos típicos relacionados:

```text
ciphertext_b64
tag_autenticacao_b64
nonce_b64
```

### ECDSA

Usado para assinatura digital.

Deve garantir:

- autenticidade do remetente;
- integridade do conteúdo assinado;
- não repúdio no contexto do laboratório.

Campos típicos relacionados:

```text
assinatura_b64
chave_publica_ecdsa
```

### Hashing

Usado como base conceitual para integridade, assinaturas, fingerprints e autenticação.

Importante: hash simples não substitui assinatura digital. Hash simples ajuda na integridade, mas não prova sozinho quem gerou a mensagem.

## Entregas e pesos

A avaliação é dividida em três entregas, todas importantes para a nota final.

## Entrega 1 — Código-fonte funcional

Peso: **20%**

O grupo deve submeter o código-fonte funcional da sua Unidade Tática.

A UT deve ser capaz de realizar as operações descritas no documento do laboratório:

- gerar chaves;
- publicar identidade;
- enviar mensagens seguras;
- receber mensagens seguras;
- processar revogação de outras unidades.

Submissão via formulário indicado pelo professor.

## Entrega 2 — Desafio do Oráculo

Peso: **30%**

A UT deve interagir com o Oráculo.

Observação: o texto original fornecido estava incompleto nesta seção, mas o fluxo detalhado está documentado no arquivo específico:

```text
docs/desafio_oraculo.md
```

Resumo esperado do desafio:

1. Solicitar um desafio ao Oráculo.
2. Receber uma pergunta criptografada.
3. Verificar a assinatura do Oráculo.
4. Decifrar a chave de sessão com a chave RSA privada da UT.
5. Decifrar a pergunta usando AES-GCM.
6. Calcular a resposta.
7. Enviar a resposta de volta ao Oráculo como pacote seguro.
8. Garantir que o campo externo `cmd` esteja correto.

Comandos relevantes:

```json
{
  "cmd": "echo"
}
```

```json
{
  "cmd": "desafio"
}
```

```json
{
  "cmd": "resposta"
}
```

Tópico principal do Oráculo:

```text
sisdef/direto/oraculo
```

## Entrega 3 — Apresentação em cenário simulado e defesa técnica

Peso: **50%**

Na data da entrega, haverá uma simulação ao vivo em laboratório.

Cada Unidade Tática deverá demonstrar seu sistema funcionando em tempo real, por meio de uma dinâmica guiada.

Durante a apresentação, cada UT será questionada sobre as tecnologias utilizadas na operação.

As perguntas podem abordar:

- usos dos algoritmos;
- limitações dos algoritmos;
- decisões de implementação;
- por que AES-GCM foi escolhido;
- por que usar ECDSA;
- por que não usar apenas HMAC;
- implicações de segurança de cada escolha;
- confidencialidade;
- integridade;
- autenticidade;
- não repúdio;
- revogação;
- riscos do broker MQTT público.

O professor indicou que novas especificações poderiam ser entregues durante a dinâmica.

## Requisitos práticos da UT

A Unidade Tática deve implementar ou preservar funcionalidades como:

- geração de chaves locais;
- armazenamento das chaves privadas da própria UT;
- publicação de identidade;
- recebimento e salvamento de chaves públicas confiadas;
- envio de mensagem segura;
- recebimento de mensagem segura;
- validação de assinatura;
- decifragem de mensagens;
- interação com o Oráculo;
- comando `echo`;
- comando `desafio`;
- comando `resposta`;
- consulta de notas;
- revogação de unidade;
- rejeição de mensagens vindas de unidades revogadas.

## Cuidados de compatibilidade

Para não quebrar a comunicação com o Oráculo, evitar alterações nos seguintes pontos:

- Não alterar `ID_UNIDADE`.
- Não alterar os tópicos MQTT esperados pelo laboratório.
- Não alterar o formato dos pacotes seguros.
- Não alterar o fluxo de `echo`.
- Não alterar o fluxo de `desafio`.
- Não alterar o fluxo de `resposta`.
- Não enviar resposta ao desafio como JSON cifrado.
- No desafio, a resposta cifrada deve ser apenas a string numérica.
- Não remover os arquivos locais de chaves sem autorização.
- Não publicar mensagens MQTT automaticamente sem confirmação explícita em ações sensíveis.
- Não fazer refatorações grandes perto da entrega.

## Modelo conceitual da comunicação segura

Fluxo típico de envio seguro:

1. Remetente monta o conteúdo da mensagem.
2. Remetente gera uma chave de sessão AES.
3. Remetente cifra o conteúdo com AES-GCM.
4. Remetente cifra a chave de sessão AES com a chave pública RSA do destinatário.
5. Remetente assina o conteúdo com sua chave privada ECDSA.
6. Remetente publica o pacote no tópico MQTT adequado.
7. Destinatário recebe o pacote.
8. Destinatário verifica a assinatura com a chave pública ECDSA do remetente.
9. Destinatário decifra a chave de sessão com sua chave privada RSA.
10. Destinatário decifra o conteúdo com AES-GCM.
11. Destinatário processa a mensagem.

## Modelo de pacote seguro

O pacote seguro deve seguir a estrutura esperada pelo laboratório.

Exemplo genérico:

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

Dependendo do tipo de mensagem, o campo `cmd` pode não existir ou pode assumir valores específicos exigidos pelo Oráculo.

Para o desafio do Oráculo, `cmd: "resposta"` é obrigatório no envelope externo da resposta.

## Defesa técnica esperada

Durante a apresentação, a UT deve saber explicar:

### Por que AES-GCM?

Porque AES-GCM fornece criptografia autenticada.

Ele protege a confidencialidade do conteúdo e também detecta adulterações por meio da tag de autenticação.

### Por que RSA?

Porque RSA permite que a chave de sessão AES seja protegida usando a chave pública do destinatário.

RSA não deve ser usado para cifrar mensagens grandes diretamente. O uso correto no laboratório é cifrar a chave de sessão.

### Por que ECDSA?

Porque ECDSA fornece assinatura digital.

Ela permite verificar quem enviou a mensagem e se o conteúdo foi alterado.

### Por que não apenas HMAC?

HMAC é útil quando as partes compartilham uma chave secreta.

No cenário da operação, as UTs usam chaves públicas e privadas para autenticação. A assinatura digital permite autenticação sem segredo compartilhado entre todas as unidades.

Além disso, assinatura digital oferece uma noção de não repúdio no contexto do laboratório.

### Qual a limitação do MQTT público?

O broker MQTT público não garante, por si só:

- confidencialidade;
- autenticação forte do canal;
- controle de quem publica;
- proteção contra spoofing de identidade;
- proteção contra replay.

Por isso, a segurança precisa estar na camada da aplicação.

## Checklist para entrega

Antes de apresentar, validar:

```bash
python -m pip install -r requirements.txt
python -m py_compile main.py crypto_utils.py test_crypto_local.py
python test_crypto_local.py
git diff --check
git status
```

Também testar manualmente:

- publicar identidade;
- listar chaves confiadas;
- enviar mensagem segura;
- receber mensagem segura;
- testar `echo`;
- solicitar `desafio`;
- responder `desafio`;
- consultar notas;
- revogar unidade;
- rejeitar unidade revogada;
- verificar adulterações com teste local.

## Relação com outros documentos

Este documento descreve a visão geral do laboratório e das entregas.

Documentos complementares recomendados em `docs/`:

```text
docs/desafio_oraculo.md
```

Contém o protocolo específico do Desafio do Oráculo.

```text
README.md
```

Contém instruções de instalação, execução, demonstração e defesa técnica do projeto.

## Regra principal para manutenção do código

Preservar o fluxo funcional atual.

Alterações devem ser pequenas, rastreáveis e compatíveis com o Oráculo.
