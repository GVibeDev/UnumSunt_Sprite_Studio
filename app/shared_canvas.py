"""Compatibility import for the retired P2-C shared-canvas module name.

The active persistent CREATE canvas lives in :mod:`app.shared_create_canvas`.
Keeping this module as a narrow alias avoids two independent canvas
implementations drifting apart during the P2-E/P2-F transition.
"""

from app.shared_create_canvas import SharedCreateCanvas

__all__ = ['SharedCreateCanvas']
