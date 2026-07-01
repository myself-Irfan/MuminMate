from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from backend.templates import templates

router = APIRouter(tags=["views"])


@router.get("/", response_class=HTMLResponse)
def chat_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "chat.html")
