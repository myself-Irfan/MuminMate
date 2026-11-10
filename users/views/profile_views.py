from http import HTTPStatus
from typing import Any

from django.contrib import messages
from django.contrib.auth.views import RedirectURLMixin
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest, HttpResponseBase
from django.shortcuts import redirect
from django.views.generic import FormView, TemplateView

from core.mixins import UnprocessableFormMixin
from users.forms.profile_form import ProfileFieldForm, ProfileForm
from users.http import AuthenticatedHttpRequest
from users.services.profile_service import ProfileService


class WelcomeView(RedirectURLMixin, UnprocessableFormMixin[ProfileForm], FormView[ProfileForm]):
    request: AuthenticatedHttpRequest
    form_class = ProfileForm
    template_name = "users/welcome.html"
    url_name = "welcome"
    next_page = "home"

    # A blank form here would overwrite the saved profile.
    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponseBase:
        if ProfileService().has_profile(self.request.user):
            return redirect(ProfileView.url_name)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        return super().get_context_data(skip_url=self.get_success_url(), **kwargs)

    def form_valid(self, form: ProfileForm) -> HttpResponse:
        ProfileService().save_profile(self.request.user, form.cleaned_data)
        return super().form_valid(form)


class ProfileView(TemplateView):
    request: AuthenticatedHttpRequest
    template_name = "users/profile.html"
    url_name = "profile"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        profile = ProfileService().get_profile(self.request.user)
        forms = {
            name: ProfileFieldForm(instance=profile, field=name) for name in ProfileForm.base_fields
        }
        return super().get_context_data(
            profile=profile, forms=forms, full_form=ProfileForm(), open_row="", **kwargs
        )

    def post(self, request: AuthenticatedHttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        profiles = ProfileService()
        profile = profiles.get_profile(request.user)
        # Rows edit a saved profile; without one, only the full form can create it.
        has_profile = profile.pk is not None
        row = request.POST.get("row", "")
        if has_profile and row not in ProfileForm.base_fields:
            return HttpResponseBadRequest()
        form = (
            ProfileFieldForm(request.POST, instance=profile, field=row)
            if has_profile
            else ProfileForm(request.POST, instance=profile)
        )
        if not form.is_valid():
            context = self.get_context_data()
            if has_profile:
                context["forms"][row] = form
                context["open_row"] = row
            else:
                context["full_form"] = form
            return self.render_to_response(context, status=HTTPStatus.UNPROCESSABLE_ENTITY)
        profiles.save_profile(request.user, form.cleaned_data)
        messages.success(request, "Your profile is saved.")
        return redirect(self.url_name)
