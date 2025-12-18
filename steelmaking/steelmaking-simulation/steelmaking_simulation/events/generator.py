"""Event generator for steelmaking operations.

This module generates realistic event sequences for each steelmaking process (BOF, LF, RH, CCM)
following the constraints defined in steelmaking/event_code_constraints.md.

Event sequences are generated to:
1. Start with the appropriate starting events (钢包到达, 处理开始, 炉次开始)
2. Include realistic middle events (加料, 测温, 取样, etc.) in valid sequences
3. End with the appropriate ending events (炉次结束, 处理结束, 钢包离开)

Special Events (取消/回炉):
- 取消 (cancel): Stops current operation and marks all subsequent operations as canceled
- 回炉 (rework): Operation continues normally to completion but signals need for rework

Support by process:
- BOF: G12007 炉次取消 only
- LF: G13007 炉次回炉, G13008 炉次取消
- RH: G15007 炉次回炉, G15008 炉次取消
- CCM: G16015 炉次开浇取消 only
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple

from .codes import EVENT_CODES, PROC_CD_TO_NAME
from .sequences import EVENT_SEQUENCE_CONFIGS
from .messages import EventMessageGenerator


class SpecialEventType(Enum):
    """Types of special events that affect operation flow."""
    NONE = auto()      # Normal event
    CANCEL = auto()    # 取消 - cancels current and subsequent operations
    REWORK = auto()    # 回炉 - operation continues but flags for rework


@dataclass
class Event:
    """Represents a single steelmaking event."""
    heat_no: int
    pro_line_cd: str
    proc_cd: str
    device_no: str
    event_code: str
    event_name: str
    event_msg: str
    event_time_start: datetime
    event_time_end: datetime
    extra: Optional[Dict[str, Any]] = None
    special_event_type: SpecialEventType = SpecialEventType.NONE


@dataclass
class EventSequenceResult:
    """Result of generating an event sequence, including special event info."""
    events: List[Event]
    has_cancel: bool = False
    has_rework: bool = False
    cancel_event_time: Optional[datetime] = None
    rework_event_time: Optional[datetime] = None
    
    @classmethod
    def from_events(cls, events: List[Event]) -> "EventSequenceResult":
        """Create result from a list of events, detecting special events."""
        has_cancel = False
        has_rework = False
        cancel_time = None
        rework_time = None
        
        for e in events:
            if e.special_event_type == SpecialEventType.CANCEL:
                has_cancel = True
                cancel_time = e.event_time_start
            elif e.special_event_type == SpecialEventType.REWORK:
                has_rework = True
                rework_time = e.event_time_start
        
        return cls(
            events=events,
            has_cancel=has_cancel,
            has_rework=has_rework,
            cancel_event_time=cancel_time,
            rework_event_time=rework_time,
        )


class EventGenerator:
    """Generates realistic event sequences for steelmaking operations."""
    
    def __init__(
        self,
        min_events_per_operation: int = 8,
        max_events_per_operation: int = 20,
        cancel_probability: float = 0.0,
        rework_probability: float = 0.0,
    ):
        self.min_events = min_events_per_operation
        self.max_events = max_events_per_operation
        self.cancel_probability = cancel_probability
        self.rework_probability = rework_probability
        
        # Build lookup for event codes
        self._event_lookup: Dict[str, Dict[str, Tuple[str, str, str, str, str, str]]] = {}
        for process, events in EVENT_CODES.items():
            self._event_lookup[process] = {code: (code, name, p1, p2, p3, p4) 
                                          for code, name, p1, p2, p3, p4 in events}
    
    def get_process_name(self, proc_cd: str) -> Optional[str]:
        """Convert process code to process name."""
        return PROC_CD_TO_NAME.get(proc_cd)
    
    def generate_event_sequence(
        self,
        heat_no: int,
        pro_line_cd: str,
        proc_cd: str,
        device_no: str,
        start_time: datetime,
        end_time: datetime,
        force_cancel: bool = False,
        force_rework: bool = False,
    ) -> List[Event]:
        """Generate a valid event sequence for an operation.
        
        Args:
            heat_no: Heat number
            pro_line_cd: Production line code
            proc_cd: Process code (G12, G13, G15, G16)
            device_no: Device number
            start_time: Operation start time
            end_time: Operation end time
            force_cancel: If True, force a cancel event (if available for this process)
            force_rework: If True, force a rework event (if available for this process)
            
        Returns:
            List of Event objects in chronological order
        """
        process_name = self.get_process_name(proc_cd)
        if not process_name:
            return []
        
        config = EVENT_SEQUENCE_CONFIGS.get(process_name)
        if not config:
            return []
        
        # Determine if we should trigger special events
        should_cancel = force_cancel or (
            config.cancel_event and random.random() < self.cancel_probability
        )
        should_rework = not should_cancel and (
            force_rework or (config.rework_event and random.random() < self.rework_probability)
        )
        
        # Generate event codes sequence with special event consideration
        event_codes, special_event_index, special_event_type = self._generate_event_code_sequence_with_special(
            process_name, config, should_cancel, should_rework
        )
        
        # Calculate event times
        total_duration = (end_time - start_time).total_seconds()
        if total_duration <= 0 or len(event_codes) == 0:
            return []
        
        # Distribute events across the operation duration
        events: List[Event] = []
        num_events = len(event_codes)
        
        # Reserve time for start and end sequences
        start_seq_len = len(config.start_sequence)
        # End sequence length depends on whether we're canceling
        if should_cancel and config.cancel_end_sequence:
            # +1 for the cancel event itself
            end_seq_len = len(config.cancel_end_sequence)
        else:
            end_seq_len = len(config.end_sequence)
        
        middle_len = max(0, num_events - start_seq_len - end_seq_len - (1 if special_event_index is not None else 0))
        
        # Allocate 10% of time for start sequence, 10% for end sequence, 80% for middle
        start_duration = total_duration * 0.10
        end_duration = total_duration * 0.10
        middle_duration = total_duration * 0.80
        
        for i, event_code in enumerate(event_codes):
            # Calculate event time
            if i < start_seq_len:
                # Start sequence events
                segment_progress = i / max(start_seq_len, 1)
                event_time = start_time + timedelta(seconds=start_duration * segment_progress)
            elif i >= num_events - end_seq_len:
                # End sequence events
                end_idx = i - (num_events - end_seq_len)
                segment_progress = end_idx / max(end_seq_len, 1)
                event_time = start_time + timedelta(seconds=start_duration + middle_duration + end_duration * segment_progress)
            else:
                # Middle events - randomize within the middle duration
                middle_idx = i - start_seq_len
                base_progress = middle_idx / max(middle_len, 1)
                jitter = random.uniform(-0.05, 0.05)
                segment_progress = max(0, min(1, base_progress + jitter))
                event_time = start_time + timedelta(seconds=start_duration + middle_duration * segment_progress)
            
            # Ensure events are strictly after the previous event
            if events and event_time <= events[-1].event_time_start:
                event_time = events[-1].event_time_start + timedelta(seconds=random.uniform(1, 10))
            
            # Ensure we don't exceed end_time
            if event_time >= end_time:
                event_time = end_time - timedelta(seconds=(num_events - i) * 2)
            
            # Get event details
            event_info = self._event_lookup[process_name].get(event_code)
            if not event_info:
                continue
            
            code, name, p1, p2, p3, p4 = event_info
            msg = EventMessageGenerator.generate_message(code, name, p1, p2, p3, p4)
            
            # Determine if this is a special event
            event_special_type = SpecialEventType.NONE
            if i == special_event_index:
                event_special_type = special_event_type
            
            event = Event(
                heat_no=heat_no,
                pro_line_cd=pro_line_cd,
                proc_cd=proc_cd,
                device_no=device_no,
                event_code=event_code,
                event_name=name,
                event_msg=msg,
                event_time_start=event_time,
                event_time_end=event_time,  # Same as start for now
                special_event_type=event_special_type,
            )
            events.append(event)
        
        # Sort events by time to ensure proper order
        events.sort(key=lambda e: e.event_time_start)
        
        return events
    
    def _generate_event_code_sequence_with_special(
        self,
        process_name: str,
        config,
        should_cancel: bool,
        should_rework: bool,
    ) -> Tuple[List[str], Optional[int], SpecialEventType]:
        """Generate event codes with potential special events.
        
        Returns:
            Tuple of (event_codes, special_event_index, special_event_type)
        """
        sequence: List[str] = []
        special_event_index: Optional[int] = None
        special_event_type = SpecialEventType.NONE
        
        # Add start sequence
        sequence.extend(config.start_sequence)
        
        # Generate middle events
        num_middle = random.randint(
            max(0, self.min_events - len(config.start_sequence) - len(config.end_sequence)),
            max(0, self.max_events - len(config.start_sequence) - len(config.end_sequence))
        )
        
        # If canceling, reduce middle events and insert cancel event
        if should_cancel and config.cancel_event:
            # Cancel happens somewhere in the middle, typically after some events
            num_middle = max(1, num_middle // 2)
        
        pending_pairs: List[str] = []
        pending_followups: List[str] = []
        pair_start_to_end = dict(config.paired_events)
        
        middle_generated = 0
        attempts = 0
        max_attempts = num_middle * 3
        
        while middle_generated < num_middle and attempts < max_attempts:
            attempts += 1
            
            if pending_followups and random.random() < 0.7:
                followup = pending_followups.pop(0)
                sequence.append(followup)
                if followup in config.follow_up_events:
                    pending_followups.append(config.follow_up_events[followup])
                middle_generated += 1
                continue
            
            event, weight = random.choice(config.middle_events)
            
            if random.random() > weight:
                continue
            
            if event in pair_start_to_end:
                if len(pending_pairs) >= 2:
                    continue
                sequence.append(event)
                pending_pairs.append(pair_start_to_end[event])
                middle_generated += 1
            else:
                sequence.append(event)
                middle_generated += 1
            
            if event in config.follow_up_events:
                pending_followups.append(config.follow_up_events[event])
            
            if pending_pairs and random.random() < 0.4:
                end_event = pending_pairs.pop(0)
                sequence.append(end_event)
                middle_generated += 1
        
        # Close remaining pairs before special events
        sequence.extend(pending_pairs)
        sequence.extend(pending_followups)
        
        # Insert special event if needed
        if should_cancel and config.cancel_event:
            special_event_index = len(sequence)
            special_event_type = SpecialEventType.CANCEL
            sequence.append(config.cancel_event)
            # Use shortened end sequence for cancel
            sequence.extend(config.cancel_end_sequence or [])
        elif should_rework and config.rework_event:
            special_event_index = len(sequence)
            special_event_type = SpecialEventType.REWORK
            sequence.append(config.rework_event)
            # Rework continues to normal end sequence
            sequence.extend(config.end_sequence)
        else:
            # Normal end sequence
            sequence.extend(config.end_sequence)
        
        return sequence, special_event_index, special_event_type
    
    def generate_events_for_operation(
        self,
        operation: Dict[str, Any],
        force_cancel: bool = False,
        force_rework: bool = False,
    ) -> List[Event]:
        """Generate events for an operation dictionary.
        
        Args:
            operation: Dictionary with operation data including:
                - heat_no, pro_line_cd, proc_cd, device_no
                - real_start_time (or plan_start_time), real_end_time (or plan_end_time)
            force_cancel: If True, force a cancel event
            force_rework: If True, force a rework event
                
        Returns:
            List of Event objects
        """
        start_time = operation.get("real_start_time") or operation.get("plan_start_time")
        end_time = operation.get("real_end_time") or operation.get("plan_end_time")
        
        if not start_time or not end_time:
            return []
        
        return self.generate_event_sequence(
            heat_no=operation["heat_no"],
            pro_line_cd=operation["pro_line_cd"],
            proc_cd=operation["proc_cd"],
            device_no=operation["device_no"],
            start_time=start_time,
            end_time=end_time,
            force_cancel=force_cancel,
            force_rework=force_rework,
        )
