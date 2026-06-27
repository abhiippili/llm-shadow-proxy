from pydantic import BaseModel


class ChatRequest(BaseModel):
    prompt: str
    user_id: str | None = None


class ChatResponse(BaseModel):
    response: str
    model: str
    request_id: str
