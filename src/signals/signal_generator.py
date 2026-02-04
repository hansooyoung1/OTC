"""
Signal Generator Module
Combines pattern detection, confidence scoring, and kill switches
to generate actionable trading signals.
"""

import time
from dataclasses import dataclass
from typing import Optional, Callable
from enum import Enum
import sys
sys.path.insert(0, str(__file__).rsplit('src', 1)[0])
from config import SignalGrade, SessionState
from src.data.tick_buffer import TickBuffer
from src.engine.pattern_detector import PatternDetector
from src.engine.confidence_scorer import ConfidenceScorer, ConfidenceResult
from src.engine.kill_switches import KillSwitchEngine
from src.state.session_state import SessionStateMachine
from src.patterns.base_pattern import PatternType, TradeDirection


class SignalStatus(Enum):
    """Signal status"""
    GENERATED = "GENERATED"
    BLOCKED_PATTERN = "BLOCKED_PATTERN"
    BLOCKED_CONFIDENCE = "BLOCKED_CONFIDENCE"
    BLOCKED_KILL_SWITCH = "BLOCKED_KILL_SWITCH"
    BLOCKED_SESSION_STATE = "BLOCKED_SESSION_STATE"
    NO_PATTERN = "NO_PATTERN"


@dataclass
class Signal:
    """Trading signal"""
    status: SignalStatus
    
    # Trade details (if generated)
    direction: TradeDirection
    expiry_seconds: int
    entry_price: Optional[float]
    
    # Scoring
    confidence_score: int
    grade: SignalGrade
    pattern_type: PatternType
    
    # Metadata
    timestamp: float
    block_reason: Optional[str]
    
    @property
    def is_actionable(self) -> bool:
        return self.status == SignalStatus.GENERATED
    
    def __str__(self) -> str:
        if not self.is_actionable:
            return f"[BLOCKED] {self.block_reason}"
        
        return (
            f"[SIGNAL] {self.direction.value} | "
            f"Expiry: {self.expiry_seconds}s | "
            f"Score: {self.confidence_score} [{self.grade.value}] | "
            f"Pattern: {self.pattern_type.value}"
        )


class SignalGenerator:
    """
    Signal generator - the brain of the trading system.
    
    Flow:
    1. Check kill switches
    2. Check session state
    3. Detect patterns
    4. Calculate confidence
    5. Validate grade against session state
    6. Generate or block signal
    """
    
    def __init__(
        self,
        tick_buffer: TickBuffer,
        session_state: SessionStateMachine,
        on_signal: Optional[Callable[[Signal], None]] = None
    ):
        self.tick_buffer = tick_buffer
        self.session_state = session_state
        self._on_signal = on_signal
        
        # Initialize engines
        self.pattern_detector = PatternDetector(tick_buffer)
        self.confidence_scorer = ConfidenceScorer()
        self.kill_switches = KillSwitchEngine(tick_buffer)
        
        # Signal history
        self._last_signal: Optional[Signal] = None
        self._signal_count = 0
    
    def scan(self) -> Signal:
        """
        Main scan loop - check for trading signals.
        Called on each tick update.
        """
        
        # Step 1: Check kill switches
        kill_result = self.kill_switches.check_all()
        if kill_result.triggered:
            return self._blocked_signal(
                SignalStatus.BLOCKED_KILL_SWITCH,
                kill_result.reason
            )
        
        # Step 2: Check session state
        if not self.session_state.is_trading_allowed:
            return self._blocked_signal(
                SignalStatus.BLOCKED_SESSION_STATE,
                f"Session state: {self.session_state.state.value}"
            )
        
        # Step 3: Detect patterns
        detection = self.pattern_detector.detect()
        
        if not detection.has_detection:
            # Check for unclassifiable behavior
            uncl_result = self.kill_switches.check_unclassifiable(
                detection.patterns_checked,
                detection.patterns_detected
            )
            if uncl_result.triggered:
                return self._blocked_signal(
                    SignalStatus.BLOCKED_KILL_SWITCH,
                    uncl_result.reason
                )
            
            return self._no_pattern_signal()
        
        pattern_result = detection.best_pattern
        
        # Step 4: Calculate confidence
        confidence = self.confidence_scorer.calculate(pattern_result)
        
        # Step 5: Check if tradable
        if not confidence.is_tradable:
            self.session_state.record_signal(was_blocked=True)
            return self._blocked_signal(
                SignalStatus.BLOCKED_CONFIDENCE,
                confidence.block_reason
            )
        
        # Step 6: Validate grade against session state
        if not self.session_state.can_accept_grade(confidence.grade):
            self.session_state.record_signal(was_blocked=True)
            return self._blocked_signal(
                SignalStatus.BLOCKED_SESSION_STATE,
                f"Grade {confidence.grade.value} not accepted in {self.session_state.state.value} state"
            )
        
        # Step 7: Generate signal
        signal = Signal(
            status=SignalStatus.GENERATED,
            direction=pattern_result.direction,
            expiry_seconds=pattern_result.recommended_expiry,
            entry_price=pattern_result.entry_price,
            confidence_score=confidence.total_score,
            grade=confidence.grade,
            pattern_type=pattern_result.pattern_type,
            timestamp=time.time(),
            block_reason=None
        )
        
        self._last_signal = signal
        self._signal_count += 1
        self.session_state.record_signal(was_blocked=False)
        
        # Trigger callback
        if self._on_signal:
            self._on_signal(signal)
        
        return signal
    
    def _blocked_signal(self, status: SignalStatus, reason: str) -> Signal:
        """Create a blocked signal"""
        return Signal(
            status=status,
            direction=TradeDirection.NONE,
            expiry_seconds=0,
            entry_price=None,
            confidence_score=0,
            grade=SignalGrade.BLOCKED,
            pattern_type=PatternType.NONE,
            timestamp=time.time(),
            block_reason=reason
        )
    
    def _no_pattern_signal(self) -> Signal:
        """Create a no-pattern signal (not an error, just no opportunity)"""
        return Signal(
            status=SignalStatus.NO_PATTERN,
            direction=TradeDirection.NONE,
            expiry_seconds=0,
            entry_price=None,
            confidence_score=0,
            grade=SignalGrade.BLOCKED,
            pattern_type=PatternType.NONE,
            timestamp=time.time(),
            block_reason="No pattern detected"
        )
    
    def record_trade_result(self, is_win: bool):
        """Record trade result"""
        self.session_state.record_trade_outcome(is_win)
        self.kill_switches.record_trade(is_win)
    
    @property
    def last_signal(self) -> Optional[Signal]:
        return self._last_signal
    
    @property
    def signal_count(self) -> int:
        return self._signal_count
    
    def reset(self):
        """Reset generator state"""
        self._last_signal = None
        self._signal_count = 0
        self.confidence_scorer.reset_latency_data()
