"""
Countdown Timer Module
3-second countdown before signal execution.
Eliminates human reaction lag.
"""

import time
import threading
from typing import Callable, Optional
from dataclasses import dataclass
from enum import Enum
import sys
sys.path.insert(0, str(__file__).rsplit('src', 1)[0])
from config import SESSION_CONFIG


class CountdownState(Enum):
    """Countdown states"""
    IDLE = "IDLE"
    COUNTING = "COUNTING"
    READY = "READY"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


@dataclass
class CountdownResult:
    """Result of countdown execution"""
    state: CountdownState
    entry_valid: bool
    delay_ms: float
    reason: Optional[str] = None


class CountdownTimer:
    """
    3-second countdown timer for signal execution.
    
    Flow:
    1. Signal detected -> start countdown
    2. Count: 3... 2... 1...
    3. EXECUTE NOW displayed
    4. Brief entry window
    5. Window expires -> signal invalidated
    """
    
    def __init__(
        self,
        countdown_seconds: int = SESSION_CONFIG.COUNTDOWN_SECONDS,
        entry_window_seconds: float = SESSION_CONFIG.ENTRY_WINDOW_SECONDS,
        on_tick: Optional[Callable[[int], None]] = None,
        on_ready: Optional[Callable[[], None]] = None,
        on_expire: Optional[Callable[[], None]] = None
    ):
        self._countdown_seconds = countdown_seconds
        self._entry_window = entry_window_seconds
        self._on_tick = on_tick
        self._on_ready = on_ready
        self._on_expire = on_expire
        
        self._state = CountdownState.IDLE
        self._start_time: float = 0.0
        self._ready_time: float = 0.0
        self._countdown_thread: Optional[threading.Thread] = None
        self._cancelled = False
    
    @property
    def state(self) -> CountdownState:
        return self._state
    
    @property
    def is_active(self) -> bool:
        return self._state in [CountdownState.COUNTING, CountdownState.READY]
    
    def start(self) -> bool:
        """
        Start the countdown.
        Returns False if already running.
        """
        if self._state == CountdownState.COUNTING:
            return False
        
        self._cancelled = False
        self._state = CountdownState.COUNTING
        self._start_time = time.time()
        
        # Start countdown in thread
        self._countdown_thread = threading.Thread(target=self._run_countdown, daemon=True)
        self._countdown_thread.start()
        
        return True
    
    def _run_countdown(self):
        """Execute the countdown sequence"""
        for i in range(self._countdown_seconds, 0, -1):
            if self._cancelled:
                self._state = CountdownState.CANCELLED
                return
            
            # Callback for each tick
            if self._on_tick:
                self._on_tick(i)
            
            time.sleep(1.0)
            
            if self._cancelled:
                self._state = CountdownState.CANCELLED
                return
        
        # Countdown complete - READY state
        self._state = CountdownState.READY
        self._ready_time = time.time()
        
        if self._on_ready:
            self._on_ready()
        
        # Wait for entry window
        time.sleep(self._entry_window)
        
        # If still in READY state, expire
        if self._state == CountdownState.READY:
            self._state = CountdownState.EXPIRED
            if self._on_expire:
                self._on_expire()
    
    def cancel(self):
        """Cancel the countdown"""
        self._cancelled = True
        self._state = CountdownState.CANCELLED
    
    def acknowledge_entry(self) -> CountdownResult:
        """
        Acknowledge that user has entered the trade.
        Call this when user confirms entry.
        Returns validation result.
        """
        now = time.time()
        
        if self._state != CountdownState.READY:
            return CountdownResult(
                state=self._state,
                entry_valid=False,
                delay_ms=0,
                reason=f"Invalid state for entry: {self._state.value}"
            )
        
        # Calculate delay from ready signal
        delay_ms = (now - self._ready_time) * 1000
        
        # Check if within entry window
        if delay_ms > self._entry_window * 1000:
            self._state = CountdownState.EXPIRED
            return CountdownResult(
                state=CountdownState.EXPIRED,
                entry_valid=False,
                delay_ms=delay_ms,
                reason=f"Entry window expired ({delay_ms:.0f}ms > {self._entry_window * 1000:.0f}ms)"
            )
        
        # Valid entry
        self._state = CountdownState.IDLE
        return CountdownResult(
            state=CountdownState.READY,
            entry_valid=True,
            delay_ms=delay_ms,
            reason=None
        )
    
    def reset(self):
        """Reset timer to idle state"""
        self._cancelled = True
        self._state = CountdownState.IDLE
        self._start_time = 0.0
        self._ready_time = 0.0
    
    def get_remaining_seconds(self) -> int:
        """Get remaining countdown seconds"""
        if self._state != CountdownState.COUNTING:
            return 0
        
        elapsed = time.time() - self._start_time
        remaining = self._countdown_seconds - int(elapsed)
        return max(0, remaining)
    
    def get_entry_window_remaining_ms(self) -> float:
        """Get remaining entry window in milliseconds"""
        if self._state != CountdownState.READY:
            return 0.0
        
        elapsed = time.time() - self._ready_time
        remaining = (self._entry_window - elapsed) * 1000
        return max(0.0, remaining)


class BlockingCountdown:
    """
    Simple blocking countdown for console mode.
    Prints countdown to console.
    """
    
    @staticmethod
    def run(seconds: int = 3, on_complete: Optional[Callable[[], None]] = None) -> bool:
        """
        Run blocking countdown with console output.
        Returns True if completed, False if interrupted.
        """
        try:
            print("\n" + "=" * 40)
            print("   SIGNAL DETECTED - PREPARE TO EXECUTE")
            print("=" * 40)
            
            for i in range(seconds, 0, -1):
                print(f"\n   >>> {i} <<<")
                time.sleep(1.0)
            
            print("\n" + "=" * 40)
            print("   🔥 EXECUTE NOW 🔥")
            print("=" * 40 + "\n")
            
            if on_complete:
                on_complete()
            
            return True
            
        except KeyboardInterrupt:
            print("\n[CANCELLED] Countdown aborted")
            return False
