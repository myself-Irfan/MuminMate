from uuid import UUID

from django import template

from chats.sidebar import Sidebar, get_sidebar

register = template.Library()


# A tag, not a context processor: only pages on app_base.html pay for the query.
@register.simple_tag(takes_context=True)
def sidebar(context: template.Context) -> Sidebar:
    request = context["request"]
    match = request.resolver_match
    return get_sidebar(
        request.user,
        after=_parse_uuid(request.GET.get("after", "")),
        open_id=match.kwargs.get("public_id") if match else None,
    )


def _parse_uuid(value: str) -> UUID | None:
    try:
        return UUID(value)
    except ValueError:
        return None
