from typing import Any

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.views.generic import TemplateView

from core.exceptions import ProblemError
from users.exceptions import (
    EmailChangeLinkForOtherAccountError,
    EmailTakenError,
    InvalidEmailChangeLinkError,
)
from users.http import AuthenticatedHttpRequest
from users.services.email_change_service import EmailChangeService


class EmailChangeConfirmView(TemplateView):
    request: AuthenticatedHttpRequest
    template_name = "users/email_change_confirm.html"
    refused_template_name = "users/email_change_invalid.html"
    url_name = "email_change_confirm"

    # TemplateView types get()'s request as HttpRequest; self.request carries the narrowed type.
    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        try:
            new_email = EmailChangeService().get_new_email(self.request.user, kwargs["token"])
        except (InvalidEmailChangeLinkError, EmailChangeLinkForOtherAccountError) as error:
            return self._refuse(error)
        return self.render_to_response(self.get_context_data(new_email=new_email))

    def post(self, request: AuthenticatedHttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        try:
            EmailChangeService().confirm(request.user, kwargs["token"])
        except (
            InvalidEmailChangeLinkError,
            EmailChangeLinkForOtherAccountError,
            EmailTakenError,
        ) as error:
            return self._refuse(error)
        messages.success(request, f"Your email is now {request.user.email}.")
        return redirect("account_settings")

    def _refuse(self, error: ProblemError) -> HttpResponse:
        return TemplateResponse(
            self.request, self.refused_template_name, {"message": error.detail}, status=error.status
        )
