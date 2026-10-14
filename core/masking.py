import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import unquote_plus


class DataMasker:
    replacement = "***"
    # Matched after normalising: API-Key, api_key, apiKey -> apikey.
    sensitive_keys = frozenset(
        {
            "auth",
            "authorization",
            "bearer",
            "cookie",
            "jwt",
            # Exact only, so sort_key stays visible.
            "key",
            "otp",
            "otpcode",
            "passphrase",
            "pin",
            "pincode",
            "pwd",
            "sessionid",
            "setcookie",
            "signature",
        }
    )
    sensitive_parts = (
        "password",
        "passwd",
        "secret",
        "accesskey",
        "privatekey",
        "encryptionkey",
        "signingkey",
        "credential",
    )
    # "token", not "tokens", so prompt_tokens stays visible.
    sensitive_suffixes = ("token", "apikey")

    def mask(self, data: Any) -> Any:
        if isinstance(data, Mapping):
            return {
                key: self._redact(value) if self.is_sensitive(key) else self.mask(value)
                for key, value in data.items()
            }
        if isinstance(data, list | tuple):
            return [self.mask(item) for item in data]
        return data

    def mask_query(self, query: str) -> str:
        return "&".join(self._mask_pair(pair) for pair in query.split("&"))

    def is_sensitive(self, key: Any) -> bool:
        if not isinstance(key, str):
            return False
        name = re.sub(r"[^a-z0-9]", "", key.lower())
        return (
            name in self.sensitive_keys
            or name.endswith(self.sensitive_suffixes)
            or any(part in name for part in self.sensitive_parts)
        )

    def _redact(self, value: Any) -> Any:
        if isinstance(value, list | tuple):
            return [self.replacement] * len(value)
        return self.replacement

    def _mask_pair(self, pair: str) -> str:
        key, has_value, _ = pair.partition("=")
        if has_value and self.is_sensitive(unquote_plus(key)):
            return f"{key}={self.replacement}"
        return pair
