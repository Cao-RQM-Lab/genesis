"""
American Magnetics Inc. Model 420 magnet power supply programmer driver package.
"""

from .driver import INSTRUMENT_TYPE_KEY, Ami420Instrument

__all__ = ["Ami420Instrument", "INSTRUMENT_TYPE_KEY"]
