# UT-Delta - Operação Cripto-Sentinela

## Objetivo do projeto

Implementar a Unidade Tática `ut-delta` com publicação de identidade,
comunicação híbrida segura, interação com o Oráculo e revogação de unidades.
O projeto foi mantido simples e compatível com os formatos já usados pelo
Laboratório 02.

## Contexto do Laboratório 02 - Operação Cripto-Sentinela

As Unidades Táticas trocam chaves públicas e mensagens por um broker MQTT.
Cada UT possui uma identidade RSA/ECDSA. O Oráculo valida a integração por
echo, envia desafios criptografados e publica o placar de notas.

## Arquitetura geral

- `main.py`: cliente MQTT, menu, persistência das chaves confiadas,
  processamento das mensagens e integração com o Oráculo.
- `crypto_utils.py`: geração e serialização de chaves, envelope híbrido
  RSA/AES-GCM, assinatura ECDSA e assinatura canônica de objetos JSON.
- `minhas_chaves.json`: chaves privadas RSA e ECDSA da `ut-delta`.
- `chaves_confiadas.json`: chaves públicas recebidas de outras unidades.
- `unidades_revogadas.json`: lista local persistente de unidades revogadas.
- `test_crypto_local.py`: teste criptográfico isolado, sem MQTT.

O envelope seguro gera uma chave AES-256 por mensagem, cifra a mensagem com
AES-GCM, cifra somente a chave de sessão com RSA-OAEP/SHA-256 e assina o texto
original com ECDSA/SHA-256. Os campos existentes do pacote seguro não foram
alterados.

## Dependências

- Python 3
- `cryptography`
- `paho-mqtt`

## Instalação

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Em sistemas nos quais o executável se chama `python3`, substitua `python` por
`python3`.

## Como executar

```bash
source .venv/bin/activate
python main.py
```

O programa carrega `minhas_chaves.json` e `chaves_confiadas.json`, conecta-se
a `broker.hivemq.com:1883`, inicia as inscrições MQTT e exibe o menu.

## Opções do menu

1. Gerar novas chaves RSA/ECDSA e salvar em `minhas_chaves.json`.
2. Publicar a identidade da `ut-delta`.
3. Enviar echo criptografado ao Oráculo.
4. Solicitar desafio ao Oráculo.
5. Enviar mensagem segura para outra UT.
6. Listar chaves confiadas e unidades revogadas.
7. Preparar e, após confirmação, publicar uma revogação assinada.
8. Solicitar atualização e receber a consulta de notas.
9. Encerrar o cliente.

Gerar novas chaves muda a identidade criptográfica da UT.

## Publicação de identidade

A opção 2 publica com `retain=True` em:

```text
sisdef/broadcast/chaves/ut-delta
```

Formato preservado:

```json
{
  "id_unidade": "ut-delta",
  "chave_publica_rsa": "...",
  "chave_publica_ecdsa": "..."
}
```

## Recebimento de chaves públicas

A UT assina `sisdef/broadcast/chaves/#`. Pacotes válidos são normalizados para
minúsculas e persistidos em `chaves_confiadas.json`. Por compatibilidade,
também é aceito o nome legado `chave_publica_eddsa` quando seu conteúdo é a
chave ECDSA. Uma chave publicada por unidade já revogada é ignorada.

O recebimento de uma chave não prova, por si só, a identidade do publicador.
Em ambiente real seria necessário um mecanismo de certificação ou verificação
fora de banda.

## Envio de mensagem segura

A opção 5 exige a chave pública do destino. O pacote mantém os campos:

```text
id_unidade
ciphertext_b64
tag_autenticacao_b64
nonce_b64
chave_sessao_cifrada_b64
assinatura_b64
cmd (quando aplicável)
```

Para outra UT, o tópico é `sisdef/direto/<destino>`. Para o Oráculo, permanece
`sisdef/direto/oraculo`.

## Recebimento e validação de mensagem segura

