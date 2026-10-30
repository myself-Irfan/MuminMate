from django.urls import Resolver404, resolve


# CommonMiddleware's APPEND_SLASH redirect keeps a slash-less link working.
def find_url_token(path: str) -> str | None:
    candidates = [path] if path.endswith("/") else [path, f"{path}/"]
    for candidate in candidates:
        try:
            return resolve(candidate).kwargs.get("token")
        except Resolver404:
            continue
    return None
