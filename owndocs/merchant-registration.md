# OWN Acquiring APIs - Merchant Registration (`cadastrarConveniada`)

## Overview

This endpoint is used to register a merchant (`lojista`) in the OWN Acquiring platform.

The registration process creates a commercial establishment and submits it for contract analysis.

---

## Endpoint

### Sandbox

```txt
https://acquirer-qa.own.financial/agilli/parceiro/v2/cadastrarConveniada
```

### Production

```txt
https://acquirer.own.financial/agilli/parceiro/v2/cadastrarConveniada
```

---

## HTTP Method

```http
POST
```

---

# Request Payload

## Example Request

```json
{
  "cnpj": "11111111111111",
  "cnpjCanalWL": "22222222222222",
  "cnpjOrigem": "",
  "identificadorCliente": "51802678468",
  "urlCallback": "https://www.google.com",
  "razaoSocial": "EMPRESA TESTE LTDA",
  "nomeFantasia": "EMPRESA TESTE",
  "cnae": "4679-6/01",
  "ramoAtividade": "LANCHONETES, CASAS DE CHA, DE SUCOS E SIMILARES",
  "faturamentoPrevisto": 10000,
  "email": "empresateste@gmail.com",
  "dddComercial": "83",
  "telefoneComercial": "999114785",
  "cep": "58690000",
  "logradouro": "Rua Rita Pereira De Almeida",
  "numeroEndereco": 173,
  "complemento": "Em Cima Do Mercadinho Popular",
  "bairro": "Centro",
  "municipio": "Livramento",
  "uf": "PB",
  "dddCel": "83",
  "telefoneCelular": "999999999",
  "responsavelAssinatura": "Responsavel Legal",
  "quantidadePos": 1,
  "faturamentoContratado": 10000,
  "antecipacaoAutomatica": "S",
  "taxaAntecipacao": 0,
  "tipoAntecipacao": "ROTATIVO",
  "mcc": "5814",
  "tipoContrato": "W",
  "codConfiguracao": "",
  "cnpjParceiro": "11111111111111",
  "idCesta": 834,
  "tarifacao": [
    {
      "id": 118687,
      "valor": 0
    }
  ],
  "codBanco": "001",
  "agencia": "906",
  "digAgencia": "09",
  "numConta": "785985",
  "digConta": "9",
  "protocoloCore": "",
  "hashAceite": "",
  "documentosSocios": [
    {
      "identificacao": "51802678468",
      "anexos": [
        {
          "nomeArquivo": "cpf.jpg",
          "conteudo": "BASE64_CONTENT",
          "tipo": "CPF"
        }
      ]
    }
  ],
  "anexos": [
    {
      "nomeArquivo": "contrato.pdf",
      "conteudo": "BASE64_CONTENT",
      "tipo": "TERMO_ADESAO"
    }
  ],
  "outrosMeiosCaptura": [
    {
      "meioCaptura": "ECOMMERCE"
    }
  ]
}
```

---

# Main Request Fields

## Merchant Information

| Field | Required | Description |
|---|---|---|
| `cnpj` | Yes | Merchant CPF or CNPJ. |
| `cnpjOrigem` | No | Deprecated field. Send an empty string (`""`). |
| `razaoSocial` | Yes | Merchant legal name. |
| `nomeFantasia` | Yes | Merchant trade name. |
| `cnae` | Yes | Merchant primary CNAE code. |
| `ramoAtividade` | Yes | Merchant business activity description. |
| `faturamentoPrevisto` | Yes | Expected merchant revenue. |
| `email` | Yes | Merchant email address. |

---

## Contact Information

| Field | Required | Description |
|---|---|---|
| `dddComercial` | Yes | Commercial phone DDD. |
| `telefoneComercial` | Yes | Commercial phone number. |
| `dddCel` | Yes | Mobile phone DDD. |
| `telefoneCelular` | Yes | Mobile phone number. |

---

## Address Information

| Field | Required | Description |
|---|---|---|
| `cep` | Yes | ZIP code. |
| `logradouro` | Yes | Street name. |
| `numeroEndereco` | Yes | Address number. |
| `complemento` | No | Address complement. |
| `bairro` | Yes | Neighborhood. |
| `municipio` | Yes | City. |
| `uf` | Yes | State abbreviation. |

---

## Contract Information

| Field | Required | Description |
|---|---|---|
| `responsavelAssinatura` | Yes | Legal representative responsible for signing the contract. |
| `quantidadePos` | Yes | Number of POS devices to send. |
| `faturamentoContratado` | Yes | Contracted revenue amount. |
| `tipoContrato` | Yes | Must always be `W` (White Label). |
| `cnpjParceiro` | Yes | White Label partner CNPJ. |
| `urlCallback` | No | Callback URL for registration status notifications. |

---

## Anticipation Configuration

| Field | Required | Description |
|---|---|---|
| `antecipacaoAutomatica` | Yes | Indicates whether automatic anticipation is enabled (`S` or `N`). |
| `taxaAntecipacao` | Conditional | Anticipation fee. |
| `tipoAntecipacao` | Conditional | Anticipation frequency. |

### Allowed `tipoAntecipacao` values

- `ROTATIVO`
- `SEMANAL`
- `MENSAL`
- `QUINZENAL`

---

## Merchant Category

| Field | Required | Description |
|---|---|---|
| `mcc` | Yes | Merchant Category Code (MCC). |

---

## Banking Information

| Field | Required | Description |
|---|---|---|
| `codBanco` | Yes | Bank code. |
| `agencia` | Yes | Branch number. |
| `digAgencia` | Yes | Branch check digit. |
| `numConta` | Yes | Account number. |
| `digConta` | Yes | Account check digit. |

---

# Customer Identifier Format

## `identificadorCliente`

Required format:

```txt
CNPJ_CPF/EXTERNAL_ID/NOME_OPERACAO/EMAIL/CPF/NOME_PESSOA
```

---

# Tariff Configuration

## `tarifacao`

```json
[
  {
    "id": 118687,
    "valor": 0
  }
]
```

---

# Document Types

## Shareholder Documents

- `RGFRENTE`
- `RGVERSO`
- `CPF`
- `CNH`
- `COMPROVANTE_ENDERECO`

## Contract Attachments

- `COMPROVANTE_ENDERECO`
- `CONTRATO_SOCIAL`
- `TERMO_ADESAO`

---

# Additional Capture Methods

Currently supported:

- `ECOMMERCE`

---

# Deprecated Fields

| Field | Instruction |
|---|---|
| `cnpjOrigem` | Send empty string (`""`). |
| `codConfiguracao` | Send empty string (`""`). |
| `hashAceite` | Send empty string (`""`). |

---

# Successful Response

```json
{
  "protocolo": "000000000422",
  "status": "EM ANALISE"
}
```

---

# Validation Error Response

```json
{
  "timestamp": "2025-02-06T15:02:08.694742039",
  "message": "Campo(s) obrigatório(s) inválido(s): CPF ou CNPJ inválido: cnpj!",
  "camposValidados": {
    "cnpj": "CPF ou CNPJ inválido: cnpj."
  }
}
```

---

# Related Endpoints

## Activity Lookup

```txt
/agilli/parceiro/v2/consultarAtividades
```

## Basket Lookup

```txt
/agilli/parceiro/v2/consultarCesta
```

---

# LLM Optimization Notes

- Registers merchants in OWN acquiring services.
- Requires OAuth authentication before use.
- Supports White Label integrations.
- File attachments must be Base64 encoded.
- `tipoContrato` must always be `W`.
- Deprecated fields should be sent as empty strings.
- Successful requests return a protocol number for status tracking.
