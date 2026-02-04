# OTC Signal Engine

A local-first, semi-automated trading signal engine for OTC (Over-The-Counter) markets. This system analyzes near-live price data, detects explicit micro-patterns, scores setups using a strict confidence engine, and issues human-confirmable signals.

**This is NOT an auto-trading bot. It does NOT place trades. It ONLY signals.**

## Core Philosophy

- **Selectivity > Frequency** - Quality over quantity
- **Determinism > Intelligence** - Hard-coded rules, NO ML
- **Discipline > Opportunity** - No trade is better than a bad trade
- **OTC Survival** - Brutal filtering for market survival

## Features

- 🎯 **4 OTC Micro-Pattern Detectors** - Impulse-Stall-Snapback, Double Top/Bottom, Momentum Exhaustion, Compression Fakeout
- 📊 **Confidence Scoring Engine** - 0-100 score with A/A+ grading
- 🛡️ **Kill Switch System** - Absolute blocks with no override
- 📈 **Session State Machine** - ACTIVE → CAUTION → LOCKED progression
- ⏱️ **3-Second Countdown** - Eliminates human reaction lag
- 🔊 **Audio/Visual Alerts** - Configurable alert system
- 💻 **Local-First** - No cloud dependency, runs on Windows

## System Requirements

- Windows 10/11
- Python 3.9+
- No internet required for operation

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/otc-signal-engine.git
cd otc-signal-engine
```

### 2. Create Virtual Environment (Recommended)

```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. (Optional) Install Screen Capture Dependencies

For screen capture mode, install additional OCR dependencies:

```bash
pip install pytesseract
```

And install Tesseract OCR: https://github.com/UB-Mannheim/tesseract/wiki

## Quick Start

### Manual Price Input Mode (Recommended for Start)

```bash
cd src
python main.py
```

Enter prices as they appear on your trading platform. The system will analyze patterns and generate signals.

### Simulation Mode (Testing)

```bash
python main.py --simulate
```

Generates simulated price data to test the pattern detection system.

### Screen Capture Mode (Advanced)

```bash
python main.py --screen
```

Requires calibration of screen capture region. Edit `config/settings.py` to set your price region coordinates.

## Usage Workflow

### Daily Workflow

```
1. Pre-Session (5 min before)
   ├── Select primary/secondary pairs
   │   • ≥90% payout
   │   • Clean impulses visible
   │   • Minimal chop
   │   • Good UI responsiveness
   └── Mental preparation

2. Session Start
   ├── Run: python main.py
   ├── Verify status shows 🟢 ACTIVE
   └── Maximum session: 45 minutes

3. During Session
   ├── System scans automatically
   ├── On signal: 3-second countdown
   ├── Execute trade manually
   ├── Record result: (w)in / (l)oss / (s)kip
   └── System updates state

4. Session End (Automatic)
   ├── After 2 wins, OR
   ├── After 1 loss, OR
   └── After 45 minutes
```

### Commands During Operation

| Command  | Description                    |
|----------|--------------------------------|
| `status` | Show current session status    |
| `pairs`  | Show pair selection guidelines |
| `lock`   | Manually lock session          |
| `help`   | Show help information          |
| `quit`   | Exit the engine                |

## Pattern Detection

### Pattern 1: Impulse → Stall → Snapback (A+)

**Detection Requirements (ALL must be true):**
- ≥3 consecutive ticks in one direction
- Total movement ≥ minimum impulse distance
- Stall phase: 2-6 seconds with no new high/low
- Tick size contraction during stall
- No continuation breakout

**Entry:**
- Direction: Opposite to impulse
- Expiry: 5-15 seconds
- Trigger: First tick against impulse

**Automatic Blocks:**
- No stall detected
- Stall duration > 6 seconds
- Whipsaw pattern detected

### Pattern 2: Micro Double-Top / Double-Bottom (A/A+)

