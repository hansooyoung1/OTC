"""
Trade Limits Module
Manages and enforces trading limits.
"""

from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional
import sys
sys.path.insert(0, str(__file__).rsplit('src', 1)[0])
from config import KILL_SWITCH_CONFIG


@dataclass
class DailyLimits:
    """Daily trading limits"""
    max_trades: int = KILL_SWITCH_CONFIG.MAX_TRADES_PER_DAY
    max_losses: int = KILL_SWITCH_CONFIG.MAX_LOSSES_PER_DAY
    max_wins: int = KILL_SWITCH_CONFIG.MAX_WINS_PER_DAY


class TradeLimits:
    """
    Trade limit manager.
    Tracks and enforces daily limits.
    """
    
    def __init__(self, limits: Optional[DailyLimits] = None):
        self._limits = limits or DailyLimits()
        self._current_date: Optional[date] = None
        self._trades_today = 0
        self._wins_today = 0
        self._losses_today = 0
    
    def start_new_day(self):
        """Reset counters for new day"""
        self._current_date = date.today()
        self._trades_today = 0
        self._wins_today = 0
        self._losses_today = 0
    
    def _check_date(self):
        """Auto-reset if date changed"""
        today = date.today()
        if self._current_date != today:
            self.start_new_day()
    
    def can_trade(self) -> tuple[bool, str]:
        """
        Check if trading is allowed.
        Returns (allowed, reason)
        """
        self._check_date()
        
        if self._trades_today >= self._limits.max_trades:
            return False, f"Daily trade limit reached ({self._limits.max_trades})"
        
        if self._losses_today >= self._limits.max_losses:
            return False, f"Daily loss limit reached ({self._limits.max_losses})"
        
        if self._wins_today >= self._limits.max_wins:
            return False, f"Daily win limit reached ({self._limits.max_wins})"
        
        return True, "Trading allowed"
    
    def record_trade(self, is_win: bool) -> tuple[bool, str]:
        """
        Record a trade and return limit status.
        Returns (still_allowed, message)
        """
        self._check_date()
        
        self._trades_today += 1
        
        if is_win:
            self._wins_today += 1
        else:
            self._losses_today += 1
        
        return self.can_trade()
    
    @property
    def trades_remaining(self) -> int:
        self._check_date()
        return max(0, self._limits.max_trades - self._trades_today)
    
    @property
    def trades_today(self) -> int:
        self._check_date()
        return self._trades_today
    
    @property
    def wins_today(self) -> int:
        self._check_date()
        return self._wins_today
    
    @property
    def losses_today(self) -> int:
        self._check_date()
        return self._losses_today
    
    def get_summary(self) -> str:
        """Get human-readable summary"""
        self._check_date()
        return (
            f"Trades: {self._trades_today}/{self._limits.max_trades} | "
            f"Wins: {self._wins_today}/{self._limits.max_wins} | "
            f"Losses: {self._losses_today}/{self._limits.max_losses}"
        )
