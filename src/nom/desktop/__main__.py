"""``python -m nom.desktop`` entry — equivalent to the ``nom-app`` script."""

from __future__ import annotations

import sys

from nom.desktop.main import main

if __name__ == "__main__":
    sys.exit(main())
