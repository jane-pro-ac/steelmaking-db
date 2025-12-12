"""Steelmaking operations simulator."""

import random
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Any

from .config import (
    SimulationConfig, DatabaseConfig,
    EQUIPMENT, PROCESS_FLOW, PRO_LINE_CD, ProcessStatus, CREW_CODES
)
from .database import DatabaseManager

logger = logging.getLogger(__name__)

# Timezone for China Standard Time (UTC+8)
CST = timezone(timedelta(hours=8))

# Warning message templates keyed by process name
WARNING_TEMPLATES = {
    "BOF": [
        {"msg": "检测到氧枪压力波动", "code": "BOF-01", "level": 2},
        {"msg": "转炉煤气温度快速上升", "code": "BOF-02", "level": 2},
        {"msg": "冷却水流量低于下限", "code": "BOF-03", "level": 1},
        {"msg": "铁水硅超标，需调整造渣剂加入量", "code": "BOF-04", "level": 3},
    ],
    "LF": [
        {"msg": "氩搅拌压力不稳定", "code": "LF-01", "level": 2},
        {"msg": "钢包温度下降超过目标", "code": "LF-02", "level": 3},
        {"msg": "合金加入机堵料", "code": "LF-03", "level": 2},
        {"msg": "电极消耗高于预期", "code": "LF-04", "level": 4},
    ],
    "CCM": [
        {"msg": "结晶器液位振荡超出范围", "code": "CCM-01", "level": 2},
        {"msg": "二冷水压力偏低", "code": "CCM-02", "level": 1},
        {"msg": "中间包温度偏移", "code": "CCM-03", "level": 3},
        {"msg": "拉速波动", "code": "CCM-04", "level": 3},
    ],
    "COMMON": [
        {"msg": "传感器信号噪声过高", "code": "W-100", "level": 4},
        {"msg": "请人工检查工艺参数", "code": "W-101", "level": 4},
        {"msg": "数据采集延迟", "code": "W-102", "level": 4},
    ],
}


