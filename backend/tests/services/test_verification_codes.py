"""Verification-code policy — generation, hashing, and the two guards.

Pure and clock-injected: expiry and cooldown are tested by passing a time, never
by sleeping.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.services.verification_codes import (
    CODE_LENGTH,
    CODE_TTL,
    MAX_ATTEMPTS,
    MAX_RESENDS,
    RESEND_COOLDOWN,
    AttemptVerdict,
    CodeState,
    ResendVerdict,
    expiry_from,
    generate_code,
    hash_code,
    may_attempt,
    may_resend,
    seconds_until_resend,
    verify_code,
)


NOW = datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)


def state(**over) -> CodeState:
    base = dict(
        expires_at=NOW + CODE_TTL,
        consumed_at=None,
        attempts=0,
        last_sent_at=NOW - RESEND_COOLDOWN,
        resend_count=0,
    )
    base.update(over)
    return CodeState(**base)


# --- generation --------------------------------------------------------------

def test_code_is_always_six_digits():
    for _ in range(200):
        code = generate_code()
        assert len(code) == CODE_LENGTH
        assert code.isdigit()


def test_leading_zeros_are_preserved():
    """A code that renders as '4512' is a different string from '004512' and
    would never match. Generate enough to hit the low range."""
    codes = [generate_code() for _ in range(3000)]
    assert all(len(c) == CODE_LENGTH for c in codes)


def test_codes_are_not_trivially_repeating():
    """A weak generator (a constant, a counter, a seeded PRNG) shows up here."""
    codes = {generate_code() for _ in range(300)}
    assert len(codes) > 250, "generator is not behaving like a CSPRNG"


# --- hashing -----------------------------------------------------------------

def test_hash_does_not_contain_the_code():
    code = "123456"
    assert code not in hash_code(code)


def test_hash_is_salted_so_two_users_with_one_code_differ():
    assert hash_code("123456") != hash_code("123456")


def test_verify_accepts_the_right_code_and_rejects_others():
    h = hash_code("123456")
    assert verify_code("123456", h) is True
    assert verify_code("123457", h) is False
    assert verify_code("", h) is False


def test_verify_fails_closed_on_a_corrupt_hash():
    """A damaged row must not 500 the endpoint — it must simply not match."""
    assert verify_code("123456", "not-a-bcrypt-hash") is False
    assert verify_code("123456", "") is False


# --- the attempt guard -------------------------------------------------------

def test_a_fresh_code_may_be_attempted():
    assert may_attempt(state(), NOW) is AttemptVerdict.OK


def test_expired_code_is_refused():
    assert may_attempt(state(expires_at=NOW - timedelta(seconds=1)), NOW) is AttemptVerdict.EXPIRED


def test_expiry_is_inclusive_at_the_boundary():
    """At exactly expires_at the code is over. Ten minutes means ten."""
    assert may_attempt(state(expires_at=NOW), NOW) is AttemptVerdict.EXPIRED


def test_consumed_code_is_single_use():
    assert may_attempt(state(consumed_at=NOW), NOW) is AttemptVerdict.ALREADY_USED


def test_attempts_are_capped():
    assert may_attempt(state(attempts=MAX_ATTEMPTS - 1), NOW) is AttemptVerdict.OK
    assert may_attempt(state(attempts=MAX_ATTEMPTS), NOW) is AttemptVerdict.TOO_MANY_ATTEMPTS


def test_consumption_and_expiry_outrank_the_attempt_count():
    """Order matters: a dead code must not report 'too many attempts', which
    would tell an attacker their guessing was the thing that stopped them."""
    dead = state(consumed_at=NOW, attempts=MAX_ATTEMPTS + 99)
    assert may_attempt(dead, NOW) is AttemptVerdict.ALREADY_USED


def test_naive_timestamps_are_normalized_not_crashed():
    """Values read from the DB are aware; values built in Python may not be.
    Comparing the two raises TypeError — the 2026-08-17 incident."""
    naive = state(expires_at=(NOW + CODE_TTL).replace(tzinfo=None))
    assert may_attempt(naive, NOW.replace(tzinfo=None)) is AttemptVerdict.OK


# --- the resend guard --------------------------------------------------------

def test_resend_allowed_once_the_cooldown_passed():
    assert may_resend(state(), NOW) is ResendVerdict.OK


def test_resend_blocked_inside_the_cooldown():
    fresh = state(last_sent_at=NOW - timedelta(seconds=1))
    assert may_resend(fresh, NOW) is ResendVerdict.COOLDOWN


def test_resends_are_capped():
    maxed = state(resend_count=MAX_RESENDS)
    assert may_resend(maxed, NOW) is ResendVerdict.TOO_MANY_RESENDS


def test_the_cap_outranks_the_cooldown():
    """A caller who exhausted resends is told that, not 'wait 60s' — otherwise
    the UI promises a retry that will never be allowed."""
    maxed_and_fresh = state(resend_count=MAX_RESENDS, last_sent_at=NOW)
    assert may_resend(maxed_and_fresh, NOW) is ResendVerdict.TOO_MANY_RESENDS


@pytest.mark.parametrize("elapsed,expected_max", [(0, 60), (30, 30), (59, 1), (60, 0), (120, 0)])
def test_countdown_never_goes_negative_or_promises_early(elapsed, expected_max):
    s = state(last_sent_at=NOW - timedelta(seconds=elapsed))
    remaining = seconds_until_resend(s, NOW)
    assert 0 <= remaining <= expected_max


# --- expiry helper -----------------------------------------------------------

def test_expiry_is_ten_minutes_out():
    assert expiry_from(NOW) - NOW == timedelta(minutes=10)


def test_expiry_normalizes_a_naive_input():
    assert expiry_from(NOW.replace(tzinfo=None)).tzinfo is not None
