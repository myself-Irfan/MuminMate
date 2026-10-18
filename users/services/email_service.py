from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from users.models import User


class EmailService:
    def send(
        self, *, user: User, subject: str, template_name: str, context: dict[str, object]
    ) -> None:
        mail = EmailMultiAlternatives(
            subject=subject,
            body=render_to_string(f"{template_name}.txt", context),
            to=[user.email],
        )
        mail.attach_alternative(render_to_string(f"{template_name}.html", context), "text/html")
        mail.send()
