"""Bookieskit — HTTP clients for betting data scraping."""

from bookieskit.bookmakers.bet9ja import Bet9ja
from bookieskit.bookmakers.betpawa import BetPawa
from bookieskit.bookmakers.sportybet import SportyBet

__all__ = ["BetPawa", "SportyBet", "Bet9ja"]
__version__ = "0.1.0"
