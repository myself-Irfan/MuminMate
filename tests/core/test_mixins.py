from http import HTTPStatus

from django import forms
from django.http import HttpResponse, HttpResponseBase
from django.template.response import TemplateResponse
from django.test import RequestFactory
from django.views.generic import FormView

from core.mixins import UnprocessableFormMixin


class NameForm(forms.Form):
    name = forms.CharField()


# Never rendered: TemplateResponse renders lazily, so the template need not exist.
class NameView(UnprocessableFormMixin[NameForm], FormView[NameForm]):
    form_class = NameForm
    template_name = "unused.html"
    success_url = "/done/"


class HookedNameView(NameView):
    def form_invalid(self, form: NameForm) -> HttpResponse:
        form.add_error(None, "Hook ran.")
        return super().form_invalid(form)


def rendered_form(response: HttpResponseBase) -> NameForm:
    assert isinstance(response, TemplateResponse)
    assert response.context_data is not None
    form: NameForm = response.context_data["form"]
    return form


def test_invalid_form_returns_422_with_bound_form(rf: RequestFactory) -> None:
    response = NameView.as_view()(rf.post("/", {"name": ""}))

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert rendered_form(response).has_error("name", "required")


def test_valid_form_redirects_as_usual(rf: RequestFactory) -> None:
    response = NameView.as_view()(rf.post("/", {"name": "Irfan"}))

    assert response.status_code == HTTPStatus.FOUND
    assert response["Location"] == "/done/"


def test_view_form_invalid_hook_still_runs(rf: RequestFactory) -> None:
    response = HookedNameView.as_view()(rf.post("/", {"name": ""}))

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert rendered_form(response).non_field_errors() == ["Hook ran."]
