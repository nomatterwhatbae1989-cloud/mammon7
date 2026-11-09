"""
Revenue engine core module for MAMMON-7.
Provides core revenue generation utilities without financial transactions.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Final


class RevenueCore:
    """
    Core revenue engine utilities.

    Methods:
        now_iso() -> str: Returns current UTC timestamp in ISO 8601 format.
        gen_id() -> str: Generates a unique identifier for revenue records.
    """

    @staticmethod
    def now_iso() -> str:
        """
        Return current UTC timestamp in ISO 8601 format.

        Returns:
            str: ISO 8601 formatted timestamp.
        """
        return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')

    @staticmethod
    def gen_id() -> str:
        """
        Generate a unique identifier for revenue records.

        Uses UUID version 4 with hex encoding (no hyphens).

        Returns:
            str: 32-character hexadecimal UUID.
        """
        return uuid.uuid4().hex
