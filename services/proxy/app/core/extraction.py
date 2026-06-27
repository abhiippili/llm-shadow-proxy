from app.core.exceptions import ExtractionError


def extract_response(llm_json: dict) -> str:
    if "response" not in llm_json:
        raise ExtractionError(f"Missing 'response' field in: {llm_json}")
    value = llm_json["response"]
    if not isinstance(value, str):
        raise ExtractionError(f"'response' field is not a string: {type(value)}")
    return value


def extract_model(llm_json: dict) -> str:
    return llm_json.get("model", "unknown")


def extract_tokens(llm_json: dict) -> int:
    return llm_json.get("tokens", 0)
