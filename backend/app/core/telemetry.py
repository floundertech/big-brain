# Holds OTel histograms created during _init_tracing().
# Using a shared module avoids circular imports between main.py and services/claude.py
# while also bypassing the global OTel metrics API (which Traceloop may override).
_token_usage_histogram = None
_operation_duration_histogram = None
_pii_scrub_counter = None


def set_token_usage_histogram(h) -> None:
    global _token_usage_histogram
    _token_usage_histogram = h


def get_token_usage_histogram():
    return _token_usage_histogram


def set_operation_duration_histogram(h) -> None:
    global _operation_duration_histogram
    _operation_duration_histogram = h


def get_operation_duration_histogram():
    return _operation_duration_histogram


def set_pii_scrub_counter(c) -> None:
    global _pii_scrub_counter
    _pii_scrub_counter = c


def get_pii_scrub_counter():
    return _pii_scrub_counter
