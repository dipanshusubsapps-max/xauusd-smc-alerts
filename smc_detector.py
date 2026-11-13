"""
Smart Money Concepts (SMC) Structure Detection Engine.
Direct 1:1 mathematical implementation of the TradingView Pine Script:
"SMC Market Structure (HH/HL/LH/LL + BOS/CHoCH/MSS)"

Features:
- Exact ta.pivothigh / ta.pivotlow pivot identification
- Trend state tracking: 1 = Bullish, -1 = Bearish, 0 = Unknown
- Continuation (BOS) vs Reversal (CHoCH / MSS)
- MSS = Displacement CHoCH (requires candle close break + body > ATR * dispMult)
- Break confirmation: Wick or Close
- highBroken and lowBroken duplicate suppression on same watched levels
- Strictly zero repainting
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional, Tuple, Dict, Any
import numpy as np
import pandas as pd


class SignalType(Enum):
    CHOCH = "CHOCH"
    MSS = "MSS"


class Direction(Enum):
    BULLISH = "Bullish"
    BEARISH = "Bearish"


@dataclass
class SwingPoint:
    index: int
    timestamp: datetime
    price: float
    is_high: bool
    label: str  # 'HH', 'LH', 'HL', 'LL'


@dataclass
class SMCSignal:
    signal_type: SignalType
    direction: Direction
    symbol: str
    timeframe: str
    candle_timestamp: datetime
    break_level: float
    close_price: float
    atr: float
    displacement_ratio: float
    confirmed: bool
    explanation: str

    @property
    def signal_id(self) -> str:
        """Deterministic unique identifier to prevent duplicate alerts."""
        ts_str = self.candle_timestamp.isoformat()
        return (
            f"{self.symbol}_{self.timeframe}_{self.signal_type.value}_"
            f"{self.direction.value}_{ts_str}_{round(self.break_level, 2)}"
        )


class SMCDetector:
    """
    1:1 Python engine reproducing TradingView Pine Script:
    'SMC Market Structure (HH/HL/LH/LL + BOS/CHoCH/MSS)'
    """

    def __init__(
        self,
        swing_length: int = 3,
        confirmation_mode: str = "wick",  # "wick" or "close"
        atr_period: int = 14,
        min_displacement_atr_mult: float = 1.5,
        symbol: str = "XAUUSD",
        timeframe: str = "5m",
        require_candle_close: Optional[bool] = None
    ):
        self.swing_length = max(1, swing_length)
        if require_candle_close is not None:
            self.confirmation_mode = "close" if require_candle_close else "wick"
        else:
            self.confirmation_mode = confirmation_mode.lower()

        self.atr_period = max(1, atr_period)
        self.min_displacement_atr_mult = float(min_displacement_atr_mult)
        self.symbol = symbol
        self.timeframe = timeframe

    @staticmethod
    def calculate_atr_series(df: pd.DataFrame, period: int = 14) -> np.ndarray:
        """
        TradingView ta.atr() calculation:
        RMA (Wilder's moving average) of True Range.
        """
        n = len(df)
        if n == 0:
            return np.array([], dtype=float)

        highs = df['high'].values
        lows = df['low'].values
        closes = df['close'].values

        tr = np.zeros(n, dtype=float)
        tr[0] = highs[0] - lows[0]
        for i in range(1, n):
            h_l = highs[i] - lows[i]
            h_pc = abs(highs[i] - closes[i - 1])
            l_pc = abs(lows[i] - closes[i - 1])
            tr[i] = max(h_l, h_pc, l_pc)

        # Wilder's RMA: alpha = 1 / period
        alpha = 1.0 / period
        atr = np.zeros(n, dtype=float)
        atr[0] = tr[0]
        for i in range(1, n):
            atr[i] = alpha * tr[i] + (1.0 - alpha) * atr[i - 1]

        return atr

    def detect_signals(self, df: pd.DataFrame, scan_latest_only: bool = True) -> List[SMCSignal]:
        """
        Processes candle series chronologically using exact Pine Script logic.
        """
        n = len(df)
        k = self.swing_length
        min_required = 2 * k + 1
        if n < min_required:
            return []

        highs = df['high'].values
        lows = df['low'].values
        opens = df['open'].values
        closes = df['close'].values
        timestamps = df['timestamp'].tolist()

        atr_series = self.calculate_atr_series(df, period=self.atr_period)

        # Pine Script state variables
        lastHigh: Optional[float] = None
        lastHighBar: Optional[int] = None
        lastLow: Optional[float] = None
        lastLowBar: Optional[int] = None

        highBroken = False
        lowBroken = False
        trend = 0  # 1 = bullish, -1 = bearish, 0 = unknown

        signals_history: List[Tuple[int, SMCSignal]] = []

        # Iterate bar by bar exactly as Pine Script executes on each new bar
        for i in range(n):
            # 1. Swing Detection (Pivots): ta.pivothigh / ta.pivotlow at bar i - k
            gotPH = False
            ph: Optional[float] = None
            gotPL = False
            pl: Optional[float] = None

            pivot_candidate_bar = i - k
            if pivot_candidate_bar >= k:
                # Pivot High check
                cand_high = highs[pivot_candidate_bar]
                is_ph = True
                for offset in range(1, k + 1):
                    if highs[pivot_candidate_bar - offset] >= cand_high or highs[pivot_candidate_bar + offset] > cand_high:
                        is_ph = False
                        break
                if is_ph:
                    gotPH = True
                    ph = float(cand_high)

                # Pivot Low check
                cand_low = lows[pivot_candidate_bar]
                is_pl = True
                for offset in range(1, k + 1):
                    if lows[pivot_candidate_bar - offset] <= cand_low or lows[pivot_candidate_bar + offset] < cand_low:
                        is_pl = False
                        break
                if is_pl:
                    gotPL = True
                    pl = float(cand_low)

            if gotPH:
                lastHigh = ph
                lastHighBar = pivot_candidate_bar
                highBroken = False

            if gotPL:
                lastLow = pl
                lastLowBar = pivot_candidate_bar
                lowBroken = False

            if i < 1:
                continue

            # 2. Break logic
            atrV = atr_series[i]
            if atrV <= 0 or np.isnan(atrV):
                atrV = max(highs[i] - lows[i], 0.5)

            body = abs(closes[i] - opens[i])

            # Displacement
            bullDisp = (closes[i] > opens[i]) and (body > (atrV * self.min_displacement_atr_mult))
            bearDisp = (closes[i] < opens[i]) and (body > (atrV * self.min_displacement_atr_mult))

            # Break conditions (Wick vs Close)
            breakUpClose = (lastHigh is not None) and (closes[i] > lastHigh) and (closes[i - 1] <= lastHigh)
            breakDownClose = (lastLow is not None) and (closes[i] < lastLow) and (closes[i - 1] >= lastLow)

            breakUpWick = (lastHigh is not None) and (highs[i] > lastHigh) and (highs[i - 1] <= lastHigh)
            breakDownWick = (lastLow is not None) and (lows[i] < lastLow) and (lows[i - 1] >= lastLow)

            breakUp = breakUpClose if (self.confirmation_mode == "close") else breakUpWick
            breakDown = breakDownClose if (self.confirmation_mode == "close") else breakDownWick

            # Prevent duplicate breaks on same watched swing level
            breakUp = breakUp and (not highBroken) and (not gotPH)
            breakDown = breakDown and (not lowBroken) and (not gotPL)

            # 3. Classify Break Up
            if breakUp and lastHigh is not None:
                reversal = (trend == -1)
                txt = ""
                if reversal:
                    # MSS requires CLOSE break + displacement
                    isMSS = bullDisp and breakUpClose
                    txt = "MSS" if isMSS else "CHoCH"
                else:
                    txt = "BOS"

                if txt in ("CHoCH", "MSS"):
                    sig_type = SignalType.MSS if (txt == "MSS") else SignalType.CHOCH
                    disp_ratio = (body / atrV) if atrV > 0 else 1.0
                    explanation = (
                        f"Bullish {txt} confirmed at break level {lastHigh:.2f}. "
                        f"Reversal break of previous swing high ({'displacement close' if isMSS else 'structure break'})."
                    )
                    signals_history.append((i, SMCSignal(
                        signal_type=sig_type,
                        direction=Direction.BULLISH,
                        symbol=self.symbol,
                        timeframe=self.timeframe,
                        candle_timestamp=timestamps[i],
                        break_level=lastHigh,
                        close_price=float(closes[i]),
                        atr=float(atrV),
                        displacement_ratio=float(disp_ratio),
                        confirmed=True,
                        explanation=explanation
                    )))

                highBroken = True
                trend = 1

            # 4. Classify Break Down
            if breakDown and lastLow is not None:
                reversal = (trend == 1)
                txt = ""
                if reversal:
                    # MSS requires CLOSE break + displacement
                    isMSS = bearDisp and breakDownClose
                    txt = "MSS" if isMSS else "CHoCH"
                else:
                    txt = "BOS"

                if txt in ("CHoCH", "MSS"):
                    sig_type = SignalType.MSS if (txt == "MSS") else SignalType.CHOCH
                    disp_ratio = (body / atrV) if atrV > 0 else 1.0
                    explanation = (
                        f"Bearish {txt} confirmed at break level {lastLow:.2f}. "
                        f"Reversal break of previous swing low ({'displacement close' if isMSS else 'structure break'})."
                    )
                    signals_history.append((i, SMCSignal(
                        signal_type=sig_type,
                        direction=Direction.BEARISH,
                        symbol=self.symbol,
                        timeframe=self.timeframe,
                        candle_timestamp=timestamps[i],
                        break_level=lastLow,
                        close_price=float(closes[i]),
                        atr=float(atrV),
                        displacement_ratio=float(disp_ratio),
                        confirmed=True,
                        explanation=explanation
                    )))

                lowBroken = True
                trend = -1

        if scan_latest_only:
            # Return only signals confirmed on the latest completed candle
            last_idx = n - 1
            return [sig for (idx, sig) in signals_history if idx == last_idx]
        else:
            return [sig for (idx, sig) in signals_history]