Mensagens diretas chegam em `sisdef/direto/ut-delta`. Antes da abertura, o
remetente precisa ter chave ECDSA confiada e não pode constar na lista de
revogadas. A chave AES é recuperada por RSA-OAEP, o AES-GCM valida e decifra o
conteúdo e, por fim, a assinatura ECDSA do texto é verificada. Qualquer falha
interrompe o processamento.

## Interação com o Oráculo: echo

A opção 3 envia a mensagem `echo-ut-delta` no pacote seguro existente, com
`cmd` igual a `echo`. A resposta é aberta pelo mesmo fluxo criptográfico. As
frases de confirmação já reconhecidas pelo código foram preservadas.

## Desafio do Oráculo: desafio e resposta

A opção 4 envia ao Oráculo, sem alterar o formato esperado:

```json
{
  "id_unidade": "ut-delta",
  "cmd": "desafio"
}
```

A pergunta recebida é aberta como mensagem segura. O código resolve os
formatos matemáticos suportados e envia a resposta pelo pacote seguro
existente, com `cmd` igual a `resposta`. Se não conseguir resolver, não envia
uma resposta potencialmente errada.

## Consulta de notas

A opção 8 publica `{"cmd": "atualizar_notas"}` em
`sisdef/broadcast/notas`. Mensagens recebidas nesse tópico são exibidas como
JSON. Esse fluxo não foi alterado.

## Revogação de unidade

O formato recomendado para a apresentação é:

```json
{
  "remetente": "ut-delta",
  "revogacao": {
    "unidade_revogada": "ut-charlie",
    "timestamp": "2026-06-09T00:00:00Z"
  },
  "assinatura_b64": "..."
}
```

O objeto interno `revogacao` é serializado com chaves ordenadas e separadores
compactos, equivalente a:

```python
json.dumps(revogacao, sort_keys=True, separators=(",", ":")).encode("utf-8")
```

A opção 7 assina esse objeto com a chave ECDSA privada da `ut-delta`, mostra o
pacote preparado e pede confirmação explícita antes de publicar em
`sisdef/broadcast/revogacao`. Responder algo diferente de `s` ou `sim` cancela
a publicação.

Ao receber o formato assinado, a UT procura a chave ECDSA confiada do
remetente, valida a assinatura e somente então aplica a revogação. Uma
revogação válida:

- inclui a unidade em `unidades_revogadas.json`;
- remove sua entrada de `chaves_confiadas.json`;
- impede que novas chaves dessa unidade sejam aceitas;
- rejeita mensagens diretas futuras dessa unidade.

O formato simples legado `{"id_unidade": "ut-charlie"}` continua aceito para
compatibilidade com o laboratório. Ele não possui assinatura e, portanto,
deve ser tratado como legado e inseguro.

## Limitações conhecidas

- O broker MQTT público opera sem TLS e sem autenticação.
- As chaves privadas estão versionadas por decisão do contexto de laboratório.
- `id_unidade` e `cmd` não são dados associados do AES-GCM nem fazem parte da
  assinatura atual; alterar isso quebraria o formato compatível com o Oráculo.
- A confiança inicial depende das chaves públicas recebidas via broadcast.
- O formato simples legado de revogação não pode ser autenticado.
- O timestamp da revogação assinada é registrado e assinado, mas ainda não há
  política de expiração, janela de tempo ou prevenção de replay.
- Não há autoridade certificadora, rotação formal de chaves ou recuperação de
  uma revogação aplicada.

## Roteiro de Demonstração

1. Ative o ambiente virtual com `source .venv/bin/activate`.
2. Instale as dependências com `python -m pip install -r requirements.txt`.
3. Rode `python main.py`.
4. Use a opção 2 para publicar as chaves públicas da UT.
5. Use a opção 6 para listar as chaves confiadas.
6. Use a opção 5 para enviar uma mensagem segura para outra UT.
7. No terminal da destinatária, mostre o recebimento, a validação e o texto
   decifrado.
