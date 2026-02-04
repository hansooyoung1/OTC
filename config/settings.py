"""
OTC Signal Engine Configuration
All tunable parameters in one place.
NO ML. NO INDICATORS. HARD-CODED RULES ONLY.
"""

from dataclasses import dataclass, field
from typing import List, Tuple
from enum import Enum


class SessionState(Enum):
    ACTIVE = "ACTIVE"           # Normal trading
    CAUTION = "CAUTION"         # After 1 win - only A+ signals
    LOCKED = "LOCKED"           # After 1 loss or 2 wins - no trading


class SignalGrade(Enum):
    A_PLUS = "A+"               # 85-100 confidence
    A = "A"                     # 75-84 confidence
    BLOCKED = "BLOCKED"         # <75 confidence


@dataclass(frozen=True)
class PatternConfig:
    """Pattern detection thresholds - HARD CODED"""
    
    # Pattern 1: Impulse → Stall → Snapback
    IMPULSE_MIN_TICKS: int = 3
    IMPULSE_MIN_DISTANCE_PIPS: float = 5.0
    STALL_MIN_DURATION_SEC: float = 2.0
    STALL_MAX_DURATION_SEC: float = 6.0
    STALL_MAX_TICK_SIZE_RATIO: float = 0.5  # vs impulse tick avg
    
    # Pattern 2: Micro Double-Top / Double-Bottom
    DOUBLE_LEVEL_TOLERANCE_PIPS: float = 2.0
    DOUBLE_MIN_PULLBACK_PIPS: float = 3.0
    DOUBLE_RETEST_MIN_SEC: float = 3.0
    DOUBLE_RETEST_MAX_SEC: float = 10.0
    DOUBLE_SECOND_PUSH_WEAKER_RATIO: float = 0.8
    
    # Pattern 3: Tick Momentum Exhaustion
    EXHAUSTION_MIN_TICKS: int = 4
    EXHAUSTION_TICK_DECAY_RATIO: float = 0.85  # Each tick < 85% of previous
    
    # Pattern 4: Flat Compression → Fakeout
    COMPRESSION_MIN_DURATION_SEC: float = 5.0
    COMPRESSION_MAX_RANGE_PIPS: float = 3.0
    FAKEOUT_HESITATION_MAX_SEC: float = 1.5
    

@dataclass(frozen=True)
class ConfidenceConfig:
    """Confidence scoring thresholds"""
    
    # Minimum tradable score
    MIN_TRADABLE_SCORE: int = 75
    A_PLUS_THRESHOLD: int = 85
    
    # Component weights
    PATTERN_QUALITY_MAX: int = 30
    TICK_CONSISTENCY_MAX: int = 20
    VOLATILITY_QUALITY_MAX: int = 20
    TIMING_BONUS_MAX: int = 15
    NOISE_PENALTY_MAX: int = 15
    
    # Pattern quality thresholds
    PATTERN_TEXTBOOK_MIN: int = 28
    PATTERN_CLEAR_MIN: int = 22
    PATTERN_WEAK_MIN: int = 15
    PATTERN_BLOCK_BELOW: int = 15
    
    # Tick consistency thresholds
    TICK_STRONG_MIN: int = 18
    TICK_MIXED_MIN: int = 8
    TICK_BLOCK_BELOW: int = 8
    
    # Volatility quality thresholds
    VOLATILITY_GOOD_MIN: int = 18
    VOLATILITY_BLOCK_BELOW: int = 8


@dataclass(frozen=True)
class KillSwitchConfig:
    """ABSOLUTE kill switch thresholds - NO OVERRIDE"""
    
    # Tick alternation kill switch
    ALTERNATION_COUNT_THRESHOLD: int = 3
    ALTERNATION_WINDOW_SEC: float = 5.0
    
    # Volatility spike detection
    VOLATILITY_SPIKE_MULTIPLIER: float = 3.0  # vs recent average
    
    # Entry delay threshold
    ENTRY_DELAY_MAX_MS: int = 500
    
    # Session limits
    MAX_TRADES_PER_DAY: int = 2
    MAX_LOSSES_PER_DAY: int = 1
    MAX_WINS_PER_DAY: int = 2


@dataclass(frozen=True)
class SessionConfig:
    """Session management settings"""
    
    MAX_SESSION_MINUTES: int = 45
    MIN_SESSION_MINUTES: int = 30
    
    # Countdown for human execution
    COUNTDOWN_SECONDS: int = 3
    
    # Entry window after countdown
    ENTRY_WINDOW_SECONDS: float = 2.0
    
    # Signal expiry times (seconds)
    EXPIRY_OPTIONS: Tuple[int, ...] = (5, 10, 15, 30)


@dataclass(frozen=True)
class PairSelectionConfig:
    """Daily pair selection criteria"""
    
    MIN_PAYOUT_PERCENT: int = 90
    PRIMARY_PAIR_ALLOCATION: float = 0.7
    SECONDARY_PAIR_ALLOCATION: float = 0.3
    
    # Quality assessment periods (seconds)
    IMPULSE_ASSESSMENT_WINDOW: int = 60
    CHOP_DETECTION_WINDOW: int = 30


@dataclass(frozen=True)
class TimingConfig:
    """OTC timing windows for bonus scoring"""
    
    # Hot windows (UTC) - higher activity, cleaner patterns
    HOT_WINDOWS: List[Tuple[int, int]] = field(default_factory=lambda: [
        (8, 10),   # European open
        (13, 15),  # US open
        (19, 21),  # Asian prep
    ])
    
    # Dead periods (UTC) - avoid
    DEAD_WINDOWS: List[Tuple[int, int]] = field(default_factory=lambda: [
        (0, 5),    # Low liquidity
        (11, 12),  # Lunch lull
    ])


@dataclass(frozen=True)
class DataConfig:
    """Price data capture settings"""
    
    # Tick buffer size (circular buffer)
    TICK_BUFFER_SIZE: int = 500
    
    # Price capture settings
    CAPTURE_INTERVAL_MS: int = 100  # 10 FPS
    
    # Screen capture region (to be calibrated per broker)
    PRICE_REGION_X: int = 0
    PRICE_REGION_Y: int = 0
    PRICE_REGION_WIDTH: int = 200
    PRICE_REGION_HEIGHT: int = 50
    
    # Price staleness threshold
    PRICE_STALE_MS: int = 500


@dataclass
class RuntimeConfig:
    """Runtime state - mutable"""
    
    session_state: SessionState = SessionState.ACTIVE
    trades_today: int = 0
    wins_today: int = 0
    losses_today: int = 0
    primary_pair: str = ""
    secondary_pair: str = ""
    session_start_time: float = 0.0
    last_signal_time: float = 0.0


# Singleton configurations
PATTERN_CONFIG = PatternConfig()
CONFIDENCE_CONFIG = ConfidenceConfig()
KILL_SWITCH_CONFIG = KillSwitchConfig()
SESSION_CONFIG = SessionConfig()
PAIR_CONFIG = PairSelectionConfig()
TIMING_CONFIG = TimingConfig()
DATA_CONFIG = DataConfig()
