"""
Session State Machine
Manages trading session states and transitions.

States:
🟢 ACTIVE    - Normal trading
🟡 CAUTION   - After 1 win (only A+ signals)
🔴 LOCKED    - After 1 loss or 2 wins (no trading)
"""

import time
from dataclasses import dataclass, field
from typing import Optional, Callable
import sys
sys.path.insert(0, str(__file__).rsplit('src', 1)[0])
from config import SessionState, SignalGrade, SESSION_CONFIG, KILL_SWITCH_CONFIG


@dataclass
class SessionStats:
    """Session statistics"""
    session_start: float = 0.0
    trades_taken: int = 0
    wins: int = 0
    losses: int = 0
    signals_generated: int = 0
    signals_blocked: int = 0
    
    @property
    def win_rate(self) -> float:
        if self.trades_taken == 0:
            return 0.0
        return self.wins / self.trades_taken
    
    @property
    def session_duration_minutes(self) -> float:
        if self.session_start == 0:
            return 0.0
        return (time.time() - self.session_start) / 60


class SessionStateMachine:
    """
    State machine for trading session management.
    
    Transitions:
    ACTIVE -> CAUTION (on first win)
    ACTIVE -> LOCKED (on first loss)
    CAUTION -> LOCKED (on win or loss)
    LOCKED -> (no exit, session ended)
    """
    
    def __init__(
        self,
        on_state_change: Optional[Callable[[SessionState, SessionState], None]] = None
    ):
        self._state = SessionState.ACTIVE
        self._stats = SessionStats()
        self._on_state_change = on_state_change
        self._session_active = False
    
    @property
    def state(self) -> SessionState:
        return self._state
    
    @property
    def stats(self) -> SessionStats:
        return self._stats
    
    @property
    def is_trading_allowed(self) -> bool:
        """Check if trading is allowed in current state"""
        return self._state != SessionState.LOCKED and self._session_active
    
    def start_session(self):
        """Start a new trading session"""
        self._state = SessionState.ACTIVE
        self._stats = SessionStats(session_start=time.time())
        self._session_active = True
        print(f"[SESSION] Started - State: {self._state.value}")
    
    def end_session(self):
        """End the current session"""
        self._session_active = False
        print(f"[SESSION] Ended - Duration: {self._stats.session_duration_minutes:.1f}min")
        print(f"[SESSION] Stats: {self._stats.trades_taken} trades, {self._stats.wins}W/{self._stats.losses}L")
    
    def record_trade_outcome(self, is_win: bool):
        """
        Record trade outcome and transition state if needed.
        """
        self._stats.trades_taken += 1
        
        old_state = self._state
        
        if is_win:
            self._stats.wins += 1
            self._handle_win()
        else:
            self._stats.losses += 1
            self._handle_loss()
        
        if old_state != self._state:
            self._trigger_state_change(old_state, self._state)
    
    def _handle_win(self):
        """Handle win outcome"""
        if self._state == SessionState.ACTIVE:
            # First win: go to CAUTION (only A+ from now)
            self._state = SessionState.CAUTION
            print("[SESSION] First win - Switching to CAUTION mode (A+ only)")
        
        elif self._state == SessionState.CAUTION:
            # Second win in caution: LOCK
            self._state = SessionState.LOCKED
            print("[SESSION] Second win - Session LOCKED (daily win limit)")
    
    def _handle_loss(self):
        """Handle loss outcome"""
        # ANY loss from any state -> LOCKED
        self._state = SessionState.LOCKED
        print("[SESSION] Loss recorded - Session LOCKED (max 1 loss rule)")
    
    def record_signal(self, was_blocked: bool):
        """Record signal generation"""
        self._stats.signals_generated += 1
        if was_blocked:
            self._stats.signals_blocked += 1
    
    def can_accept_grade(self, grade: SignalGrade) -> bool:
        """
        Check if a signal grade can be accepted in current state.
        
        ACTIVE: A or A+ allowed
        CAUTION: Only A+ allowed
        LOCKED: Nothing allowed
        """
        if self._state == SessionState.LOCKED:
            return False
        
        if self._state == SessionState.CAUTION:
            return grade == SignalGrade.A_PLUS
        
        # ACTIVE state
        return grade in [SignalGrade.A, SignalGrade.A_PLUS]
    
    def check_session_timeout(self) -> bool:
        """Check if session has exceeded max duration"""
        if not self._session_active:
            return False
        
        duration = self._stats.session_duration_minutes
        if duration >= SESSION_CONFIG.MAX_SESSION_MINUTES:
            print(f"[SESSION] Timeout reached ({duration:.1f}min)")
            self._state = SessionState.LOCKED
            return True
        
        return False
    
    def get_state_display(self) -> str:
        """Get display string for current state"""
        state_displays = {
            SessionState.ACTIVE: "🟢 ACTIVE",
            SessionState.CAUTION: "🟡 CAUTION (A+ only)",
            SessionState.LOCKED: "🔴 LOCKED"
        }
        return state_displays.get(self._state, "UNKNOWN")
    
    def get_remaining_trades(self) -> int:
        """Get remaining allowed trades"""
        return max(0, KILL_SWITCH_CONFIG.MAX_TRADES_PER_DAY - self._stats.trades_taken)
    
    def _trigger_state_change(self, old_state: SessionState, new_state: SessionState):
        """Trigger state change callback"""
        if self._on_state_change:
            self._on_state_change(old_state, new_state)
    
    def force_lock(self, reason: str = "Manual lock"):
        """Force lock the session"""
        old_state = self._state
        self._state = SessionState.LOCKED
        print(f"[SESSION] Force locked: {reason}")
        if old_state != self._state:
            self._trigger_state_change(old_state, self._state)