8. Use a opção 3 para solicitar echo ao Oráculo.
9. Use a opção 4 para solicitar o desafio ao Oráculo.
10. Mostre a pergunta criptografada sendo recebida e aberta.
11. Mostre o cálculo e o envio automático da resposta segura.
12. Use a opção 8 para consultar as notas e exibir o placar.
13. Use a opção 7, informe a unidade, confira o JSON assinado e confirme a
    publicação somente durante a demonstração.
14. Tente receber mensagem da unidade revogada e mostre a rejeição antes da
    decriptação.
15. Em outro terminal, rode `python test_crypto_local.py` e mostre a rejeição
    de ciphertext, tag AES-GCM, nonce, assinatura e chave de sessão cifrada
    adulterados.

Para evitar publicação acidental, prepare previamente quais IDs e mensagens
serão usados. Fora da apresentação, cancele a confirmação da opção 7.

## Defesa Técnica

### Por que usar AES-GCM

AES é eficiente para dados de tamanho arbitrário. O modo GCM oferece
criptografia autenticada: além de esconder o conteúdo, produz uma tag que
detecta alterações no ciphertext. O nonce de 12 bytes deve ser único para cada
uso da mesma chave; o projeto gera chave e nonce novos por mensagem.

### Por que RSA cifra apenas a chave de sessão AES

RSA é adequado para encapsular um segredo pequeno, aqui a chave AES de 256
bits. RSA-OAEP com SHA-256 permite que apenas o detentor da chave RSA privada
recupere essa chave de sessão.

### Por que não cifrar a mensagem inteira com RSA

RSA tem limite de tamanho por operação, é mais lento e não foi projetado para
cifrar grandes volumes diretamente. O modelo híbrido combina a eficiência do
AES com a distribuição de chave oferecida pelo RSA.

### Por que usar ECDSA

ECDSA fornece assinatura digital com chaves menores e boa eficiência. A chave
privada assina e a chave pública correspondente verifica. Neste projeto é
usada a curva `secp256r1` com SHA-256.

### Hash, HMAC e assinatura digital

- Hash simples gera um resumo e detecta mudanças quando o valor esperado vem
  por um canal confiável, mas qualquer pessoa pode recalculá-lo.
- HMAC usa um segredo compartilhado para autenticar dados. Todos que conhecem
  o segredo podem gerar a mesma autenticação, então não distingue autores.
- Assinatura digital usa uma chave privada para assinar e uma chave pública
  para verificar, permitindo atribuir a assinatura ao controlador da chave
  privada.

### Confidencialidade

A mensagem é cifrada com AES-256-GCM. A chave AES é cifrada com a chave RSA
pública do destino; somente a chave RSA privada correspondente deve recuperá-la.

### Integridade

A tag do AES-GCM detecta alteração no ciphertext, no nonce efetivo ou na chave
usada para abrir o pacote. A assinatura ECDSA também detecta alteração no
texto após a decriptação.

### Autenticidade

A assinatura é validada com a chave ECDSA pública associada ao remetente. A
garantia depende de essa associação ter sido estabelecida de forma confiável.

### Não repúdio

ECDSA oferece evidência de que a chave privada correspondente produziu a
assinatura. A solução busca não repúdio, mas a garantia operacional depende de
custódia exclusiva da chave privada, identidade verificada e trilhas de
auditoria. Como as chaves privadas são versionadas no laboratório, essa
garantia é limitada neste ambiente.

### Como funciona a revogação

A revogação recomendada assina canonicamente unidade e timestamp. O receptor
valida a assinatura do remetente antes de persistir a unidade revogada,
remover a chave confiada e bloquear mensagens futuras. A compatibilidade com
o formato simples foi preservada, embora sem a mesma segurança.

## Teste local sem MQTT

```bash
python test_crypto_local.py
```

O script gera chaves temporárias somente em memória, monta e abre um pacote,
testa o resolvedor e exige falha para cada adulteração. Ele importa somente
funções de `main.py`; não inicia o cliente, não conecta ao broker, não publica
MQTT e não depende do Oráculo.
