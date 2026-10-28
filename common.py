"""Shared text helpers: whitespace-normalized verbatim matching."""
import re


def norm(t):
    # Strip ingest's page markers, then whitespace-only normalization.
    return " ".join(re.sub(r"\[page \d+\]", "", t).split())


def quote_in_source(quote, source):
    return bool(quote.strip()) and norm(quote) in norm(source)
