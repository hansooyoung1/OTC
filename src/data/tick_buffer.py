"""
Tick Buffer Module
Circular buffer for storing and analyzing tick data.
Designed for OTC markets with imperfect data.
"""

import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from collections import deque
import sys
sys.path.insert(0, str(__file__).rsplit('src', 1)[0])
from config import DATA_CONFIG


@dataclass
class Tick:
    """Single tick data point"""
    price: float
    timestamp: float  # Unix timestamp in seconds
    direction: int = 0  # 1 = up, -1 = down, 0 = unchanged
    size: float = 0.0  # Absolute price change from previous tick
    
    def __post_init__(self):
        self.timestamp = self.timestamp or time.time()


@dataclass
class TickBuffer:
    """
    Circular buffer for tick storage and analysis.
    Provides methods for pattern detection support.
    """
    max_size: int = DATA_CONFIG.TICK_BUFFER_SIZE
    _buffer: deque = field(default_factory=deque, repr=False)
    _last_price: Optional[float] = None
    
    def add_tick(self, price: float, timestamp: Optional[float] = None) -> Optional[Tick]:
        """Add a new tick to the buffer. Returns the created Tick or None if duplicate."""
        ts = timestamp or time.time()
        
        # Calculate direction and size from previous tick
        direction = 0
        size = 0.0
        
        if self._last_price is not None:
            diff = price - self._last_price
            if diff > 0:
                direction = 1
            elif diff < 0:
                direction = -1
            size = abs(diff)
        
        # Skip if price unchanged (no actual tick)
        if self._last_price is not None and direction == 0:
            return None
        
        tick = Tick(price=price, timestamp=ts, direction=direction, size=size)
        
        # Maintain circular buffer
        if len(self._buffer) >= self.max_size:
            self._buffer.popleft()
        
        self._buffer.append(tick)
        self._last_price = price
        
        return tick
    
    def get_recent_ticks(self, count: int) -> List[Tick]:
        """Get the N most recent ticks"""
        return list(self._buffer)[-count:] if self._buffer else []
    
    def get_ticks_in_window(self, seconds: float) -> List[Tick]:
        """Get all ticks within the last N seconds"""
        if not self._buffer:
            return []
        
        cutoff = time.time() - seconds
        return [t for t in self._buffer if t.timestamp >= cutoff]
    
    def get_consecutive_direction_ticks(self, from_end: bool = True) -> List[Tick]:
        """
        Get consecutive ticks in the same direction.
        Used for impulse detection.
        """
        if len(self._buffer) < 2:
            return []
        
        ticks = list(self._buffer)
        if from_end:
            ticks = ticks[::-1]
        
        result = [ticks[0]]
        target_direction = ticks[0].direction
        
        if target_direction == 0:
            return []
        
        for tick in ticks[1:]:
            if tick.direction == target_direction:
                result.append(tick)
            else:
                break
        
        return result[::-1] if from_end else result
    
    def calculate_impulse_distance(self, ticks: List[Tick]) -> float:
        """Calculate total price movement for a sequence of ticks"""
        if not ticks:
            return 0.0
        return sum(t.size for t in ticks)
    
    def get_average_tick_size(self, count: int = 20) -> float:
        """Get average tick size from recent ticks"""
        ticks = self.get_recent_ticks(count)
        if not ticks:
            return 0.0
        sizes = [t.size for t in ticks if t.size > 0]
        return sum(sizes) / len(sizes) if sizes else 0.0
    
    def detect_tick_alternation(self, window_sec: float = 5.0) -> int:
        """
        Count direction alternations in window.
        Used for kill switch detection.
        """
        ticks = self.get_ticks_in_window(window_sec)
        if len(ticks) < 3:
            return 0
        
        alternations = 0
        for i in range(1, len(ticks)):
            if ticks[i].direction != 0 and ticks[i-1].direction != 0:
                if ticks[i].direction != ticks[i-1].direction:
                    alternations += 1
        
        return alternations
    
    def detect_volatility_spike(self, multiplier: float = 3.0) -> bool:
        """
        Detect if recent tick size is a spike vs average.
        Returns True if volatility spike detected.
        """
        if len(self._buffer) < 10:
            return False
        
        recent_ticks = self.get_recent_ticks(5)
        historical_avg = self.get_average_tick_size(50)
        
        if historical_avg == 0:
            return False
        
        for tick in recent_ticks:
            if tick.size > historical_avg * multiplier:
                return True
        
        return False
    
    def get_price_range(self, seconds: float) -> Tuple[float, float, float]:
        """
        Get price range in window.
        Returns (min, max, range)
        """
        ticks = self.get_ticks_in_window(seconds)
        if not ticks:
            return (0.0, 0.0, 0.0)
        
        prices = [t.price for t in ticks]
        min_price = min(prices)
        max_price = max(prices)
        return (min_price, max_price, max_price - min_price)
    
    def get_tick_speed(self, count: int = 5) -> float:
        """
        Calculate ticks per second for recent period.
        Used for momentum analysis.
        """
        ticks = self.get_recent_ticks(count)
        if len(ticks) < 2:
            return 0.0
        
        time_span = ticks[-1].timestamp - ticks[0].timestamp
        if time_span <= 0:
            return 0.0
        
        return (len(ticks) - 1) / time_span
    
    def is_price_stale(self, threshold_ms: int = None) -> bool:
        """Check if price data is stale (no recent updates)"""
        threshold = threshold_ms or DATA_CONFIG.PRICE_STALE_MS
        
        if not self._buffer:
            return True
        
        last_tick = self._buffer[-1]
        age_ms = (time.time() - last_tick.timestamp) * 1000
        
        return age_ms > threshold
    
    @property
    def latest_tick(self) -> Optional[Tick]:
        """Get the most recent tick"""
        return self._buffer[-1] if self._buffer else None
    
    @property
    def latest_price(self) -> Optional[float]:
        """Get the most recent price"""
        return self._buffer[-1].price if self._buffer else None
    
    @property
    def tick_count(self) -> int:
        """Get total ticks in buffer"""
        return len(self._buffer)
    
    def clear(self):
        """Clear the buffer"""
        self._buffer.clear()
        self._last_price = None
    
    def get_local_high(self, lookback: int = 20) -> Optional[float]:
        """Get local high price"""
        ticks = self.get_recent_ticks(lookback)
        if not ticks:
            return None
        return max(t.price for t in ticks)
    
    def get_local_low(self, lookback: int = 20) -> Optional[float]:
        """Get local low price"""
        ticks = self.get_recent_ticks(lookback)
        if not ticks:
            return None
        return min(t.price for t in ticks)
    
    def has_new_high(self, seconds: float = 2.0) -> bool:
        """Check if price made new high in recent window"""
        ticks = self.get_ticks_in_window(seconds)
        if len(ticks) < 2:
            return False
        
        recent_high = max(t.price for t in ticks)
        older_ticks = self.get_recent_ticks(50)
        older_ticks = [t for t in older_ticks if t not in ticks]
        
        if not older_ticks:
            return False
        
        prior_high = max(t.price for t in older_ticks)
        return recent_high > prior_high
    
    def has_new_low(self, seconds: float = 2.0) -> bool:
        """Check if price made new low in recent window"""
        ticks = self.get_ticks_in_window(seconds)
        if len(ticks) < 2:
            return False
        
        recent_low = min(t.price for t in ticks)
        older_ticks = self.get_recent_ticks(50)
        older_ticks = [t for t in older_ticks if t not in ticks]
        
        if not older_ticks:
            return False
        
        prior_low = min(t.price for t in older_ticks)
        return recent_low < prior_low
