from typing import Any

from django.contrib.auth.decorators import login_not_required
from django.http import HttpRequest, HttpResponse, HttpResponseBase
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.generic import FormView

from users.forms import SignupForm
from users.services.user_service import UserService


@method_decorator(login_not_required, name="dispatch")
class SignupView(FormView[SignupForm]):
    form_class = SignupForm
    template_name = "registration/signup.html"
    url_name = "signup"
    success_url = reverse_lazy("signup_done")

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponseBase:
        if request.user.is_authenticated:
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form: SignupForm) -> HttpResponse:
        UserService().signup(
            email=form.cleaned_data["email"], password=form.cleaned_data["password1"]
        )
        return super().form_valid(form)
