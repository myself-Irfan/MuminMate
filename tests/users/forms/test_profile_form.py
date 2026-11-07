from datetime import date, timedelta

import pytest
from django.utils import timezone

from users.forms.profile_form import ProfileFieldForm, ProfileForm


def profile_form(**values: str) -> ProfileForm:
    return ProfileForm(data={"display_name": "Irfan", "birth_date": "1996-04-17", **values})


@pytest.mark.django_db
def test_profile_form_valid_without_optional_fields() -> None:
    form = profile_form()

    assert form.is_valid()
    assert form.cleaned_data["gender"] == ""
    assert form.cleaned_data["employment_status"] == ""


@pytest.mark.parametrize("field", ["display_name", "birth_date"])
@pytest.mark.django_db
def test_profile_form_fails_when_required_field_empty(field: str) -> None:
    form = profile_form(**{field: ""})

    assert not form.is_valid()
    assert form.has_error(field, "required")


@pytest.mark.django_db
def test_profile_form_fails_when_display_name_only_spaces() -> None:
    form = profile_form(display_name="  \t")

    assert not form.is_valid()
    assert form.has_error("display_name", "required")


@pytest.mark.django_db
def test_profile_form_fails_when_birth_date_in_future() -> None:
    form = profile_form(birth_date=str(timezone.localdate() + timedelta(days=1)))

    assert not form.is_valid()
    assert form.has_error("birth_date", "birth_date_in_future")


@pytest.mark.django_db
def test_profile_form_fails_when_birth_date_before_1900() -> None:
    form = profile_form(birth_date=str(date(1899, 12, 31)))

    assert not form.is_valid()
    assert form.has_error("birth_date", "birth_date_too_early")


def test_profile_form_birth_date_picker_ends_today() -> None:
    field = str(ProfileForm()["birth_date"])

    assert 'type="date"' in field
    assert 'min="1900-01-01"' in field
    assert f'max="{timezone.localdate().isoformat()}"' in field


def test_profile_field_form_keeps_only_its_field() -> None:
    form = ProfileFieldForm(field="gender")

    assert list(form.fields) == ["gender"]


@pytest.mark.django_db
def test_profile_field_form_cleans_only_its_field() -> None:
    form = ProfileFieldForm({"gender": "female"}, field="gender")

    assert form.is_valid()
    assert form.cleaned_data == {"gender": "female"}


@pytest.mark.django_db
def test_profile_field_form_keeps_required_rule() -> None:
    form = ProfileFieldForm({"display_name": ""}, field="display_name")

    assert not form.is_valid()
    assert form.has_error("display_name", "required")
