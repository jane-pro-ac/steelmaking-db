"""Event engine for steelmaking operations.

This module handles both historical event seeding and real-time event generation
during simulation ticks. It wraps the EventGenerator and manages event insertion
into the database.

Special Events:
- 取消 (cancel): When a cancel event occurs, the operation is marked as canceled,
  and all subsequent operations for the same heat are also canceled.
- 回炉 (rework): When a rework event occurs, the operation continues to completion,
  but a callback is triggered to handle rework logic.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import Counter
from typing import Any, Callable, Dict, List, Optional, Protocol

from ..config import PRO_LINE_CD, SimulationConfig, CANCEL_EVENT_PROBABILITY, REWORK_EVENT_PROBABILITY
from .generator import Event, EventGenerator, EventSequenceResult, SpecialEventType
from .codes import EVENT_CODES, PROC_CD_TO_NAME
from .sequences import EVENT_SEQUENCE_CONFIGS
from .messages import EventMessageGenerator


class _ProcessNameResolver(Protocol):
    def __call__(self, proc_cd: str) -> Optional[str]: ...


class _SpecialEventCallback(Protocol):
    """Callback protocol for handling special events."""
    def __call__(
        self,
        operation_id: Optional[int],
        heat_no: int,
        proc_cd: str,
        event_type: SpecialEventType,
        event_time: datetime,
    ) -> None: ...


@dataclass
class EventEngineConfig:
    """Configuration for event generation."""
    # Min/max events per operation for historical seeding
    min_events_per_operation: int = 8
    max_events_per_operation: int = 20
    
    # Probability of seeding events for a completed operation
    seed_event_probability_per_completed_operation: float = 0.95
    
    # Max events that can be generated during real-time for active operations
    max_realtime_events_per_operation: int = 15
    
    # Probability of emitting an event during a tick
    event_probability_per_tick: float = 0.3
    
    # Probability of cancel/rework events during historical seeding
    # These are per-operation probabilities
    cancel_event_probability: float = CANCEL_EVENT_PROBABILITY
    rework_event_probability: float = REWORK_EVENT_PROBABILITY


class EventEngine:
    """Manages event generation for steelmaking operations."""
    
    def __init__(
        self,
        *,
        db,
        config: SimulationConfig,
        event_config: Optional[EventEngineConfig] = None,
        get_process_name: _ProcessNameResolver,
        logger,
        on_special_event: Optional[_SpecialEventCallback] = None,
    ):
        self.db = db
        self.config = config
        self.event_config = event_config or EventEngineConfig()
        self.get_process_name = get_process_name
        self.logger = logger
        self.on_special_event = on_special_event
        
        self.generator = EventGenerator(
            min_events_per_operation=self.event_config.min_events_per_operation,
            max_events_per_operation=self.event_config.max_events_per_operation,
            cancel_probability=self.event_config.cancel_event_probability,
            rework_probability=self.event_config.rework_event_probability,
        )

    @staticmethod
    def _pending_paired_end_codes(existing_events: List[Dict[str, Any]], config) -> List[str]:
        counts = Counter(e["event_code"] for e in existing_events)
        pending: List[str] = []
        for start_code, end_code in config.paired_events:
            missing = counts.get(start_code, 0) - counts.get(end_code, 0)
            if missing > 0:
                pending.extend([end_code] * missing)
        return pending

    @staticmethod
    def _paired_end_time(start_time: datetime, now: datetime) -> datetime:
        end_time = min(now, start_time + timedelta(seconds=1))
        if end_time < start_time:
            end_time = start_time
        return end_time

    def _append_missing_paired_end_events(
        self,
        *,
        events_to_insert: List[Dict[str, Any]],
        config,
        event_lookup: Dict[str, Any],
        heat_no: int,
        pro_line_cd: str,
        proc_cd: str,
        device_no: str,
        operation_id: Optional[int],
        now: datetime,
    ) -> None:
        start_events: Dict[str, List[Dict[str, Any]]] = {}
        counts = Counter()
        pair_start_to_end = dict(config.paired_events)

        for event in events_to_insert:
            code = event["event_code"]
            counts[code] += 1
            if code in pair_start_to_end:
                start_events.setdefault(code, []).append(event)

        for start_code, end_code in config.paired_events:
            starts = start_events.get(start_code, [])
            missing = len(starts) - counts.get(end_code, 0)
            if missing <= 0:
                continue
            event_info = event_lookup.get(end_code)
            if not event_info:
                continue
            code, name, p1, p2, p3, p4 = event_info
            for start_event in starts[-missing:]:
                start_time = start_event["event_time_start"]
                end_time = self._paired_end_time(start_time, now)
                msg = EventMessageGenerator.generate_message(code, name, p1, p2, p3, p4)
                events_to_insert.append({
                    "heat_no": heat_no,
                    "pro_line_cd": pro_line_cd,
                    "proc_cd": proc_cd,
                    "device_no": device_no,
                    "event_code": end_code,
                    "event_name": name,
                    "event_msg": msg,
                    "event_time_start": end_time,
                    "event_time_end": end_time,
                    "extra": {"operation_id": operation_id} if operation_id else None,
                })
    
    def seed_historical_events_for_completed_operation(
        self,
        *,
        operation_id: Optional[int],
        heat_no: int,
        pro_line_cd: str,
        proc_cd: str,
        device_no: str,
        window_start: datetime,
        window_end: datetime,
        force_cancel: bool = False,
        force_rework: bool = False,
    ) -> EventSequenceResult:
        """Seed historical events for a completed operation.
        
        Args:
            operation_id: Operation ID (optional)
            heat_no: Heat number
            pro_line_cd: Production line code
            proc_cd: Process code
            device_no: Device number
            window_start: Operation start time
            window_end: Operation end time
            force_cancel: Force a cancel event
            force_rework: Force a rework event
        
        Returns:
            EventSequenceResult with events and special event info
        """
        if window_start is None or window_end is None or window_end <= window_start:
            return EventSequenceResult(events=[])
        
        # Probabilistically skip some operations
        if random.random() >= self.event_config.seed_event_probability_per_completed_operation:
            return EventSequenceResult(events=[])
        
        # Generate events
        events = self.generator.generate_event_sequence(
            heat_no=heat_no,
            pro_line_cd=pro_line_cd,
            proc_cd=proc_cd,
            device_no=device_no,
            start_time=window_start,
            end_time=window_end,
            force_cancel=force_cancel,
            force_rework=force_rework,
        )
        
        if not events:
            return EventSequenceResult(events=[])
        
        # Create result with special event info
        result = EventSequenceResult.from_events(events)
        
        # Convert Event objects to dicts for batch insert
        event_dicts = [
            {
                "heat_no": e.heat_no,
                "pro_line_cd": e.pro_line_cd,
                "proc_cd": e.proc_cd,
                "device_no": e.device_no,
                "event_code": e.event_code,
                "event_name": e.event_name,
                "event_msg": e.event_msg,
                "event_time_start": e.event_time_start,
                "event_time_end": e.event_time_end,
                "extra": {"operation_id": operation_id} if operation_id else None,
            }
            for e in events
        ]
        
        count = self.db.insert_events_batch(event_dicts)
        self.logger.debug(
            "Seeded %d historical events for heat %s proc %s (cancel=%s, rework=%s)",
            count, heat_no, proc_cd, result.has_cancel, result.has_rework
        )
        
        # Trigger callback if special event occurred
        if self.on_special_event:
            if result.has_cancel and result.cancel_event_time:
                self.on_special_event(
                    operation_id=operation_id,
                    heat_no=heat_no,
                    proc_cd=proc_cd,
                    event_type=SpecialEventType.CANCEL,
                    event_time=result.cancel_event_time,
                )
            elif result.has_rework and result.rework_event_time:
                self.on_special_event(
                    operation_id=operation_id,
                    heat_no=heat_no,
                    proc_cd=proc_cd,
                    event_type=SpecialEventType.REWORK,
                    event_time=result.rework_event_time,
                )
        
        return result
    
    def seed_partial_events_for_active_operation(
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
        """Seed partial events for an active (in-progress) operation.
        
        When initializing the simulator, active operations should already have some
        events generated (start sequence + some middle events) since they have been
        running for some time. This method generates events from operation start
        up to the current time.
        
        Args:
            operation_id: Operation ID (optional)
            heat_no: Heat number
            pro_line_cd: Production line code
            proc_cd: Process code
            device_no: Device number
            window_start: Operation start time (real_start_time)
            now: Current time (events will be generated up to this time)
            
        Returns:
            Number of events inserted
        """
        if window_start is None or now is None or now <= window_start:
            return 0
        
        proc_name = self.get_process_name(proc_cd)
        if not proc_name:
            return 0
        
        config = EVENT_SEQUENCE_CONFIGS.get(proc_name)
        if not config:
            return 0
        
        # Calculate how far into the operation we are (as a fraction)
        # Assume a typical operation duration for estimation
        typical_duration_seconds = (
            (self.config.min_operation_duration + self.config.max_operation_duration) / 2
        ) * 60
        elapsed_seconds = (now - window_start).total_seconds()
        progress = min(1.0, elapsed_seconds / typical_duration_seconds)
        
        # Build event info lookup
        event_lookup = {}
        for code, name, p1, p2, p3, p4 in EVENT_CODES.get(proc_name, []):
            event_lookup[code] = (code, name, p1, p2, p3, p4)
        
        events_to_insert = []
        
        # Always generate start sequence events (these should have happened)
        start_seq = config.start_sequence
        start_duration = elapsed_seconds * 0.15  # Start events in first 15% of elapsed time
        
        for i, event_code in enumerate(start_seq):
            event_info = event_lookup.get(event_code)
            if not event_info:
                continue
            
            code, name, p1, p2, p3, p4 = event_info
            msg = EventMessageGenerator.generate_message(code, name, p1, p2, p3, p4)
            
            # Space start events evenly in the start duration
            if len(start_seq) > 1:
                event_time = window_start + timedelta(seconds=start_duration * i / (len(start_seq) - 1))
            else:
                event_time = window_start
            
            events_to_insert.append({
                "heat_no": heat_no,
                "pro_line_cd": pro_line_cd,
                "proc_cd": proc_cd,
                "device_no": device_no,
                "event_code": event_code,
                "event_name": name,
                "event_msg": msg,
                "event_time_start": event_time,
                "event_time_end": event_time,
                "extra": {"operation_id": operation_id} if operation_id else None,
            })
        
        # Generate some middle events based on progress
        # More progress = more middle events
        if progress > 0.2 and config.middle_events:
            # Calculate how many middle events to generate
            # At 100% progress, generate about half the possible middle events
            max_middle_events = len(config.middle_events)
            num_middle_events = int(max_middle_events * progress * 0.5)
            num_middle_events = max(1, min(num_middle_events, max_middle_events))
            
            # Select random middle events based on their weights
            middle_pool = []
            for event_code, weight in config.middle_events:
                if random.random() < weight:
                    middle_pool.append(event_code)
            
            # Limit to num_middle_events
            if len(middle_pool) > num_middle_events:
                middle_pool = random.sample(middle_pool, num_middle_events)
            
            # Generate middle events spaced between start and now
            middle_start_time = window_start + timedelta(seconds=start_duration)
            middle_available_time = elapsed_seconds - start_duration - 10  # Leave 10s buffer
            
            if middle_available_time > 0 and middle_pool:
                for i, event_code in enumerate(middle_pool):
                    event_info = event_lookup.get(event_code)
                    if not event_info:
                        continue
                    
                    code, name, p1, p2, p3, p4 = event_info
                    msg = EventMessageGenerator.generate_message(code, name, p1, p2, p3, p4)
                    
                    # Space events with some randomness
                    base_offset = middle_available_time * (i + 1) / (len(middle_pool) + 1)
                    jitter = random.uniform(-10, 10)
                    event_time = middle_start_time + timedelta(seconds=max(0, base_offset + jitter))
                    
                    # Ensure event is before now
                    if event_time >= now:
                        event_time = now - timedelta(seconds=random.uniform(1, 10))
                    
                    events_to_insert.append({
                        "heat_no": heat_no,
                        "pro_line_cd": pro_line_cd,
                        "proc_cd": proc_cd,
                        "device_no": device_no,
                        "event_code": event_code,
                        "event_name": name,
                        "event_msg": msg,
                        "event_time_start": event_time,
                        "event_time_end": event_time,
                        "extra": {"operation_id": operation_id} if operation_id else None,
                    })

        if events_to_insert:
            self._append_missing_paired_end_events(
                events_to_insert=events_to_insert,
                config=config,
                event_lookup=event_lookup,
                heat_no=heat_no,
                pro_line_cd=pro_line_cd,
                proc_cd=proc_cd,
                device_no=device_no,
                operation_id=operation_id,
                now=now,
            )

        if not events_to_insert:
            return 0
        
        count = self.db.insert_events_batch(events_to_insert)
        self.logger.debug(
            "Seeded %d partial events for active operation heat %s proc %s (progress=%.1f%%)",
            count, heat_no, proc_cd, progress * 100
        )
        
        return count
    
    @staticmethod
    def _operation_window(operation: Dict[str, Any]):
        """Get the time window for an operation."""
        start = operation.get("real_start_time") or operation.get("plan_start_time")
        end = operation.get("real_end_time") or operation.get("plan_end_time")
        return start, end
    
    def should_emit_event_now(self, operation: Dict[str, Any], now: datetime) -> bool:
        """Check if we should emit an event for this operation at this tick."""
        max_events = self.event_config.max_realtime_events_per_operation
        if max_events <= 0:
            return False
        
        window_start, window_end = self._operation_window(operation)
        if not window_start:
            return False
        
        # For active operations, window_end might be None
        effective_end = window_end or (now + timedelta(hours=1))
        
        existing_events = self.db.get_operation_events(
            heat_no=operation["heat_no"],
            proc_cd=operation["proc_cd"],
            device_no=operation["device_no"],
            window_start=window_start,
            window_end=effective_end,
        )
        count = len(existing_events)
        if count >= max_events:
            return False
        
        last_time = self.db.get_operation_last_event_time(
            heat_no=operation["heat_no"],
            proc_cd=operation["proc_cd"],
            device_no=operation["device_no"],
            window_start=window_start,
            window_end=effective_end,
        )
        
        # Ensure minimum spacing between events
        if last_time is not None:
            min_spacing = 30.0  # 30 seconds minimum between events
            if (now - last_time).total_seconds() < min_spacing:
                return False
        
        return random.random() < self.event_config.event_probability_per_tick
    
    def emit_realtime_event(self, operation: Dict[str, Any], now: datetime) -> Optional[int]:
        """Emit a single event for an active operation at the current time.
        
        Returns:
            Event ID if inserted, None otherwise
        """
        proc_name = self.get_process_name(operation["proc_cd"])
        if not proc_name:
            return None
        
        config = EVENT_SEQUENCE_CONFIGS.get(proc_name)
        if not config:
            return None
        
        # Get existing event count to determine what type of event to generate
        window_start, _ = self._operation_window(operation)
        if not window_start:
            return None
        
        effective_end = now + timedelta(hours=1)
        existing_events = self.db.get_operation_events(
            heat_no=operation["heat_no"],
            proc_cd=operation["proc_cd"],
            device_no=operation["device_no"],
            window_start=window_start,
            window_end=effective_end,
        )
        count = len(existing_events)
        
        # Early in operation: emit start events
        # Middle: emit middle events
        # This is simplified for real-time - full sequence tracking would be complex
        
        pending_paired_end_codes = self._pending_paired_end_codes(existing_events, config)
        if pending_paired_end_codes:
            event_code = pending_paired_end_codes[0]
        elif count < len(config.start_sequence):
            # Emit start sequence event
            event_code = config.start_sequence[count]
        else:
            # Emit a random middle event
            if config.middle_events:
                event_code, _ = random.choice(config.middle_events)
            else:
                return None
        
        # Get event info
        event_info = None
        for code, name, p1, p2, p3, p4 in EVENT_CODES.get(proc_name, []):
            if code == event_code:
                event_info = (code, name, p1, p2, p3, p4)
                break
        
        if not event_info:
            return None
        
        code, name, p1, p2, p3, p4 = event_info
        msg = EventMessageGenerator.generate_message(code, name, p1, p2, p3, p4)
        
        event_id = self.db.insert_event(
            heat_no=operation["heat_no"],
            pro_line_cd=operation.get("pro_line_cd", PRO_LINE_CD),
            proc_cd=operation["proc_cd"],
            device_no=operation["device_no"],
            event_code=event_code,
            event_name=name,
            event_msg=msg,
            event_time_start=now,
            event_time_end=now,
            extra={"operation_id": operation.get("id")},
        )
        
        self.logger.debug(
            "Emitted realtime event %s (%s) for heat %s proc %s",
            event_code, name, operation["heat_no"], operation["proc_cd"]
        )
        
        return event_id
    
    def tick_realtime_events(self, now: datetime) -> None:
        """Process real-time event generation for all active operations."""
        active_ops = self.db.get_active_operations()
        
        for op in active_ops:
            if self.should_emit_event_now(op, now):
                self.emit_realtime_event(op, now)
    
    def emit_end_sequence_events(
        self,
        operation: Dict[str, Any],
        completion_time: datetime,
    ) -> int:
        """Emit end sequence events when an operation completes.
        
        This generates the proper ending events (e.g., 炉次结束, 处理结束, 钢包离开)
        that were not emitted during real-time event generation.
        
        Args:
            operation: The operation that is completing
            completion_time: The time the operation is completing
            
        Returns:
            Number of end events inserted
        """
        proc_name = self.get_process_name(operation["proc_cd"])
        if not proc_name:
            return 0
        
        config = EVENT_SEQUENCE_CONFIGS.get(proc_name)
        if not config:
            return 0
        
        # Get existing events for this operation
        window_start = operation.get("real_start_time") or operation.get("plan_start_time")
        if not window_start:
            return 0
        
        existing_events = self.db.get_operation_events(
            heat_no=operation["heat_no"],
            proc_cd=operation["proc_cd"],
            device_no=operation["device_no"],
            window_start=window_start,
            window_end=completion_time,
        )
        existing_codes = {e["event_code"] for e in existing_events}
        
        # Determine which end sequence events are missing
        end_sequence = config.end_sequence
        missing_end_events = [code for code in end_sequence if code not in existing_codes]
        pending_paired_end_codes = self._pending_paired_end_codes(existing_events, config)
        
        if not missing_end_events and not pending_paired_end_codes:
            self.logger.debug(
                "All end events already present for heat %s proc %s",
                operation["heat_no"], operation["proc_cd"]
            )
            return 0

        events_to_insert = pending_paired_end_codes + missing_end_events
        
        # Calculate time spacing for end events
        # End events should occur in the last 10% of the operation duration
        last_event_time = max(
            (e["event_time_start"] for e in existing_events),
            default=window_start
        )
        
        # Space end events between last_event_time and completion_time
        time_available = (completion_time - last_event_time).total_seconds()
        num_events = len(events_to_insert)
        
        if time_available <= 0:
            # Not enough time, place all events at completion_time with small offsets
            time_step = 0.5  # 0.5 second between events
        else:
            time_step = time_available / (num_events + 1)
        
        # Build event info lookup
        event_lookup = {}
        for code, name, p1, p2, p3, p4 in EVENT_CODES.get(proc_name, []):
            event_lookup[code] = (code, name, p1, p2, p3, p4)
        
        # Insert end events
        events_inserted = 0
        for i, event_code in enumerate(events_to_insert):
            event_info = event_lookup.get(event_code)
            if not event_info:
                continue
            
            code, name, p1, p2, p3, p4 = event_info
            msg = EventMessageGenerator.generate_message(code, name, p1, p2, p3, p4)
            
            event_time = last_event_time + timedelta(seconds=time_step * (i + 1))
            # Ensure we don't exceed completion time
            if event_time > completion_time:
                event_time = completion_time - timedelta(seconds=0.5 * (num_events - i))
            
            self.db.insert_event(
                heat_no=operation["heat_no"],
                pro_line_cd=operation.get("pro_line_cd", PRO_LINE_CD),
                proc_cd=operation["proc_cd"],
                device_no=operation["device_no"],
                event_code=event_code,
                event_name=name,
                event_msg=msg,
                event_time_start=event_time,
                event_time_end=event_time,
                extra={"operation_id": operation.get("id")},
            )
            events_inserted += 1
        
        self.logger.debug(
            "Emitted %d end sequence events for heat %s proc %s",
            events_inserted, operation["heat_no"], operation["proc_cd"]
        )
        
        return events_inserted