class SteelmakingSimulator:
    """Simulates steelmaking operations."""

    def __init__(self, db_config: DatabaseConfig, sim_config: SimulationConfig):
        self.db = DatabaseManager(db_config)
        self.config = sim_config
        self.steel_grades: List[Dict[str, Any]] = []
        # Basic probabilities to avoid flooding warnings
        self.seed_warning_probability = 0.5
        self.active_warning_probability = 0.1

    def initialize(self):
        """Initialize the simulator by loading necessary data."""
        logger.info("Initializing simulator...")
        self.steel_grades = self.db.get_steel_grades()
        if not self.steel_grades:
            raise RuntimeError("No steel grades found in database. Please populate the base.steel_grade table first.")
        logger.info(f"Loaded {len(self.steel_grades)} steel grades")
        self._reset_demo_data()

    def generate_heat_no(self) -> int:
        """Generate a new heat number based on current date.
        
        Format: YYMMNNNNN where:
        - YY: Last two digits of year
        - MM: Two-digit month (01-12)
        - NNNNN: Sequential number within the month (5 digits)
        """
        now = datetime.now(CST)
        year = now.year % 100
        month = now.month
        
        # Get the latest heat_no for the current month to determine next sequence
        latest = self.db.get_latest_heat_no_for_month(year, month)
        seq = (latest % 100000) + 1 if latest else 1
        
        return int(f"{year:02d}{month:02d}{seq:05d}")

    def get_random_steel_grade(self) -> Dict[str, Any]:
        """Get a random steel grade."""
        return random.choice(self.steel_grades)

    def get_random_duration(self) -> timedelta:
        """Get a random operation duration."""
        minutes = random.randint(
            self.config.min_operation_duration,
            self.config.max_operation_duration
        )
        return timedelta(minutes=minutes)

    def get_random_crew(self) -> str:
        """Pick a random crew code for a heat."""
        return random.choice(CREW_CODES)

    def get_random_gap(self) -> timedelta:
        """Get a random gap between operations."""
        minutes = random.randint(
            self.config.min_gap_duration,
            self.config.max_gap_duration
        )
        return timedelta(minutes=minutes)

    def _random_warning_level(self) -> int:
        """Pick a warning level (1-4) with mild bias toward lower severity."""
        return random.choices([1, 2, 3, 4], weights=[0.1, 0.2, 0.35, 0.35], k=1)[0]

    def _get_warning_templates(self, proc_cd: str) -> List[Dict[str, Any]]:
        """Get warning templates for a process code, plus common fallbacks."""
        proc_name = self._get_process_name(proc_cd)
        templates = WARNING_TEMPLATES.get(proc_name, [])
        return templates + WARNING_TEMPLATES["COMMON"]

    def _build_warning_payload(self, proc_cd: str) -> Dict[str, Any]:
        """Pick a warning template and derive code/level/message."""
        templates = self._get_warning_templates(proc_cd)
        template = random.choice(templates) if templates else {"msg": "Process warning", "level": 4}
        warning_level = template.get("level") or self._random_warning_level()
        warning_code = template.get("code")
        # Drop the code occasionally to exercise optionality
        if warning_code and random.random() < 0.3:
            warning_code = None
        return {
            "warning_code": warning_code,
            "warning_msg": template["msg"],
            "warning_level": warning_level,
        }

    def _random_warning_window(self, start: datetime, end: datetime) -> Optional[Dict[str, datetime]]:
        """Generate a random warning time window within [start, end]."""
        if start is None or end is None or end <= start:
            return None

        start_ts = start.timestamp()
        end_ts = end.timestamp()
        warn_start_ts = random.uniform(start_ts, end_ts)
        warn_end_ts = random.uniform(warn_start_ts, end_ts)

        warn_start = datetime.fromtimestamp(warn_start_ts, tz=start.tzinfo)
        warn_end = datetime.fromtimestamp(warn_end_ts, tz=start.tzinfo)

        if warn_end <= warn_start:
            warn_end = warn_start + timedelta(seconds=30)
            if warn_end > end:
                warn_end = end
                if warn_end <= warn_start:
                    return None

        return {
            "warning_time_start": warn_start,
            "warning_time_end": warn_end,
        }

    def _create_warnings_for_operation(
        self,
        operation: Dict[str, Any],
        window_start: datetime,
        window_end: datetime,
        probability: float
    ):
        """Maybe create 1-5 warnings for an operation within the given window."""
        if window_start is None or window_end is None or window_end <= window_start or probability <= 0:
            return

        if random.random() >= probability:
            return

        warning_count = random.randint(1, 5)
        for _ in range(warning_count):
            window = self._random_warning_window(window_start, window_end)
            if not window:
                continue
            payload = self._build_warning_payload(operation["proc_cd"])
            self.db.insert_warning(
                operation_id=operation["id"],
                heat_no=operation["heat_no"],
                pro_line_cd=operation["pro_line_cd"],
                proc_cd=operation["proc_cd"],
                device_no=operation["device_no"],
                crew_cd=operation["crew_cd"],
                warning_code=payload["warning_code"],
                warning_msg=payload["warning_msg"],
                warning_level=payload["warning_level"],
                warning_time_start=window["warning_time_start"],
                warning_time_end=window["warning_time_end"],
                extra=None,
            )

    def _reset_demo_data(self):
        """Reset table and seed past completed flows and future plans for demo."""
        logger.info("Resetting demo data: clearing table and seeding past/future operations")
        self.db.clear_operations()
        now = datetime.now(CST)
        self._seed_completed_history(now)
        self._seed_future_plans(now)

    def _seed_completed_history(self, now: datetime):
        """Seed completed flows within the last 12 hours."""
        start_time = now - timedelta(hours=12)
        for _ in range(self.config.seed_past_heats):
            heat_no = self.generate_heat_no()
            steel_grade = self.get_random_steel_grade()
            crew_cd = self.get_random_crew()
            start_time = self._seed_single_flow(
                heat_no=heat_no,
                steel_grade=steel_grade,
                crew_cd=crew_cd,
                start_time=start_time,
                mark_completed=True
            )
            # Small gap between heats to avoid overlapping devices
            start_time += self.get_random_gap()

    def _seed_future_plans(self, now: datetime):
        """Seed planned (pending) flows within the next 12 hours."""
        start_time = now + timedelta(minutes=5)
        end_window = now + timedelta(hours=12)
        for _ in range(self.config.seed_future_heats):
            if start_time >= end_window:
                break
            heat_no = self.generate_heat_no()
            steel_grade = self.get_random_steel_grade()
            crew_cd = self.get_random_crew()
            start_time = self._seed_single_flow(
                heat_no=heat_no,
                steel_grade=steel_grade,
                crew_cd=crew_cd,
                start_time=start_time,
                mark_completed=False
            )
            start_time += self.get_random_gap()

    def _seed_single_flow(
        self,
        heat_no: int,
        steel_grade: Dict[str, Any],
        crew_cd: str,
        start_time: datetime,
        mark_completed: bool,
    ) -> datetime:
        """Create one BOF->LF->CCM flow, completed or planned."""
        current_plan_start = start_time
        last_end = start_time

        for process_name in PROCESS_FLOW:
            proc_info = EQUIPMENT[process_name]
            proc_cd = proc_info["proc_cd"]
            device_no = random.choice(proc_info["devices"])

            duration = self.get_random_duration()
            plan_start = current_plan_start
            plan_end = plan_start + duration

            if mark_completed:
                # Keep real duration within limits; slight variation from plan
                start_jitter = timedelta(minutes=random.uniform(0, 1))
                real_start = plan_start + start_jitter
                real_duration_minutes = min(
                    self.config.max_operation_duration,
                    max(
                        self.config.min_operation_duration,
                        duration.total_seconds() / 60 + random.uniform(-1, 2)
                    ),
                )
                real_end = real_start + timedelta(minutes=real_duration_minutes)
                proc_status = ProcessStatus.COMPLETED
            else:
                real_start = None
                real_end = None
                proc_status = ProcessStatus.PENDING

            operation_id = self.db.insert_operation(
                heat_no=heat_no,
                pro_line_cd=PRO_LINE_CD,
                proc_cd=proc_cd,
                device_no=device_no,
                crew_cd=crew_cd,
                stl_grd_id=steel_grade['id'],
                stl_grd_cd=steel_grade['code'],
                proc_status=proc_status,
                plan_start_time=plan_start,
                plan_end_time=plan_end,
                real_start_time=real_start,
                real_end_time=real_end
            )

            if mark_completed:
                operation = {
                    "id": operation_id,
                    "heat_no": heat_no,
                    "pro_line_cd": PRO_LINE_CD,
                    "proc_cd": proc_cd,
                    "device_no": device_no,
                    "crew_cd": crew_cd,
                }
                self._create_warnings_for_operation(
                    operation,
                    window_start=real_start,
                    window_end=real_end,
                    probability=self.seed_warning_probability,
                )

            last_end = real_end if mark_completed else plan_end
            current_plan_start = plan_end + self.get_random_gap()

        return last_end

    def create_new_heat(self) -> Optional[int]:
        """Create a new heat with all operations (BOF -> LF -> CCM)."""
        # Check if there's an available BOF device
        bof_device = self.db.get_available_device(
            EQUIPMENT["BOF"]["proc_cd"],
            EQUIPMENT["BOF"]["devices"]
        )
        
        if not bof_device:
            logger.debug("No available BOF device, skipping new heat creation")
            return None
        
        heat_no = self.generate_heat_no()
        steel_grade = self.get_random_steel_grade()
        crew_cd = self.get_random_crew()
        now = datetime.now(CST)
        
        logger.info(f"Creating new heat {heat_no} with steel grade {steel_grade['code']}")
        
        # Plan start time for BOF (current time)
        current_plan_start = now
        
        # Create operations for each process stage
        for i, process_name in enumerate(PROCESS_FLOW):
            proc_info = EQUIPMENT[process_name]
            proc_cd = proc_info["proc_cd"]
            
            # Select a device (for BOF use the available one, for others randomly select)
            if process_name == "BOF":
                device_no = bof_device
            else:
                device_no = random.choice(proc_info["devices"])
            
            # Calculate plan times
            duration = self.get_random_duration()
            plan_start = current_plan_start
            plan_end = plan_start + duration
            
            # Determine initial status and real times
            if i == 0:
                # BOF starts as active immediately
                proc_status = ProcessStatus.ACTIVE
                real_start_time = now
                real_end_time = None
            else:
                # LF and CCM start as pending
                proc_status = ProcessStatus.PENDING
                real_start_time = None
                real_end_time = None
            
            # Insert the operation
            self.db.insert_operation(
                heat_no=heat_no,
                pro_line_cd=PRO_LINE_CD,
                proc_cd=proc_cd,
                device_no=device_no,
                crew_cd=crew_cd,
                stl_grd_id=steel_grade['id'],
                stl_grd_cd=steel_grade['code'],
                proc_status=proc_status,
                plan_start_time=plan_start,
                plan_end_time=plan_end,
                real_start_time=real_start_time,
                real_end_time=real_end_time
            )
            
            logger.info(f"  Created {process_name} operation on {device_no}, status: {proc_status}")
            
            # Calculate next operation's plan start time
            gap = self.get_random_gap()
            current_plan_start = plan_end + gap
        
        return heat_no

    def process_active_operations(self):
        """Process active operations and check if they should complete."""
        active_ops = self.db.get_active_operations()
        now = datetime.now(CST)
        
        for op in active_ops:
            # Occasionally generate warnings during active operations
            if op['real_start_time']:
                self._create_warnings_for_operation(
                    op,
                    window_start=op['real_start_time'],
                    window_end=now,
                    probability=self.active_warning_probability
                )

            # Check if operation has been running long enough
            if op['real_start_time']:
                elapsed = now - op['real_start_time']
                min_duration = timedelta(minutes=self.config.min_operation_duration)
                
                # Operation should complete after minimum duration with some probability
                if elapsed >= min_duration:
                    # Calculate completion probability based on elapsed time
                    max_duration = timedelta(minutes=self.config.max_operation_duration)
                    if elapsed >= max_duration:
                        # Must complete if max duration reached
                        should_complete = True
                    else:
                        # Probability increases as time passes
                        progress = (elapsed - min_duration) / (max_duration - min_duration)
                        should_complete = random.random() < (0.3 + 0.7 * progress)
                    
                    if should_complete:
                        self._complete_operation(op, now)

    def _complete_operation(self, operation: Dict[str, Any], completion_time: datetime):
        """Complete an operation and potentially start the next one."""
        logger.info(f"Completing operation {operation['id']} for heat {operation['heat_no']} ({operation['proc_cd']})")
        
        # Update operation to completed
        self.db.update_operation_status(
            operation_id=operation['id'],
            proc_status=ProcessStatus.COMPLETED,
            real_end_time=completion_time
        )
        
        # Find the next pending operation for this heat
        heat_ops = self.db.get_heat_operations(operation['heat_no'])
        next_op = None
        
        for op in heat_ops:
            if op['proc_status'] == ProcessStatus.PENDING:
                next_op = op
                break
        
        if next_op:
            proc_name = self._get_process_name(next_op['proc_cd'])
            if proc_name:
                # Push the planned start/end to honor the required gap after real completion
                planned_duration = next_op['plan_end_time'] - next_op['plan_start_time']
                gap = self.get_random_gap()
                earliest_start = completion_time + gap
                new_plan_start = max(next_op['plan_start_time'], earliest_start)
                new_plan_end = new_plan_start + planned_duration
                self.db.update_operation_plan_times(next_op['id'], new_plan_start, new_plan_end)

                # Start immediately only if the scheduled time has arrived and a device is free
                now = datetime.now(CST)
                if now >= new_plan_start:
                    device_to_use = next_op['device_no'] if self._is_device_available(next_op['device_no']) else None
                    if not device_to_use:
                        device_to_use = self.db.get_available_device(
                            next_op['proc_cd'],
                            EQUIPMENT[proc_name]["devices"]
                        )

                    if device_to_use:
                        logger.info(f"Starting next operation {next_op['id']} ({next_op['proc_cd']}) on {device_to_use}")
                        self.db.update_operation_status(
                            operation_id=next_op['id'],
                            proc_status=ProcessStatus.ACTIVE,
                            real_start_time=now,
                            device_no=device_to_use
                        )
                    else:
                        logger.debug("No available device for next operation, will retry later")

    def _is_device_available(self, device_no: str) -> bool:
        """Check if a specific device is available."""
        current_op = self.db.get_device_current_operation(device_no)
        return current_op is None or current_op['proc_status'] != ProcessStatus.ACTIVE

    def _get_process_name(self, proc_cd: str) -> Optional[str]:
        """Get the process name from process code."""
        for name, info in EQUIPMENT.items():
            if info["proc_cd"] == proc_cd:
                return name
        return None

    def process_pending_operations(self):
        """Check pending operations and start them if previous step is complete."""
        pending_ops = self.db.get_pending_operations()
        now = datetime.now(CST)
        
        for op in pending_ops:
            # Get all operations for this heat
            heat_ops = self.db.get_heat_operations(op['heat_no'])
            
            # Find the previous operation in the flow
            current_proc_idx = None
            for i, proc_name in enumerate(PROCESS_FLOW):
                if EQUIPMENT[proc_name]["proc_cd"] == op['proc_cd']:
                    current_proc_idx = i
                    break
            
            if current_proc_idx is None or current_proc_idx == 0:
                continue
            
            # Get previous process info
            prev_proc_name = PROCESS_FLOW[current_proc_idx - 1]
            prev_proc_cd = EQUIPMENT[prev_proc_name]["proc_cd"]
            
            # Find the previous operation
            prev_op = None
            for heat_op in heat_ops:
                if heat_op['proc_cd'] == prev_proc_cd:
                    prev_op = heat_op
                    break
            
            if prev_op and prev_op['proc_status'] == ProcessStatus.COMPLETED and prev_op['real_end_time']:
                # Previous operation is complete; ensure the required gap has elapsed
                proc_name = PROCESS_FLOW[current_proc_idx]
                min_ready_time = prev_op['real_end_time'] + timedelta(minutes=self.config.min_gap_duration)
                scheduled_start = max(op['plan_start_time'], min_ready_time)

                if now < scheduled_start:
                    # Push plan times forward so later checks use the updated schedule
                    duration = op['plan_end_time'] - op['plan_start_time']
                    if scheduled_start > op['plan_start_time']:
                        self.db.update_operation_plan_times(
                            operation_id=op['id'],
                            plan_start_time=scheduled_start,
                            plan_end_time=scheduled_start + duration
                        )
                    continue

                device_no = op['device_no'] if self._is_device_available(op['device_no']) else None
                if not device_no:
                    device_no = self.db.get_available_device(
                        op['proc_cd'],
                        EQUIPMENT[proc_name]["devices"]
                    )
                if not device_no:
                    logger.debug(f"No available device for pending operation {op['id']}, will retry")
                    continue

                logger.info(f"Starting pending operation {op['id']} for heat {op['heat_no']} ({op['proc_cd']}) on {device_no}")
                self.db.update_operation_status(
                    operation_id=op['id'],
                    proc_status=ProcessStatus.ACTIVE,
                    real_start_time=now,
                    device_no=device_no
                )

    def tick(self):
        """Perform one simulation tick."""
        logger.debug("Simulation tick...")
        
        # Process active operations (potentially complete them)
        self.process_active_operations()
        
        # Process pending operations (potentially start them)
        self.process_pending_operations()
        
        # Maybe create a new heat
        if random.random() < self.config.new_heat_probability:
            self.create_new_heat()

    def run(self):
        """Run the simulation loop."""
        import time
        
        self.initialize()
        logger.info(f"Starting simulation with {self.config.interval}s interval")
        
        try:
            while True:
                self.tick()
                time.sleep(self.config.interval)
        except KeyboardInterrupt:
            logger.info("Simulation stopped by user")
        finally:
            self.db.close()
