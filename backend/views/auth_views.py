from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from backend.templates import templates

router = APIRouter(tags=["views"])


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "login.html")


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "register.html")
