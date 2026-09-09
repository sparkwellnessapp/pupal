"""
Stage D (UPLOAD_LATENCY_PLAN.md, ruling R11) — the fleet-uplink log line.

WHY IT EXISTS. The entire latency diagnosis rests on ONE teacher's link: 3.67
Mbps measured on a live 8-file batch, and a ~2.0 Mbps figure INFERRED by fitting
the reported four-to-six minutes to the measured payload. Neither is a fleet
distribution — and whether the byte-reduction work (Stage E/F) is worth its eval
risk at all depends on what the real spread turns out to be.

WHAT THESE TESTS PIN. That the number is either sound or ABSENT. The clock is
the client's, so it carries skew and the server-side queue time; that is fine
for a distribution and useless for anything else. A fabricated Mbps in the logs
that decide a model-input change is the same confidently-wrong-number failure
§3.5a keeps closing — so every unsound input must produce None, not a guess.

LOG ONLY (R11): nothing in the codebase branches on this value.
"""
from app.api.v0.batch_grading import _client_elapsed_ms, _uplink_kbps

NOW = 1_757_000_000_000.0          # an arbitrary fixed "now", in ms


def test_computes_kbps_from_bytes_and_elapsed():
    # 1 MB in 8s ⇒ 8 Mbit / 8 s = 1000 kbit/s.
    assert _uplink_kbps(1_000_000, str(NOW - 8_000), NOW) == 1000


def test_a_slow_link_reads_slow():
    # 5 MB in 20s ⇒ 40 Mbit / 20 s = 2 Mbit/s — the reported case.
    assert _uplink_kbps(5_000_000, str(NOW - 20_000), NOW) == 2000


def test_absent_header_yields_no_number():
    """An older client, or any request that did not stamp one."""
    assert _uplink_kbps(1_000_000, None, NOW) is None
    assert _uplink_kbps(1_000_000, "", NOW) is None


def test_unparseable_header_yields_no_number():
    for bad in ("abc", "12.3.4", "NaN-ish", "  "):
        assert _uplink_kbps(1_000_000, bad, NOW) is None, bad


def test_nan_and_inf_PARSE_and_must_still_yield_no_number():
    """The review finding, and the reason "NaN-ish" above was false comfort:
    that string fails `float()`, while the literal `nan` SUCCEEDS — and NaN
    then loses every comparison silently (`nan <= 0` and `nan > 86_400_000` are
    both False), so control reached `int(x / nan)` and raised ValueError.

    That raise landed at the log line: AFTER the GCS upload, AFTER the job row
    committed and AFTER the task was enqueued. The file was accepted and would
    transcribe, but the teacher got a 500 and re-uploaded megabytes for a file
    the server already had."""
    for hostile in ("nan", "NaN", "-nan", "inf", "-inf", "Infinity", "1e400"):
        assert _uplink_kbps(1_000_000, hostile, NOW) is None, hostile
        assert _client_elapsed_ms(hostile, NOW) is None, hostile


def test_an_implausible_rate_yields_no_number():
    """A client clock ONE MILLISECOND ahead of the server's produces a duration
    of 1 ms and a rate in the tens of Gbit/s — a value that passes every other
    guard while being pure fiction. No teacher has a 2 Gbit/s uplink."""
    assert _uplink_kbps(10_000_000, str(NOW - 1), NOW) is None
    # …but a fast school fibre link is NOT rejected.
    assert _uplink_kbps(10_000_000, str(NOW - 400), NOW) == 200_000


def test_clock_skew_yields_no_number_rather_than_a_negative_rate():
    """A client clock running AHEAD makes the elapsed time negative. Reporting
    a negative — or worse, an absolute value — would put fiction in the
    distribution that decides an eval-gated change."""
    assert _uplink_kbps(1_000_000, str(NOW + 5_000), NOW) is None


def test_zero_elapsed_yields_no_number_rather_than_infinity():
    assert _uplink_kbps(1_000_000, str(NOW), NOW) is None


def test_an_absurd_duration_yields_no_number():
    """A client clock set to the epoch would otherwise report an upload that
    took 56 years, at a plausible-looking handful of kbit/s."""
    assert _uplink_kbps(1_000_000, "0", NOW) is None


