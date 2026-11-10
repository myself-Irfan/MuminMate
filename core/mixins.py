from http import HTTPStatus

from django.forms import BaseForm
from django.http import HttpResponse
from django.views.generic.edit import FormMixin


# RFC 9110 15.5.21: the request was understood but its content was refused.
class UnprocessableFormMixin[FormT: BaseForm](FormMixin[FormT]):
    def form_invalid(self, form: FormT) -> HttpResponse:
        response = super().form_invalid(form)
        response.status_code = HTTPStatus.UNPROCESSABLE_ENTITY
        return response
