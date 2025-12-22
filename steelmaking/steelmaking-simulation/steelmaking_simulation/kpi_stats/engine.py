"""KPI statistics engine for steelmaking operations.

This module handles both historical KPI stats seeding and real-time KPI 
generation during simulation ticks. It manages the lifecycle of KPI stats
for active operations and integrates with the simulator's tick loop.
"""

from __future__ import annotations

import random
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Protocol

from ..config import SimulationConfig, PRO_LINE_CD
from .generator import KpiValueGenerator, KpiStat


class _ProcessNameResolver(Protocol):
    def __call__(self, proc_cd: str) -> Optional[str]: ...


@dataclass
class KpiStatsEngineConfig:
    """Configuration for KPI statistics generation."""
    
    # Probability of generating KPI stats for a completed operation during seeding
    seed_kpi_stats_probability: float = float(
        os.getenv("SEED_KPI_STATS_PROBABILITY", "0.95")
    )
    
    # Min/max number of sample points per operation for historical seeding
    min_samples_per_operation: int = int(
        os.getenv("MIN_KPI_SAMPLES_PER_OPERATION", "5")
    )
    max_samples_per_operation: int = int(
        os.getenv("MAX_KPI_SAMPLES_PER_OPERATION", "15")
    )
    
    # Probability of emitting KPI stats during a tick for active operations
    kpi_probability_per_tick: float = float(
        os.getenv("KPI_PROBABILITY_PER_TICK", "0.4")
    )
    
    # Minimum interval between KPI samples for the same operation (seconds)
    min_sample_interval_seconds: int = int(
        os.getenv("MIN_KPI_SAMPLE_INTERVAL_SECONDS", "30")
    )
    
    # Maximum number of KPI sample batches per active operation during realtime
    max_realtime_samples_per_operation: int = int(
        os.getenv("MAX_REALTIME_KPI_SAMPLES_PER_OPERATION", "50")
    )
    
    # Probability of values exceeding limits
    out_of_range_probability: float = float(
        os.getenv("KPI_OUT_OF_RANGE_PROBABILITY", "0.05")
    )
    
    # Factor for how much values can exceed limits (0.15 = 15% beyond)
    out_of_range_factor: float = float(
        os.getenv("KPI_OUT_OF_RANGE_FACTOR", "0.15")
    )


@dataclass
class OperationKpiState:
    """Tracks KPI generation state for an active operation."""
    operation_id: int
    heat_no: int
    proc_cd: str
    device_no: str
    start_time: datetime
    last_sample_time: Optional[datetime] = None
    sample_count: int = 0
    previous_values: Dict[str, Decimal] = field(default_factory=dict)