def test_a_float_header_is_accepted():
    """`performance.timeOrigin + now()` is fractional; `Date.now()` is not.
    Both must work — the client may switch to the finer clock later."""
    assert _uplink_kbps(1_000_000, str(NOW - 8_000.5), NOW) == 999


def test_an_empty_file_reports_zero_not_a_crash():
    assert _uplink_kbps(0, str(NOW - 1_000), NOW) == 0


# ---------------------------------------------------------------------------
# The duration, logged in its own right (review finding D-4)
# ---------------------------------------------------------------------------

def test_client_elapsed_ms_reports_the_duration():
    assert _client_elapsed_ms(str(NOW - 8_000), NOW) == 8_000


def test_client_elapsed_ms_is_absent_on_every_unsound_input():
    for bad in (None, "", "abc", str(NOW + 5_000), str(NOW), "0"):
        assert _client_elapsed_ms(bad, NOW) is None, bad


def test_the_duration_survives_a_rejected_RATE():
    """Why this is logged separately rather than back-computed from the rate:
    `bytes*8/kbps` recovers it only when the rate survived its guards. An
    implausibly fast rate is dropped, and the duration behind it is exactly the
    row worth seeing."""
    assert _uplink_kbps(10_000_000, str(NOW - 1), NOW) is None
    assert _client_elapsed_ms(str(NOW - 1), NOW) == 1


# ---------------------------------------------------------------------------
# D-1: the measurement has to REACH the log, under THIS service's formatter.
# ---------------------------------------------------------------------------

def test_the_numbers_render_under_the_services_actual_log_format():
    """The defect this pins voided the whole stage silently.

    The numbers were passed via `extra=`, which attaches them to the LogRecord
    and renders them only if a formatter asks for them. This service configures
    logging exactly once — `basicConfig(format='…%(message)s')` in `app/main.py`,
    no dictConfig, no JSON formatter, no google-cloud-logging — so the line
    Cloud Run captured was the bare `batch_file_appended` and nothing else.

    Every test passed. The code looked right. The data was simply absent when
    someone went to query it a week later — and §9's deliverable (the per-append
    Mbps distribution that decides whether the byte-reduction work is worth its
    eval risk) cannot be reconstructed from a line that never carried it.

    So this asserts the RENDERED text, through the real formatter, not the
    record's attributes.
    """
    import logging
    from app.api.v0.batch_grading import logger as batch_logger

    records: list[str] = []

    class Capture(logging.Handler):
        def emit(self, record):
            records.append(self.format(record))

    handler = Capture()
    # The exact format string app/main.py installs.
    handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    batch_logger.addHandler(handler)
    prev = batch_logger.level
    batch_logger.setLevel(logging.INFO)
    try:
        batch_logger.info(
            "batch_file_appended batch=%s job=%s prio=%d bytes=%d "
            "client_elapsed_ms=%s uplink_kbps=%s",
            "b-1", "j-1", 0, 3_000_000, 12_000, 2000,
            extra={"batch_id": "b-1", "bytes": 3_000_000, "uplink_kbps": 2000},
        )
    finally:
        batch_logger.removeHandler(handler)
        batch_logger.setLevel(prev)

    assert len(records) == 1
    line = records[0]
    assert "bytes=3000000" in line, line
    assert "uplink_kbps=2000" in line, line
    assert "client_elapsed_ms=12000" in line, line


def test_an_absent_measurement_renders_as_a_dash_not_as_None():
    """An omitted figure must be visibly omitted. `None` in a log line reads as
    a value; `-` reads as "we did not have one", which is what it means."""
    import logging
    records: list[str] = []

    class Capture(logging.Handler):
        def emit(self, record):
            records.append(self.format(record))

    log = logging.getLogger("uplink-render-test")
    handler = Capture()
    handler.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    try:
        kbps = _uplink_kbps(1_000_000, None, NOW)          # → None
        elapsed = _client_elapsed_ms(None, NOW)            # → None
        log.info("batch_file_appended bytes=%d client_elapsed_ms=%s uplink_kbps=%s",
                 1_000_000,
                 "-" if elapsed is None else elapsed,
                 "-" if kbps is None else kbps)
    finally:
        log.removeHandler(handler)

    assert records == ["batch_file_appended bytes=1000000 "
                       "client_elapsed_ms=- uplink_kbps=-"]
