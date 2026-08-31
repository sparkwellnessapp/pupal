"""
Secrets must never appear in a repr.

Found 2026-08-31: any `AttributeError` on `settings` makes pydantic render the
WHOLE model, so a one-line typo printed the OpenAI, Anthropic and xAI keys, the
Supabase password, the LangSmith key and a base64 service-account key into the
test output. That output goes to CI logs, and **both git remotes are public**.

The rule this file enforces is about the OUTCOME, not the mechanism: no secret
value may appear in `repr(settings)` or `str(settings)`. Credentials use
`SecretStr` (which also masks interpolation); the database URLs use
`Field(repr=False)` because they are consumed as connection strings with string
operations at 14 sites, where `.get_secret_value()` noise buys nothing this test
does not already guarantee.

NOTE for whoever edits this file: assertions here name the FIELD, never the
value. A test that prints the secret it is protecting has defeated itself.
"""
from __future__ import annotations

import pytest

# Every field whose value is a credential. Adding a secret to config.py without
# adding it here is the failure mode this list exists to prevent — see
# `test_no_unlisted_secret_shaped_field_escapes_the_policy` below.
SECRET_FIELDS = (
    "openai_api_key",
    "anthropic_api_key",
    "xai_api_key",
    "langchain_api_key",
    "supabase_access_token",
    "gmail_service_account_json",
    "internal_task_token",
    "database_url",
    "test_database_url",
)


def _plain(value) -> str:
    """The underlying string, whatever wrapper it wears."""
    if value is None:
        return ""
    return value.get_secret_value() if hasattr(value, "get_secret_value") else str(value)


@pytest.mark.parametrize("field", SECRET_FIELDS)
def test_secret_never_appears_in_the_settings_repr(field):
    from app.config import settings

    value = _plain(getattr(settings, field, None))
    if len(value) < 8:
        pytest.skip(f"{field} is unset in this environment")

    rendered = repr(settings) + str(settings)
    assert value not in rendered, (
        f"{field} leaks its value into repr(settings) — an AttributeError "
        f"anywhere near settings would print it to the logs")


def test_no_unlisted_secret_shaped_field_escapes_the_policy():
    """A new key added to config.py must not quietly bypass this.

    Matches on NAME, because that is what a new secret has in common with the
    old ones — a value-shaped heuristic would either miss or false-positive on
    every model id and bucket name in the file.
    """
    from app.config import settings

    # extras too: `extra = "allow"` is how five credentials got in undeclared
    # and into the repr in the first place.
    names = set(type(settings).model_fields) | set(
        getattr(settings, "__pydantic_extra__", None) or {})

    suspicious = []
    for name in sorted(names):
        # `*_file` fields are PATHS (config/token.json), not secrets
        if name.endswith("_file") or name in SECRET_FIELDS:
            continue
        if not any(k in name for k in ("api_key", "secret", "token", "password",
                                       "credentials_json", "service_account")):
            continue
        value = _plain(getattr(settings, name, None))
        if len(value) >= 8 and value in repr(settings):
            suspicious.append(name)

    assert not suspicious, (
        f"secret-shaped settings fields are not covered by the repr policy: "
        f"{suspicious} — add them to config.py's protection and to SECRET_FIELDS")


def test_credentials_are_secretstr_so_interpolation_masks_them():
    """`repr=False` hides a field from the model repr; `SecretStr` also masks it
    when someone f-strings the field itself. Credentials get both."""
    from pydantic import SecretStr

    from app.config import settings

    for field in ("openai_api_key", "anthropic_api_key", "internal_task_token"):
        value = getattr(settings, field, None)
        if value is None or not _plain(value):
            continue
        assert isinstance(value, SecretStr), f"{field} is not a SecretStr"
        assert _plain(value) not in f"{value}", (
            f"{field} renders its value under interpolation")
