"""KPI value generator for steelmaking operations.

This module generates realistic KPI values based on KPI definitions,
considering digit constraints, limits, and typical real-world patterns.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional


@dataclass
class KpiStat:
    """Represents a single KPI statistic record."""
    heat_no: int
    pro_line_cd: str
    proc_cd: str
    device_no: str
    kpi_code: str
    stat_value: Optional[Decimal]
    sample_time: datetime
    extra: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database insertion."""
        return {
            "heat_no": self.heat_no,
            "pro_line_cd": self.pro_line_cd,
            "proc_cd": self.proc_cd,
            "device_no": self.device_no,
            "kpi_code": self.kpi_code,
            "stat_value": self.stat_value,
            "sample_time": self.sample_time,
            "extra": self.extra,
        }


class KpiValueGenerator:
    """Generates realistic KPI values based on KPI definitions.
    
    The generator considers:
    - int_digits and decimal_digits for value formatting
    - upper_limit and lower_limit for value range
    - Occasional values exceeding limits to simulate real-world scenarios
    - KPI-specific patterns (e.g., temperatures, rates, percentages)
    """
    
    def __init__(
        self,
        *,
        out_of_range_probability: float = 0.05,
        out_of_range_factor: float = 0.15,
    ):
        """Initialize the KPI value generator.
        
        Args:
            out_of_range_probability: Probability of generating a value outside limits
            out_of_range_factor: How much beyond limits out-of-range values can go (0.15 = 15%)
        """
        self.out_of_range_probability = out_of_range_probability
        self.out_of_range_factor = out_of_range_factor
    
    def generate_value(
        self,
        kpi_def: Dict[str, Any],
        *,
        progress: float = 0.5,
        previous_value: Optional[Decimal] = None,
    ) -> Optional[Decimal]:
        """Generate a realistic value for a KPI definition.
        
        Args:
            kpi_def: KPI definition dict with upper_limit, lower_limit, etc.
            progress: Operation progress (0.0 to 1.0), affects value generation
            previous_value: Previous value for this KPI, used for continuity
            
        Returns:
            Generated value as Decimal, or None if both limits are None
        """
        upper_limit = kpi_def.get("upper_limit")
        lower_limit = kpi_def.get("lower_limit")
        int_digits = kpi_def.get("int_digits", 6)
        decimal_digits = kpi_def.get("decimal_digits", 2)
        kpi_code = kpi_def.get("kpi_code", "")
        
        # Handle cases where limits are None
        if upper_limit is None and lower_limit is None:
            return None
        
        # Convert to float for calculations
        upper = float(upper_limit) if upper_limit is not None else None
        lower = float(lower_limit) if lower_limit is not None else 0.0
        
        if upper is None:
            # Estimate upper based on int_digits
            upper = 10 ** int_digits - 1
        
        # Calculate base value range
        base_value = self._generate_base_value(
            kpi_code=kpi_code,
            lower=lower,
            upper=upper,
            progress=progress,
            previous_value=float(previous_value) if previous_value is not None else None,
        )
        
        # Apply out-of-range variation occasionally
        if random.random() < self.out_of_range_probability:
            base_value = self._apply_out_of_range(base_value, lower, upper)
        
        # Round to specified decimal places
        return self._format_value(base_value, decimal_digits)
    
    def _generate_base_value(
        self,
        *,
        kpi_code: str,
        lower: float,
        upper: float,
        progress: float,
        previous_value: Optional[float],
    ) -> float:
        """Generate the base value based on KPI type and context."""
        range_size = upper - lower
        
        # Identify KPI type from code
        kpi_upper = kpi_code.upper()
        
        # Temperature KPIs - typically in operating range, gradual changes
        if "_T_" in kpi_upper or "_TEMP" in kpi_upper:
            return self._generate_temperature_value(lower, upper, progress, previous_value)
        
        # Rate/flow KPIs - can vary more widely
        if "_RATE" in kpi_upper or "_FLOW" in kpi_upper:
            return self._generate_rate_value(lower, upper, progress, previous_value)
        
        # Cumulative/total KPIs - increase with progress
        if "_TOTAL" in kpi_upper or "_CUM" in kpi_upper:
            return self._generate_cumulative_value(lower, upper, progress)
        
        # Percentage/efficiency KPIs
        if "_PCT" in kpi_upper or "_RATE" in kpi_upper.split("_")[-1]:
            return self._generate_percentage_value(lower, upper, progress)
        
        # Deviation KPIs - centered around 0 or small values
        if "_DEV" in kpi_upper:
            return self._generate_deviation_value(lower, upper)
        
        # Chemical composition KPIs
        if "_CHEM_" in kpi_upper or kpi_upper.endswith("_PV"):
            return self._generate_chemical_value(lower, upper, progress)
        
        # Default: random value within range with some clustering
        center = lower + range_size * 0.5
        if previous_value is not None:
            # Trend towards previous value with some drift
            center = previous_value + random.gauss(0, range_size * 0.05)
            center = max(lower, min(upper, center))
        
        return random.gauss(center, range_size * 0.15)
    
    def _generate_temperature_value(
        self,
        lower: float,
        upper: float,
        progress: float,
        previous_value: Optional[float],
    ) -> float:
        """Generate temperature-like values (gradual changes, operating range)."""
        range_size = upper - lower
        
        # Temperatures typically stay in a working range (middle 60% of range)
        working_lower = lower + range_size * 0.2
        working_upper = upper - range_size * 0.2
        
        if previous_value is not None:
            # Small drift from previous value
            drift = random.gauss(0, range_size * 0.02)
            value = previous_value + drift
        else:
            # Start in working range
            value = random.uniform(working_lower, working_upper)
        
        # Temperature may increase slightly during operation
        if progress > 0.3:
            value += random.uniform(0, range_size * 0.05 * progress)
        
        return max(lower, min(upper, value))
    
    def _generate_rate_value(
        self,
        lower: float,
        upper: float,
        progress: float,
        previous_value: Optional[float],
    ) -> float:
        """Generate rate/flow values (can vary, sometimes zero)."""
        range_size = upper - lower
        
        # Rates can sometimes be zero or near zero
        if random.random() < 0.1:
            return lower + random.uniform(0, range_size * 0.1)
        
        # Typically in middle-high range during operation
        center = lower + range_size * (0.4 + progress * 0.2)
        
        if previous_value is not None:
            # Rates can change more abruptly than temperatures
            drift = random.gauss(0, range_size * 0.1)
            value = previous_value + drift
            # Mix with expected center
            value = 0.7 * value + 0.3 * center
        else:
            value = random.gauss(center, range_size * 0.2)
        
        return max(lower, min(upper, value))
    
    def _generate_cumulative_value(
        self,
        lower: float,
        upper: float,
        progress: float,
    ) -> float:
        """Generate cumulative values (increase with progress)."""
        # Cumulative values increase with operation progress
        range_size = upper - lower
        
        # Base on progress with some variation
        target = lower + range_size * progress
        variation = random.gauss(0, range_size * 0.05)
        
        return max(lower, min(upper, target + variation))
    
    def _generate_percentage_value(
        self,
        lower: float,
        upper: float,
        progress: float,
    ) -> float:
        """Generate percentage values (0-100 or similar)."""
        range_size = upper - lower
        
        # Percentages often cluster in certain ranges
        if random.random() < 0.7:
            # Common range: 30-80% of scale
            effective_lower = lower + range_size * 0.3
            effective_upper = lower + range_size * 0.8
            return random.uniform(effective_lower, effective_upper)
        else:
            # Occasional extreme values
            return random.uniform(lower, upper)
    
    def _generate_deviation_value(
        self,
        lower: float,
        upper: float,
    ) -> float:
        """Generate deviation values (centered around 0)."""
        # Deviations are typically small, centered around 0
        range_size = upper - lower
        center = (lower + upper) / 2
        
        # Most deviations are small
        if random.random() < 0.8:
            return random.gauss(center, range_size * 0.1)
        else:
            return random.gauss(center, range_size * 0.3)
    
    def _generate_chemical_value(
        self,
        lower: float,
        upper: float,
        progress: float,
    ) -> float:
        """Generate chemical composition values."""
        range_size = upper - lower
        
        # Chemical values typically stay in target range
        center = lower + range_size * 0.4
        
        # May change during operation (e.g., carbon decreases in BOF)
        if progress > 0.5:
            center -= range_size * 0.1 * (progress - 0.5)
        
        return max(lower, min(upper, random.gauss(center, range_size * 0.15)))
    
    def _apply_out_of_range(
        self,
        value: float,
        lower: float,
        upper: float,
    ) -> float:
        """Apply out-of-range variation to simulate anomalies."""
        range_size = upper - lower
        extension = range_size * self.out_of_range_factor
        
        # Decide whether to go above or below range
        if random.random() < 0.5 and upper + extension > value:
            return upper + random.uniform(0, extension)
        else:
            return lower - random.uniform(0, extension)
    
    def _format_value(self, value: float, decimal_digits: int) -> Decimal:
        """Format value to specified decimal places."""
        quantize_str = f"0.{'0' * decimal_digits}" if decimal_digits > 0 else "0"
        return Decimal(str(value)).quantize(Decimal(quantize_str), rounding=ROUND_HALF_UP)
    
    def generate_stats_for_operation(
        self,
        *,
        heat_no: int,
        pro_line_cd: str,
        proc_cd: str,
        device_no: str,
        kpi_definitions: List[Dict[str, Any]],
        sample_time: datetime,
        progress: float = 0.5,
        previous_stats: Optional[Dict[str, Decimal]] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> List[KpiStat]:
        """Generate KPI stats for all definitions at a given sample time.
        
        Args:
            heat_no: Heat number
            pro_line_cd: Production line code
            proc_cd: Process code
            device_no: Device number
            kpi_definitions: List of KPI definition dicts
            sample_time: Sample timestamp
            progress: Operation progress (0.0 to 1.0)
            previous_stats: Previous values by kpi_code for continuity
            extra: Optional extra data to include
            
        Returns:
            List of KpiStat objects
        """
        previous_stats = previous_stats or {}
        stats = []
        
        for kpi_def in kpi_definitions:
            kpi_code = kpi_def["kpi_code"]
            previous_value = previous_stats.get(kpi_code)
            
            value = self.generate_value(
                kpi_def,
                progress=progress,
                previous_value=previous_value,
            )
            
            if value is not None:
                stat = KpiStat(
                    heat_no=heat_no,
                    pro_line_cd=pro_line_cd,
                    proc_cd=proc_cd,
                    device_no=device_no,
                    kpi_code=kpi_code,
                    stat_value=value,
                    sample_time=sample_time,
                    extra=extra,
                )
                stats.append(stat)
        
        return stats
