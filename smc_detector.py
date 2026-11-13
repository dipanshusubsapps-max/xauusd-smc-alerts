"""
Smart Money Concepts (SMC) Structure Detection Engine.
Detects:
- Bullish & Bearish CHOCH (Change of Character)
- Bullish & Bearish MSS (Market Structure Shift)

Adheres strictly to:
- No repainting (confirmed pivots only)
- Completed candle closes
- Configurable swing lookback, ATR displacement, and confirmation rules
- Unambiguous distinction between CHOCH and MSS
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
    is_high: bool  # True = Swing High, False = Swing Low
    label: str     # 'HH', 'LH', 'HL', 'LL'


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
    SMC Structure Detector.

    Definitions:
    - Swing High: Bar whose high is strictly greater than N bars prior and N bars after.
    - Swing Low: Bar whose low is strictly lower than N bars prior and N bars after.
    - Anti-Repainting Guarantee: A pivot at bar i is only registered after bar i + swing_length has closed.
    
    - Trend State:
      - Bullish Trend: Sequence of Higher Highs (HH) and Higher Lows (HL).
      - Bearish Trend: Sequence of Lower Lows (LL) and Lower Highs (LH).
    
    - CHOCH (Change of Character):
      - Reversal of prevailing major trend structure.
      - Bullish CHOCH: In a Bearish trend (LL/LH), price closes above the most recent confirmed Lower High (LH).
      - Bearish CHOCH: In a Bullish trend (HH/HL), price closes below the most recent confirmed Higher Low (HL).
    
    - MSS (Market Structure Shift):
      - Decisive shift in short-term/internal market structure accompanied by strong displacement.
      - Bullish MSS: Price closes above the most recent confirmed Swing High with displacement (candle range >= mult * ATR).
      - Bearish MSS: Price closes below the most recent confirmed Swing Low with displacement (candle range >= mult * ATR).
    """

    def __init__(
        self,
        swing_length: int = 3,
        min_displacement_atr_mult: float = 1.0,
        atr_period: int = 14,
        require_candle_close: bool = True,
        symbol: str = "XAUUSD",
        timeframe: str = "5m"
    ):
        if swing_length < 1:
            raise ValueError("swing_length must be >= 1")
        self.swing_length = swing_length
        self.min_displacement_atr_mult = min_displacement_atr_mult
        self.atr_period = atr_period
        self.require_candle_close = require_candle_close
        self.symbol = symbol
        self.timeframe = timeframe

    @staticmethod
    def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculates Average True Range (ATR)."""
        high = df['high']
        low = df['low']
        close = df['close']
        prev_close = close.shift(1)

        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        atr = tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
        return atr.fillna(tr.rolling(period, min_periods=1).mean())

    def identify_swings(self, df: pd.DataFrame) -> List[SwingPoint]:
        """
        Identifies confirmed swing highs and lows strictly up to N bars back.
        Guarantees zero repainting.
        """
        n = len(df)
        k = self.swing_length
        swings: List[SwingPoint] = []

        if n < (2 * k + 1):
            return swings

        highs = df['high'].values
        lows = df['low'].values
        timestamps = df['timestamp'].tolist()

        last_swing_high_price: Optional[float] = None
        last_swing_low_price: Optional[float] = None

        for i in range(k, n - k):
            # Check for Swing High
            is_high = True
            current_high = highs[i]
            for offset in range(1, k + 1):
                if highs[i - offset] >= current_high or highs[i + offset] >= current_high:
                    is_high = False
                    break

            # Check for Swing Low
            is_low = True
            current_low = lows[i]
            for offset in range(1, k + 1):
                if lows[i - offset] <= current_low or lows[i + offset] <= current_low:
                    is_low = False
                    break

            if is_high:
                if last_swing_high_price is None:
                    label = "SH"
                elif current_high > last_swing_high_price:
                    label = "HH"  # Higher High
                else:
                    label = "LH"  # Lower High
                last_swing_high_price = current_high
                swings.append(SwingPoint(
                    index=i,
                    timestamp=timestamps[i],
                    price=float(current_high),
                    is_high=True,
                    label=label
                ))

            if is_low:
                if last_swing_low_price is None:
                    label = "SL"
                elif current_low > last_swing_low_price:
                    label = "HL"  # Higher Low
                else:
                    label = "LL"  # Lower Low
                last_swing_low_price = current_low
                swings.append(SwingPoint(
                    index=i,
                    timestamp=timestamps[i],
                    price=float(current_low),
                    is_high=False,
                    label=label
                ))

        swings.sort(key=lambda s: s.index)
        return swings

    def detect_signals(self, df: pd.DataFrame, scan_latest_only: bool = True) -> List[SMCSignal]:
        """
        Scans candle series for newly confirmed CHOCH and MSS structure breaks.
        If scan_latest_only=True, only checks if the MOST RECENT closed candle triggers a break.
        """
        signals: List[SMCSignal] = []
        min_required = 2 * self.swing_length + 1
        if len(df) < min_required:
            return signals

        # Calculate ATR
        df = df.copy()
        df['atr'] = self.calculate_atr(df, period=self.atr_period)

        # Identify all confirmed historical swings
        swings = self.identify_swings(df)
        if not swings:
            return signals

        # Determine indices to scan
        last_closed_idx = len(df) - 1
        indices_to_scan = [last_closed_idx] if scan_latest_only else range(2 * self.swing_length + 1, len(df))

        for idx in indices_to_scan:
            candle = df.iloc[idx]
            candle_close = float(candle['close'])
            candle_high = float(candle['high'])
            candle_low = float(candle['low'])
            candle_open = float(candle['open'])
            candle_atr = float(candle['atr'])
            candle_ts = candle['timestamp']

            candle_range = candle_high - candle_low
            body_size = abs(candle_close - candle_open)
            
            if np.isnan(candle_atr) or candle_atr <= 0:
                candle_atr = max(candle_range, 0.5)

            displacement_ratio = (candle_range / candle_atr) if candle_atr > 0 else 1.0

            # Swings confirmed before or at candle index idx
            # A swing at s.index is confirmed once bar s.index + swing_length has closed.
            # To break a swing at idx, the swing point itself must be prior to idx.
            valid_swings = [s for s in swings if (s.index + self.swing_length) <= idx and s.index < idx]
            if not valid_swings:
                continue

            swing_highs = [s for s in valid_swings if s.is_high]
            swing_lows = [s for s in valid_swings if not s.is_high]

            recent_sh = swing_highs[-1] if swing_highs else None
            recent_sl = swing_lows[-1] if swing_lows else None

            # -------------------------------------------------------------
            # 1. BULLISH BREAKS (Above Swing High)
            # -------------------------------------------------------------
            if recent_sh is not None:
                bullish_break_occurred = False
                if self.require_candle_close:
                    bullish_break_occurred = (candle_close > recent_sh.price)
                else:
                    bullish_break_occurred = (candle_high > recent_sh.price)

                if bullish_break_occurred:
                    prev_candle = df.iloc[idx - 1]
                    prev_close = float(prev_candle['close'])
                    prev_broke = (prev_close > recent_sh.price) if self.require_candle_close else (float(prev_candle['high']) > recent_sh.price)

                    if not prev_broke:
                        is_prevailing_bearish = (recent_sh.label == "LH" or (recent_sl and recent_sl.label == "LL"))
                        if is_prevailing_bearish:
                            explanation = (
                                f"Price closed above key Swing High ({recent_sh.price:.2f}) established at "
                                f"{recent_sh.timestamp.strftime('%H:%M')}, signaling a Bullish Change of Character (CHOCH) "
                                f"and potential macro reversal from downtrend."
                            )
                            signals.append(SMCSignal(
                                signal_type=SignalType.CHOCH,
                                direction=Direction.BULLISH,
                                symbol=self.symbol,
                                timeframe=self.timeframe,
                                candle_timestamp=candle_ts,
                                break_level=recent_sh.price,
                                close_price=candle_close,
                                atr=candle_atr,
                                displacement_ratio=displacement_ratio,
                                confirmed=True,
                                explanation=explanation
                            ))
                        else:
                            has_displacement = (
                                displacement_ratio >= self.min_displacement_atr_mult and
                                candle_close > candle_open and
                                body_size >= (0.35 * candle_range)
                            )
                            if has_displacement:
                                explanation = (
                                    f"Impulsive bullish candle broke above swing high ({recent_sh.price:.2f}) with "
                                    f"{displacement_ratio:.2f}x ATR displacement, confirming a Bullish Market Structure Shift (MSS)."
                                )
                                signals.append(SMCSignal(
                                    signal_type=SignalType.MSS,
                                    direction=Direction.BULLISH,
                                    symbol=self.symbol,
                                    timeframe=self.timeframe,
                                    candle_timestamp=candle_ts,
                                    break_level=recent_sh.price,
                                    close_price=candle_close,
                                    atr=candle_atr,
                                    displacement_ratio=displacement_ratio,
                                    confirmed=True,
                                    explanation=explanation
                                ))

            # -------------------------------------------------------------
            # 2. BEARISH BREAKS (Below Swing Low)
            # -------------------------------------------------------------
            if recent_sl is not None:
                bearish_break_occurred = False
                if self.require_candle_close:
                    bearish_break_occurred = (candle_close < recent_sl.price)
                else:
                    bearish_break_occurred = (candle_low < recent_sl.price)

                if bearish_break_occurred:
                    prev_candle = df.iloc[idx - 1]
                    prev_close = float(prev_candle['close'])
                    prev_broke = (prev_close < recent_sl.price) if self.require_candle_close else (float(prev_candle['low']) < recent_sl.price)

                    if not prev_broke:
                        is_prevailing_bullish = (recent_sl.label == "HL" or (recent_sh and recent_sh.label == "HH"))
                        if is_prevailing_bullish:
                            explanation = (
                                f"Price closed below key Swing Low ({recent_sl.price:.2f}) established at "
                                f"{recent_sl.timestamp.strftime('%H:%M')}, signaling a Bearish Change of Character (CHOCH) "
                                f"and potential macro reversal from uptrend."
                            )
                            signals.append(SMCSignal(
                                signal_type=SignalType.CHOCH,
                                direction=Direction.BEARISH,
                                symbol=self.symbol,
                                timeframe=self.timeframe,
                                candle_timestamp=candle_ts,
                                break_level=recent_sl.price,
                                close_price=candle_close,
                                atr=candle_atr,
                                displacement_ratio=displacement_ratio,
                                confirmed=True,
                                explanation=explanation
                            ))
                        else:
                            has_displacement = (
                                displacement_ratio >= self.min_displacement_atr_mult and
                                candle_close < candle_open and
                                body_size >= (0.35 * candle_range)
                            )
                            if has_displacement:
                                explanation = (
                                    f"Impulsive bearish candle broke below swing low ({recent_sl.price:.2f}) with "
                                    f"{displacement_ratio:.2f}x ATR displacement, confirming a Bearish Market Structure Shift (MSS)."
                                )
                                signals.append(SMCSignal(
                                    signal_type=SignalType.MSS,
                                    direction=Direction.BEARISH,
                                    symbol=self.symbol,
                                    timeframe=self.timeframe,
                                    candle_timestamp=candle_ts,
                                    break_level=recent_sl.price,
                                    close_price=candle_close,
                                    atr=candle_atr,
                                    displacement_ratio=displacement_ratio,
                                    confirmed=True,
                                    explanation=explanation
                                ))

        return signals
