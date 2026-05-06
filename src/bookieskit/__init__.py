"""Bookieskit — HTTP clients for betting data scraping."""

from bookieskit.bookmakers.bet9ja import Bet9ja
from bookieskit.bookmakers.betpawa import BetPawa
from bookieskit.bookmakers.betway import Betway
from bookieskit.bookmakers.msport import MSport
from bookieskit.bookmakers.sportybet import SportyBet
from bookieskit.event_info import (
    LiveInfo,
    Mode,
    Participants,
    extract_kickoff,
    extract_live_info,
    extract_participants,
    is_live_now,
)

__version__ = "0.4.0"
__all__ = [
    "BetPawa",
    "SportyBet",
    "Bet9ja",
    "Betway",
    "MSport",
    "LiveInfo",
    "Mode",
    "Participants",
    "extract_kickoff",
    "extract_live_info",
    "extract_participants",
    "is_live_now",
    "__version__",
]