**Detection Requirements:**
- Price hits a level
- Small pullback occurs
- Retest within 3-10 seconds
- Second push weaker/slower than first

**Entry:**
- Direction: Reversal
- Expiry: 10-30 seconds
- Trigger: Failure to break level

**Automatic Blocks:**
- Clean break of level
- Retest timing > 10 seconds
- Rising volatility

### Pattern 3: Tick Momentum Exhaustion (A only)

**Detection Requirements:**
- ≥4 consecutive ticks same direction
- Each tick smaller than previous
- Visible speed slowdown

**Entry:**
- Direction: Opposite to exhausted momentum
- Expiry: 5-10 seconds
- Trigger: On smallest tick

**Automatic Blocks:**
- Tick size increases
- Volatility spike detected

### Pattern 4: Flat Compression → Fakeout (A)

**Detection Requirements:**
- Tight range for ≥5 seconds
- Minimal movement during compression
- Sudden breakout tick
- Immediate hesitation after breakout

**Entry:**
- Direction: Opposite to breakout
- Expiry: 10-15 seconds
- Trigger: On hesitation confirmation

**Automatic Blocks:**
- Breakout accelerates (genuine breakout)
- No hesitation detected

## Confidence Scoring

### Score Range: 0-100

| Grade | Score Range | Action                           |
|-------|-------------|----------------------------------|
| A+    | 85-100      | Trade in ANY session state       |
| A     | 75-84       | Trade in ACTIVE state only       |
| Below | <75         | **BLOCKED - NO TRADE**           |

### Score Components

```
Confidence = Pattern Quality (0-30)
           + Tick Consistency (0-20)
           + Volatility Quality (0-20)
           + Timing Bonus (0-15)
           - Noise Penalty (0-15)
```

**Component Details:**

1. **Pattern Quality (0-30)**
   - Textbook formation: 28-30
   - Clear but noisy: 22-27
   - Weak pattern: 15-21
   - Below 15: **BLOCKED**

2. **Tick Consistency (0-20)**
   - Strong alignment: 18-20
   - Mixed signals: 8-13
   - Below 8: **BLOCKED**

3. **Volatility Quality (0-20)**
   - Impulse → compression: 18-20
   - Chaos/spikes: **BLOCKED** if <8

4. **Timing Bonus (0-15)**
   - Hot windows (UTC): 08:00-10:00, 13:00-15:00, 19:00-21:00
   - Dead periods: 00:00-05:00, 11:00-12:00

5. **Noise Penalty (0-15)**
   - UI lag detection
   - Tick latency variance
   - Alternation patterns

## Kill Switches (ABSOLUTE - NO OVERRIDE)

The following conditions **immediately block ALL trading**:

| Condition                  | Threshold                |
|---------------------------|--------------------------|
| Tick Alternation          | >3 times in 5 seconds    |
| Volatility Spike          | >3x recent average       |
| Entry Delay               | >500ms                   |
| Daily Trade Limit         | 2 trades reached         |
| Daily Loss Limit          | 1 loss reached           |
| Daily Win Limit           | 2 wins reached           |
| Unclassifiable Behavior   | No pattern matches       |

## Session State Machine

```
                    ┌──────────────────┐
                    │   🟢 ACTIVE      │
                    │   (A or A+)      │
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
         1st Win        1st Loss      Timeout
              │              │              │
              ▼              │              │
    ┌──────────────────┐     │              │
    │   🟡 CAUTION     │     │              │
    │   (A+ only)      │     │              │
    └────────┬─────────┘     │              │
             │               │              │
    ┌────────┴────────┐      │              │
    │                 │      │              │
Win or Loss      Timeout     │              │
    │                 │      │              │
    ▼                 ▼      ▼              ▼
    ┌─────────────────────────────────────────┐
    │            🔴 LOCKED                     │
    │         (Session Ended)                  │
    └─────────────────────────────────────────┘
```

## Configuration

