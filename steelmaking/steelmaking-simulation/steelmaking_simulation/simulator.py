"""Steelmaking operations simulator.

This module is the orchestration layer. Most business logic lives in:
- warning_engine.py (warnings)
- event_engine.py (events)
- seeding.py (initialization seeding)
- heat_planner.py (new heat creation)
- operation_processor.py (runtime progression)
"""

from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .config import (
    CREW_CODES,
    DatabaseConfig,
    EQUIPMENT,
    PROCESS_FLOW,
    PRO_LINE_CD,
    ProcessStatus,
    SimulationConfig,
)
from .database import DatabaseManager
from .event_engine import EventEngine
from .heat_planner import HeatPlanContext, HeatPlanner
from .operation_processor import OperationProcessor, OperationProcessorContext
from .scheduler import DeviceScheduler
from .seeding import OperationSeeder, SeedContext
from .time_utils import CST
from .warning_engine import WarningEngine

logger = logging.getLogger(__name__)


class SteelmakingSimulator:
    """Simulates steelmaking operations."""

    def __init__(self, db_config: DatabaseConfig, sim_config: SimulationConfig, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager(db_config)
        self.config = sim_config
        self.scheduler = DeviceScheduler(self.db, self.config)
        self.steel_grades: List[Dict[str, Any]] = []

        self.warnings = WarningEngine(db=self.db, config=self.config, get_process_name=self._get_process_name, logger=logger)
        self.events = EventEngine(db=self.db, config=self.config, get_process_name=self._get_process_name, logger=logger)
        self.seeder = OperationSeeder(
            SeedContext(
                db=self.db,
                config=self.config,
                warnings=self.warnings,
                events=self.events,
                generate_heat_no=self.generate_heat_no,
                get_random_steel_grade=self.get_random_steel_grade,
                get_random_crew=self.get_random_crew,
                get_random_duration=self.get_random_duration,
                logger=logger,
            )
        )
        self.planner = HeatPlanner(
            HeatPlanContext(
                db=self.db,
                config=self.config,
                scheduler=self.scheduler,
                generate_heat_no=self.generate_heat_no,
                get_random_steel_grade=self.get_random_steel_grade,
                get_random_crew=self.get_random_crew,
                get_random_duration=self.get_random_duration,
                get_random_transfer_gap=self.get_random_transfer_gap,
                aligned_device=self._aligned_device,
                logger=logger,
            )
        )
        self.processor = OperationProcessor(
            OperationProcessorContext(
                db=self.db,
                config=self.config,
                scheduler=self.scheduler,
                get_process_name=self._get_process_name,
                is_device_available=self._is_device_available,
                get_random_transfer_gap=self.get_random_transfer_gap,
                aligned_device=self._aligned_device,
                logger=logger,
                events=self.events,
            )
        )

    def initialize(self) -> None:
        logger.info("Initializing simulator...")
        self.steel_grades = self.db.get_steel_grades()
        if not self.steel_grades:
            raise RuntimeError("No steel grades found in database. Please populate the base.steel_grade table first.")
        logger.info("Loaded %s steel grades", len(self.steel_grades))

        now = datetime.now(CST)
        self.seeder.reset_demo_data(now)

        if not self.db.get_active_operations():
            # Fallback: ensure at least one active flow exists for demo readability.
            self._seed_forced_active_heat(now, start_time=now - timedelta(minutes=self.config.max_operation_duration))

    def generate_heat_no(self) -> int:
        now = datetime.now(CST)
        year = now.year % 100
        month = now.month
        latest = self.db.get_latest_heat_no_for_month(year, month)
        seq = (latest % 100000) + 1 if latest else 1
        return int(f"{year:02d}{month:02d}{seq:05d}")

    def get_random_steel_grade(self) -> Dict[str, Any]:
        return random.choice(self.steel_grades)

    def get_random_duration(self) -> timedelta:
        minutes = random.randint(self.config.min_operation_duration, self.config.max_operation_duration)
        return timedelta(minutes=minutes)

    def get_random_crew(self) -> str:
        return random.choice(CREW_CODES)

    def get_random_transfer_gap(self) -> timedelta:
        minutes = random.randint(self.config.min_transfer_gap_minutes, self.config.max_transfer_gap_minutes)
        return timedelta(minutes=minutes)

    def create_new_heat(self) -> Optional[int]:
        return self.planner.create_new_heat()

    def process_active_operations(self) -> None:
        self.processor.process_active_operations()

    def process_pending_operations(self) -> None:
        self.processor.process_pending_operations()

    def tick(self) -> None:
        logger.debug("Simulation tick...")
        now = datetime.now(CST)
        self._tick_realtime_warnings(now)
        self._tick_realtime_events(now)

        self.process_active_operations()
        self.process_pending_operations()

        if random.random() < self.config.new_heat_probability:
            self.create_new_heat()

    def run(self) -> None:
        import time

        self.initialize()
        logger.info("Starting simulation with %ss interval", self.config.interval)
        try:
            while True:
                self.tick()
                time.sleep(self.config.interval)
        except KeyboardInterrupt:
            logger.info("Simulation stopped by user")
        finally:
            self.db.close()

    # --- Compatibility wrappers for tests / legacy callers ---

    def _random_warning_duration_seconds(self) -> float:
        return self.warnings.random_warning_duration_seconds()

    def _tick_realtime_warnings(self, now: datetime) -> None:
        self.warnings.tick_realtime_warnings(now)

    def _tick_realtime_events(self, now: datetime) -> None:
        self.events.tick_realtime_events(now)

    # --- Internal helpers ---

    def _get_process_name(self, proc_cd: str) -> Optional[str]:
        for name, info in EQUIPMENT.items():
            if info["proc_cd"] == proc_cd:
                return name
        return None

    def _aligned_device(self, src_device_no: str, target_process_name: str) -> Optional[str]:
        if not src_device_no:
            return None
        suffix = src_device_no[-1]
        for dev in EQUIPMENT[target_process_name]["devices"]:
            if dev.endswith(suffix):
                return dev
        return None

    def _is_device_available(self, device_no: str) -> bool:
        current_op = self.db.get_device_current_operation(device_no)
        return current_op is None or current_op["proc_status"] != ProcessStatus.ACTIVE

    def _seed_forced_active_heat(self, now: datetime, start_time: datetime) -> None:
        """Fallback active flow creation when seeded timeline misses 'now'."""
        duration = self.get_random_duration()
        attempt_start = min(start_time, now - (duration / 2))

        slot = None
        for _ in range(10):
            candidate = self.scheduler.find_slot(
                process_name="BOF",
                desired_start=attempt_start,
                latest_start=None,
                duration=duration,
                devices=EQUIPMENT["BOF"]["devices"],
            )
            if candidate and candidate.plan_start <= now < candidate.plan_end:
                slot = candidate
                break
            attempt_start -= timedelta(minutes=self.config.min_rest_duration_minutes)

        if not slot:
            return

        heat_no = self.generate_heat_no()
        steel_grade = self.get_random_steel_grade()
        crew_cd = self.get_random_crew()

        planned_ops = [
            {
                "proc_cd": EQUIPMENT["BOF"]["proc_cd"],
                "plan_start": slot.plan_start,
                "plan_end": slot.plan_end,
                "real_start": slot.plan_start,
                "real_end": None,
                "status": ProcessStatus.ACTIVE,
                "device_no": slot.device_no,
            }
        ]

        current_plan_start = slot.plan_end + self.get_random_transfer_gap()
        for process_name in PROCESS_FLOW[1:]:
            proc_info = EQUIPMENT[process_name]
            proc_duration = self.get_random_duration()
            latest_start = slot.plan_end + timedelta(minutes=self.config.max_transfer_gap_minutes)
            proc_slot = self.scheduler.find_slot(
                process_name=process_name,
                desired_start=current_plan_start,
                latest_start=latest_start,
                duration=proc_duration,
                devices=proc_info["devices"],
            )
            if not proc_slot:
                break
            planned_ops.append(
                {
                    "proc_cd": proc_info["proc_cd"],
                    "plan_start": proc_slot.plan_start,
                    "plan_end": proc_slot.plan_end,
                    "real_start": None,
                    "real_end": None,
                    "status": ProcessStatus.PENDING,
                    "device_no": proc_slot.device_no,
                }
            )
            current_plan_start = proc_slot.plan_end + self.get_random_transfer_gap()

        for op in planned_ops:
            self.db.insert_operation(
                heat_no=heat_no,
                pro_line_cd=PRO_LINE_CD,
                proc_cd=op["proc_cd"],
                device_no=op["device_no"],
                crew_cd=crew_cd,
                stl_grd_id=steel_grade["id"],
                stl_grd_cd=steel_grade["stl_grd_cd"],
                proc_status=op["status"],
                plan_start_time=op["plan_start"],
                plan_end_time=op["plan_end"],
                real_start_time=op["real_start"],
                real_end_time=op["real_end"],
            )
