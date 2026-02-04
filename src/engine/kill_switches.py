"""
Kill Switch Engine
ABSOLUTE blocks - NO OVERRIDE, NO EXCEPTIONS

Immediately block all trades if:
- Tick alternation > 3 times in 5s
- Sudden volatility spike
- Entry delay exceeds threshold
- Trade limits reached
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional
import time
import sys
sys.path.insert(0, str(__file__).rsplit('src', 1)[0])
from config import KILL_SWITCH_CONFIG
from src.data.tick_buffer import TickBuffer


class KillSwitchType(Enum):
    """Types of kill switches"""
    TICK_ALTERNATION = "TICK_ALTERNATION"
    VOLATILITY_SPIKE = "VOLATILITY_SPIKE"
    ENTRY_DELAY = "ENTRY_DELAY"
    DAILY_TRADE_LIMIT = "DAILY_TRADE_LIMIT"
    DAILY_LOSS_LIMIT = "DAILY_LOSS_LIMIT"
    DAILY_WIN_LIMIT = "DAILY_WIN_LIMIT"
    SESSION_LOCKED = "SESSION_LOCKED"
    UNCLASSIFIABLE_BEHAVIOR = "UNCLASSIFIABLE_BEHAVIOR"
    NONE = "NONE"


@dataclass
class KillSwitchResult:
    """Result of kill switch check"""
    triggered: bool
    switch_type: KillSwitchType
    reason: str
    severity: int  # 1-5, 5 being most severe
    
    @property
    def is_hard_block(self) -> bool:
        """All triggered switches are hard blocks"""
        return self.triggered


class KillSwitchEngine:
    """
    Kill switch engine - enforces absolute blocks.
    NO OVERRIDE. NO EXCEPTIONS.
    """
    
    def __init__(self, tick_buffer: TickBuffer):
        self.tick_buffer = tick_buffer
        self._trades_today = 0
        self._wins_today = 0
        self._losses_today = 0
        self._session_locked = False
        self._last_signal_time = 0.0
    
    def check_all(self) -> KillSwitchResult:
        """
        Check all kill switches.
        Returns first triggered switch or NONE.
        """
        
        # Priority order: session locks first
        
        # 1. Session locked
        if self._session_locked:
            return KillSwitchResult(
                triggered=True,
                switch_type=KillSwitchType.SESSION_LOCKED,
                reason="Session is locked - no more trades allowed",
                severity=5
            )
        
        # 2. Daily trade limit
        if self._trades_today >= KILL_SWITCH_CONFIG.MAX_TRADES_PER_DAY:
            return KillSwitchResult(
                triggered=True,
                switch_type=KillSwitchType.DAILY_TRADE_LIMIT,
                reason=f"Daily trade limit reached: {self._trades_today}/{KILL_SWITCH_CONFIG.MAX_TRADES_PER_DAY}",
                severity=5
            )
        
        # 3. Daily loss limit
        if self._losses_today >= KILL_SWITCH_CONFIG.MAX_LOSSES_PER_DAY:
            return KillSwitchResult(
                triggered=True,
                switch_type=KillSwitchType.DAILY_LOSS_LIMIT,
                reason=f"Daily loss limit reached: {self._losses_today}/{KILL_SWITCH_CONFIG.MAX_LOSSES_PER_DAY}",
                severity=5
            )
        
        # 4. Daily win limit
        if self._wins_today >= KILL_SWITCH_CONFIG.MAX_WINS_PER_DAY:
            return KillSwitchResult(
                triggered=True,
                switch_type=KillSwitchType.DAILY_WIN_LIMIT,
                reason=f"Daily win limit reached: {self._wins_today}/{KILL_SWITCH_CONFIG.MAX_WINS_PER_DAY}",
                severity=5
            )
        
        # 5. Tick alternation
        alternation_result = self._check_tick_alternation()
        if alternation_result.triggered:
            return alternation_result
        
        # 6. Volatility spike
        volatility_result = self._check_volatility_spike()
        if volatility_result.triggered:
            return volatility_result
        
        # All clear
        return KillSwitchResult(
            triggered=False,
            switch_type=KillSwitchType.NONE,
            reason="All kill switches clear",
            severity=0
        )
    
    def check_entry_delay(self, signal_time: float, entry_time: float) -> KillSwitchResult:
        """
        Check if entry delay exceeds threshold.
        Called during signal execution.
        """
        delay_ms = (entry_time - signal_time) * 1000
        
        if delay_ms > KILL_SWITCH_CONFIG.ENTRY_DELAY_MAX_MS:
            return KillSwitchResult(
                triggered=True,
                switch_type=KillSwitchType.ENTRY_DELAY,
                reason=f"Entry delay {delay_ms:.0f}ms exceeds {KILL_SWITCH_CONFIG.ENTRY_DELAY_MAX_MS}ms",
                severity=4
            )
        
        return KillSwitchResult(
            triggered=False,
            switch_type=KillSwitchType.NONE,
            reason="Entry delay acceptable",
            severity=0
        )
    
    def _check_tick_alternation(self) -> KillSwitchResult:
        """Check for excessive tick alternation (random noise)"""
        alternations = self.tick_buffer.detect_tick_alternation(
            KILL_SWITCH_CONFIG.ALTERNATION_WINDOW_SEC
        )
        
        if alternations > KILL_SWITCH_CONFIG.ALTERNATION_COUNT_THRESHOLD:
            return KillSwitchResult(
                triggered=True,
                switch_type=KillSwitchType.TICK_ALTERNATION,
                reason=f"Tick alternation detected: {alternations} in {KILL_SWITCH_CONFIG.ALTERNATION_WINDOW_SEC}s",
                severity=4
            )
        
        return KillSwitchResult(
            triggered=False,
            switch_type=KillSwitchType.NONE,
            reason="Tick alternation normal",
            severity=0
        )
    
    def _check_volatility_spike(self) -> KillSwitchResult:
        """Check for sudden volatility spike"""
        is_spike = self.tick_buffer.detect_volatility_spike(
            KILL_SWITCH_CONFIG.VOLATILITY_SPIKE_MULTIPLIER
        )
        
        if is_spike:
            return KillSwitchResult(
                triggered=True,
                switch_type=KillSwitchType.VOLATILITY_SPIKE,
                reason=f"Volatility spike detected (>{KILL_SWITCH_CONFIG.VOLATILITY_SPIKE_MULTIPLIER}x average)",
                severity=4
            )
        
        return KillSwitchResult(
            triggered=False,
            switch_type=KillSwitchType.NONE,
            reason="Volatility normal",
            severity=0
        )
    
    def check_unclassifiable(self, patterns_checked: int, patterns_detected: int) -> KillSwitchResult:
        """
        Block if behavior cannot be classified.
        If we checked all patterns and none detected, behavior is unclassifiable.
        """
        if patterns_checked > 0 and patterns_detected == 0:
            # Check if there's price movement but no pattern
            recent_ticks = self.tick_buffer.get_ticks_in_window(5.0)
            if len(recent_ticks) >= 5:
                # There's activity but no pattern - unclassifiable
                movement = sum(t.size for t in recent_ticks)
                if movement > 0:
                    return KillSwitchResult(
                        triggered=True,
                        switch_type=KillSwitchType.UNCLASSIFIABLE_BEHAVIOR,
                        reason="Price behavior cannot be classified to any pattern",
                        severity=3
                    )
        
        return KillSwitchResult(
            triggered=False,
            switch_type=KillSwitchType.NONE,
            reason="Behavior classifiable or insufficient data",
            severity=0
        )
    
    def record_trade(self, is_win: bool):
        """Record trade outcome and update limits"""
        self._trades_today += 1
        
        if is_win:
            self._wins_today += 1
            if self._wins_today >= KILL_SWITCH_CONFIG.MAX_WINS_PER_DAY:
                self.lock_session("Win limit reached")
        else:
            self._losses_today += 1
            if self._losses_today >= KILL_SWITCH_CONFIG.MAX_LOSSES_PER_DAY:
                self.lock_session("Loss limit reached")
    
    def lock_session(self, reason: str = "Manual lock"):
        """Lock the session - no more trades"""
        self._session_locked = True
        print(f"[KILL SWITCH] Session LOCKED: {reason}")
    
    def unlock_session(self):
        """Unlock session (use with caution)"""
        self._session_locked = False
    
    def reset_daily_counters(self):
        """Reset all daily counters - call at session start"""
        self._trades_today = 0
        self._wins_today = 0
        self._losses_today = 0
        self._session_locked = False
    
    @property
    def trades_today(self) -> int:
        return self._trades_today
    
    @property
    def wins_today(self) -> int:
        return self._wins_today
    
    @property
    def losses_today(self) -> int:
        return self._losses_today
    
    @property
    def is_session_locked(self) -> bool:
        return self._session_locked
    
    @property
    def remaining_trades(self) -> int:
        return max(0, KILL_SWITCH_CONFIG.MAX_TRADES_PER_DAY - self._trades_today)