Edit `config/settings.py` to customize:

### Pattern Detection Thresholds

```python
@dataclass(frozen=True)
class PatternConfig:
    IMPULSE_MIN_TICKS: int = 3
    IMPULSE_MIN_DISTANCE_PIPS: float = 5.0
    STALL_MIN_DURATION_SEC: float = 2.0
    STALL_MAX_DURATION_SEC: float = 6.0
    # ... more settings
```

### Session Limits

```python
@dataclass(frozen=True)
class KillSwitchConfig:
    MAX_TRADES_PER_DAY: int = 2
    MAX_LOSSES_PER_DAY: int = 1
    MAX_WINS_PER_DAY: int = 2
```

### Screen Capture Region (for screen mode)

```python
@dataclass(frozen=True)
class DataConfig:
    PRICE_REGION_X: int = 0      # X coordinate
    PRICE_REGION_Y: int = 0      # Y coordinate
    PRICE_REGION_WIDTH: int = 200
    PRICE_REGION_HEIGHT: int = 50
```

## Project Structure

```
otc-signal-engine/
├── config/
│   ├── __init__.py
│   └── settings.py          # All configuration
├── src/
│   ├── __init__.py
│   ├── main.py              # Entry point
│   ├── data/
│   │   ├── __init__.py
│   │   ├── tick_buffer.py   # Price data storage
│   │   └── price_capture.py # Price input methods
│   ├── patterns/
│   │   ├── __init__.py
│   │   ├── base_pattern.py
│   │   ├── impulse_stall_snapback.py
│   │   ├── micro_double_top_bottom.py
│   │   ├── tick_momentum_exhaustion.py
│   │   └── flat_compression_fakeout.py
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── confidence_scorer.py
│   │   ├── kill_switches.py
│   │   └── pattern_detector.py
│   ├── state/
│   │   ├── __init__.py
│   │   ├── session_state.py
│   │   └── trade_limits.py
│   ├── signals/
│   │   ├── __init__.py
│   │   ├── signal_generator.py
│   │   └── countdown.py
│   └── ui/
│       ├── __init__.py
│       └── alert_display.py
├── requirements.txt
└── README.md
```

## Troubleshooting

### No signals generated

1. Check if session is in ACTIVE state
2. Ensure price data is being received (ticks appearing)
3. Current market may not have qualifying patterns
4. **This is often correct behavior** - no trade days are SUCCESS

### Sound not working

- Only works on Windows
- Install winsound (should be built-in)
- Use `--no-sound` flag to disable

### Screen capture not working

1. Install Tesseract OCR
2. Configure correct screen region in settings
3. Ensure price area has clear, readable numbers
4. Consider using manual mode instead

### High noise penalty

- Check your system performance
- Close unnecessary applications
- Use wired mouse/keyboard
- Consider lower tick rates

## Important Notes

### What This System Does NOT Do

- ❌ Place trades automatically
- ❌ Connect to broker APIs
- ❌ Use machine learning
- ❌ Use technical indicators (RSI, EMA, etc.)
- ❌ Require internet connection
- ❌ Store or transmit any data

### Design Principles

- **Boring is good** - Few signals, high quality
- **No trade = success** - Discipline enforcement
- **Deterministic** - Same inputs = same outputs
- **Human in the loop** - You execute, system advises

## Success Metrics

Your usage of this system is successful when:

- ✅ System runs locally without issues
- ✅ Signals are rare (1-2 per day max)
- ✅ No-trade days are common
- ✅ Discipline is enforced automatically
- ✅ Human error is minimized
- ✅ **You find the system boring** - that's a feature

## License

MIT License - Use at your own risk. This software provides signals only and does not guarantee trading success.

## Disclaimer

This software is for educational and informational purposes only. Trading OTC markets involves substantial risk of loss. Past performance is not indicative of future results. The authors accept no responsibility for any financial losses incurred through the use of this software.