class KpiStatsEngine:
    """Manages KPI statistics generation for steelmaking operations."""
    
    def __init__(
        self,
        *,
        db,
        config: SimulationConfig,
        kpi_config: Optional[KpiStatsEngineConfig] = None,
        get_process_name: _ProcessNameResolver,
        logger,
    ):
        self.db = db
        self.config = config
        self.kpi_config = kpi_config or KpiStatsEngineConfig()
        self.get_process_name = get_process_name
        self.logger = logger
        
        self.generator = KpiValueGenerator(
            out_of_range_probability=self.kpi_config.out_of_range_probability,
            out_of_range_factor=self.kpi_config.out_of_range_factor,
        )
        
        # Cache for KPI definitions by proc_cd
        self._kpi_definitions_cache: Dict[str, List[Dict[str, Any]]] = {}
        
        # Track state for active operations
        self._operation_states: Dict[int, OperationKpiState] = {}
    
    def load_kpi_definitions(self) -> None:
        """Load KPI definitions from database and cache them."""
        try:
            self._kpi_definitions_cache = self.db.get_all_kpi_definitions()
            total_count = sum(len(defs) for defs in self._kpi_definitions_cache.values())
            self.logger.info(
                "Loaded %d KPI definitions for %d process codes",
                total_count,
                len(self._kpi_definitions_cache),
            )
        except Exception as e:
            self.logger.warning("Failed to load KPI definitions: %s", e)
            self._kpi_definitions_cache = {}
    
    def get_kpi_definitions(self, proc_cd: str) -> List[Dict[str, Any]]:
        """Get KPI definitions for a process code (from cache or DB)."""
        if proc_cd not in self._kpi_definitions_cache:
            try:
                defs = self.db.get_kpi_definitions_by_proc_cd(proc_cd)
                self._kpi_definitions_cache[proc_cd] = defs
            except Exception as e:
                self.logger.warning("Failed to fetch KPI definitions for %s: %s", proc_cd, e)
                return []
        return self._kpi_definitions_cache.get(proc_cd, [])
    
    def seed_historical_kpi_stats_for_completed_operation(
        self,
        *,
        operation_id: Optional[int],
        heat_no: int,
        pro_line_cd: str,
        proc_cd: str,
        device_no: str,
        window_start: datetime,
        window_end: datetime,
    ) -> int:
        """Seed historical KPI stats for a completed operation.
        
        Args:
            operation_id: Operation ID (optional)
            heat_no: Heat number
            pro_line_cd: Production line code
            proc_cd: Process code
            device_no: Device number
            window_start: Operation start time
            window_end: Operation end time
            
        Returns:
            Number of KPI stats records inserted
        """
        if window_start is None or window_end is None or window_end <= window_start:
            return 0
        
        # Probabilistically skip some operations
        if random.random() >= self.kpi_config.seed_kpi_stats_probability:
            return 0
        
        kpi_definitions = self.get_kpi_definitions(proc_cd)
        if not kpi_definitions:
            return 0
        
        # Determine number of sample points
        num_samples = random.randint(
            self.kpi_config.min_samples_per_operation,
            self.kpi_config.max_samples_per_operation,
        )
        
        total_seconds = (window_end - window_start).total_seconds()
        if total_seconds <= 1 or num_samples < 1:
            return 0
        
        # Generate sample times distributed across the operation window
        sample_times = self._generate_sample_times(
            window_start, window_end, num_samples
        )
        
        all_stats: List[Dict[str, Any]] = []
        previous_values: Dict[str, Decimal] = {}
        
        for i, sample_time in enumerate(sample_times):
            progress = i / max(1, num_samples - 1)
            
            stats = self.generator.generate_stats_for_operation(
                heat_no=heat_no,
                pro_line_cd=pro_line_cd,
                proc_cd=proc_cd,
                device_no=device_no,
                kpi_definitions=kpi_definitions,
                sample_time=sample_time,
                progress=progress,
                previous_stats=previous_values,
                extra={"operation_id": operation_id} if operation_id else None,
            )
            
            # Update previous values for continuity
            for stat in stats:
                previous_values[stat.kpi_code] = stat.stat_value
                all_stats.append(stat.to_dict())
        
        if not all_stats:
            return 0
        
        count = self.db.insert_kpi_stats_batch(all_stats)
        self.logger.debug(
            "Seeded %d historical KPI stats for heat %s proc %s (%d samples)",
            count, heat_no, proc_cd, num_samples
        )
        return count
    
    def seed_partial_kpi_stats_for_active_operation(
        self,
        *,
        operation_id: Optional[int],
        heat_no: int,
        pro_line_cd: str,
        proc_cd: str,
        device_no: str,
        window_start: datetime,
        now: datetime,
    ) -> int:
        """Seed partial KPI stats for an active (in-progress) operation.
        
        When initializing, active operations should have some KPI stats generated
        from operation start up to current time.
        
        Args:
            operation_id: Operation ID (optional)
            heat_no: Heat number
            pro_line_cd: Production line code
            proc_cd: Process code
            device_no: Device number
            window_start: Operation start time (real_start_time)
            now: Current time
            
        Returns:
            Number of KPI stats records inserted
        """
        if window_start is None or now is None or now <= window_start:
            return 0
        
        kpi_definitions = self.get_kpi_definitions(proc_cd)
        if not kpi_definitions:
            return 0
        
        elapsed_seconds = (now - window_start).total_seconds()
        
        # Calculate number of samples based on elapsed time
        # Aim for roughly one sample every minute
        estimated_samples = max(1, int(elapsed_seconds / 60))
        num_samples = min(
            estimated_samples,
            self.kpi_config.max_samples_per_operation // 2,  # Leave room for more during operation
        )
        
        sample_times = self._generate_sample_times(window_start, now, num_samples)
        
        all_stats: List[Dict[str, Any]] = []
        previous_values: Dict[str, Decimal] = {}
        
        # Estimate total operation duration for progress calculation
        expected_duration = timedelta(
            minutes=(self.config.min_operation_duration + self.config.max_operation_duration) / 2
        )
        
        for i, sample_time in enumerate(sample_times):
            time_into_op = (sample_time - window_start).total_seconds()
            progress = min(1.0, time_into_op / expected_duration.total_seconds())
            
            stats = self.generator.generate_stats_for_operation(
                heat_no=heat_no,
                pro_line_cd=pro_line_cd,
                proc_cd=proc_cd,
                device_no=device_no,
                kpi_definitions=kpi_definitions,
                sample_time=sample_time,
                progress=progress,
                previous_stats=previous_values,
                extra={"operation_id": operation_id} if operation_id else None,
            )
            
            for stat in stats:
                previous_values[stat.kpi_code] = stat.stat_value
                all_stats.append(stat.to_dict())
        
        if not all_stats:
            return 0
        
        count = self.db.insert_kpi_stats_batch(all_stats)
        
        # Initialize state for this operation
        if operation_id:
            self._operation_states[operation_id] = OperationKpiState(
                operation_id=operation_id,
                heat_no=heat_no,
                proc_cd=proc_cd,
                device_no=device_no,
                start_time=window_start,
                last_sample_time=sample_times[-1] if sample_times else now,
                sample_count=num_samples,
                previous_values=previous_values,
            )
        
        self.logger.debug(
            "Seeded %d partial KPI stats for active heat %s proc %s",
            count, heat_no, proc_cd
        )
        return count
    
    def tick_realtime_kpi_stats(self, now: datetime) -> None:
        """Generate real-time KPI stats for active operations during tick.
        
        This method is called during each simulation tick to potentially
        generate new KPI statistics for active operations.
        
        Args:
            now: Current simulation time
        """
        active_ops = self.db.get_active_operations()
        
        for op in active_ops:
            if random.random() >= self.kpi_config.kpi_probability_per_tick:
                continue
            
            self._emit_kpi_stats_for_operation(op, now)
    
    def _emit_kpi_stats_for_operation(
        self,
        operation: Dict[str, Any],
        now: datetime,
    ) -> int:
        """Emit KPI stats for a single active operation.
        
        Args:
            operation: Operation dict from database
            now: Current simulation time
            
        Returns:
            Number of KPI stats inserted
        """
        operation_id = operation["id"]
        heat_no = operation["heat_no"]
        proc_cd = operation["proc_cd"]
        device_no = operation["device_no"]
        pro_line_cd = operation.get("pro_line_cd", PRO_LINE_CD)
        
        start_time = operation.get("real_start_time") or operation.get("plan_start_time")
        if start_time is None:
            return 0
        
        # Get or create operation state
        state = self._operation_states.get(operation_id)
        if state is None:
            state = OperationKpiState(
                operation_id=operation_id,
                heat_no=heat_no,
                proc_cd=proc_cd,
                device_no=device_no,
                start_time=start_time,
            )
            self._operation_states[operation_id] = state
        
        # Check if we've exceeded max samples
        if state.sample_count >= self.kpi_config.max_realtime_samples_per_operation:
            return 0
        
        # Check minimum sample interval
        if state.last_sample_time is not None:
            elapsed_since_last = (now - state.last_sample_time).total_seconds()
            if elapsed_since_last < self.kpi_config.min_sample_interval_seconds:
                return 0
        
        kpi_definitions = self.get_kpi_definitions(proc_cd)
        if not kpi_definitions:
            return 0
        
        # Calculate operation progress
        expected_duration = timedelta(
            minutes=(self.config.min_operation_duration + self.config.max_operation_duration) / 2
        )
        elapsed = (now - start_time).total_seconds()
        progress = min(1.0, elapsed / expected_duration.total_seconds())
        
        stats = self.generator.generate_stats_for_operation(
            heat_no=heat_no,
            pro_line_cd=pro_line_cd,
            proc_cd=proc_cd,
            device_no=device_no,
            kpi_definitions=kpi_definitions,
            sample_time=now,
            progress=progress,
            previous_stats=state.previous_values,
            extra={"operation_id": operation_id},
        )
        
        if not stats:
            return 0
        
        # Update state
        for stat in stats:
            state.previous_values[stat.kpi_code] = stat.stat_value
        state.last_sample_time = now
        state.sample_count += 1
        
        # Insert stats
        stat_dicts = [s.to_dict() for s in stats]
        count = self.db.insert_kpi_stats_batch(stat_dicts)
        
        self.logger.debug(
            "Emitted %d realtime KPI stats for heat %s proc %s (sample #%d)",
            count, heat_no, proc_cd, state.sample_count
        )
        return count
    
    def cleanup_completed_operation(self, operation_id: int) -> None:
        """Clean up state for a completed operation.
        
        Args:
            operation_id: ID of the completed operation
        """
        if operation_id in self._operation_states:
            del self._operation_states[operation_id]
    
    def _generate_sample_times(
        self,
        start: datetime,
        end: datetime,
        num_samples: int,
    ) -> List[datetime]:
        """Generate sample times distributed across a time window.
        
        Times are distributed with some randomness to simulate real-world
        sampling patterns.
        
        Args:
            start: Window start time
            end: Window end time
            num_samples: Number of samples to generate
            
        Returns:
            List of sample timestamps
        """
        if num_samples <= 0:
            return []
        
        if num_samples == 1:
            # Single sample in the middle
            mid = start + (end - start) / 2
            return [mid]
        
        total_seconds = (end - start).total_seconds()
        interval = total_seconds / num_samples
        
        times = []
        for i in range(num_samples):
            base_offset = interval * (i + 0.5)  # Center of each interval
            jitter = random.uniform(-interval * 0.3, interval * 0.3)
            offset = max(0, min(total_seconds, base_offset + jitter))
            times.append(start + timedelta(seconds=offset))
        
        return sorted(times)
