"""Eftervisningsmoduler. Import registrerer modulerne i REGISTRY."""
from .base import REGISTRY, Member, LTBInput, CheckResult, prepare  # noqa: F401
from . import klassifikation, boejning, forskydning, kombineret, soejlefladning, kipning  # noqa: F401
