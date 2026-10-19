"""Compatibility PEP 517 backend, now publicly authorized under MIT.

The root optional distribution contains the disclosed historical evaluator.
Product-only users install aevora_core and console independently.
"""
from setuptools import build_meta as _backend

def __getattr__(name):
    return getattr(_backend, name)
