# The sidebar shows about 30 characters; the page heading and tab title show more.
def make_title(content: str, limit: int = 60) -> str:
    text = " ".join(content.split())
    if len(text) <= limit:
        return text
    words = text[: limit + 1].rsplit(" ", 1)[0]
    return f"{words if len(words) <= limit else text[:limit]}\N{HORIZONTAL ELLIPSIS}"
