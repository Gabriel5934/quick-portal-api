import requests

BRASIL_API_CNPJ_URL = "https://brasilapi.com.br/api/cnpj/v1/{cnpj}"


class BrasilApiError(Exception):
    def __init__(self, message, status_code=None, response_body=None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


def fetch_cnpj_info(cnpj: str) -> dict:
    url = BRASIL_API_CNPJ_URL.format(cnpj=cnpj)

    try:
        response = requests.get(url, timeout=15)
    except requests.RequestException as exc:
        raise BrasilApiError(f"Connection error: {exc}") from exc

    if response.status_code != 200:
        raise BrasilApiError(
            f"Brasil API returned status {response.status_code}",
            status_code=response.status_code,
            response_body=response.text,
        )

    data = response.json()
    cnae_fiscal = data.get("cnae_fiscal")
    if cnae_fiscal is None:
        raise BrasilApiError(
            "Brasil API response missing 'cnae_fiscal'",
            status_code=response.status_code,
            response_body=response.text,
        )
    return {
        "cod_cnae": str(cnae_fiscal),
        "trade_name": data.get("nome_fantasia") or "",
        "name": data.get("razao_social") or "",
    }
