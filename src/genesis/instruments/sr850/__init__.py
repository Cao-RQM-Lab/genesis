"""
SR850-specific driver definitions.

This package provides an instrument driver module for use by the Genesis
instrument registry and job builder GUI.
"""

from .driver import INSTRUMENT_TYPE_KEY, Sr850Instrument

__all__ = ["INSTRUMENT_TYPE_KEY", "Sr850Instrument"]
