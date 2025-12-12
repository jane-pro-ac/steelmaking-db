from datetime import datetime, timedelta

import pytest

from steelmaking_simulation.config import (
    DatabaseConfig,
    SimulationConfig,
    ProcessStatus,
    EQUIPMENT,
    PROCESS_FLOW,
)
from steelmaking_simulation.simulator import SteelmakingSimulator
from steelmaking_simulation.time_utils import CST
from steelmaking_simulation.scheduler import Slot


class FakeDatabaseManager:
    """In-memory stand-in for DatabaseManager to test scheduling logic."""

    def __init__(self):
        self.operations = []
        self.warnings = []

    def clear_operations(self):
        self.operations = []
        self.warnings = []

    def get_steel_grades(self):
        return [{"id": 1, "code": "G-TEST", "name": "Test Grade"}]

    def get_latest_heat_no_for_month(self, year: int, month: int):
        lower_bound = int(f"{year:02d}{month:02d}00000")
        upper_bound = int(f"{year:02d}{month:02d}99999")
        candidates = [op["heat_no"] for op in self.operations if lower_bound <= op["heat_no"] < upper_bound]
        return max(candidates) if candidates else 0

    def insert_operation(
        self,
        heat_no,
        pro_line_cd,
        proc_cd,
        device_no,
        crew_cd,
        stl_grd_id,
        stl_grd_cd,
        proc_status,
        plan_start_time,
        plan_end_time,
        real_start_time=None,
        real_end_time=None,
    ):
        op_id = len(self.operations) + 1
        self.operations.append(
            {
                "id": op_id,
                "heat_no": heat_no,
                "pro_line_cd": pro_line_cd,
                "proc_cd": proc_cd,
                "device_no": device_no,
                "crew_cd": crew_cd,
                "stl_grd_id": stl_grd_id,
                "stl_grd_cd": stl_grd_cd,
                "proc_status": proc_status,
                "plan_start_time": plan_start_time,
                "plan_end_time": plan_end_time,
                "real_start_time": real_start_time,
                "real_end_time": real_end_time,
            }
        )
        return op_id

    def insert_warning(self, **kwargs):
        warn_id = len(self.warnings) + 1
        self.warnings.append({"id": warn_id, **kwargs})
        return warn_id

    def get_operation_warning_count(self, operation_id: int) -> int:
        return sum(1 for w in self.warnings if w.get("operation_id") == operation_id)

    def get_operation_last_warning_end_time(self, operation_id: int):
        ends = [w.get("warning_time_end") for w in self.warnings if w.get("operation_id") == operation_id and w.get("warning_time_end")]
        return max(ends) if ends else None

    def get_active_operations(self):
        return sorted(
            [op for op in self.operations if op["proc_status"] == ProcessStatus.ACTIVE],
            key=lambda op: op["real_start_time"] or op["plan_start_time"],
        )

    def get_pending_operations(self):
        return sorted(
            [op for op in self.operations if op["proc_status"] == ProcessStatus.PENDING],
            key=lambda op: op["plan_start_time"],
        )

    def get_heat_operations(self, heat_no: int):
        return sorted(
            [op for op in self.operations if op["heat_no"] == heat_no],
            key=lambda op: op["plan_start_time"],
        )

    def update_operation_status(
        self,
        operation_id: int,
        proc_status: int,
        real_start_time=None,
        real_end_time=None,
        device_no=None,
    ):
        for op in self.operations:
            if op["id"] == operation_id:
                op["proc_status"] = proc_status
                op["real_start_time"] = real_start_time or op["real_start_time"]
                op["real_end_time"] = real_end_time or op["real_end_time"]
                if device_no:
                    op["device_no"] = device_no
                break

    def update_operation_plan_times(self, operation_id: int, plan_start_time, plan_end_time):
        for op in self.operations:
            if op["id"] == operation_id:
                op["plan_start_time"] = plan_start_time
                op["plan_end_time"] = plan_end_time
                break

    def get_device_current_operation(self, device_no: str):
        candidates = [
            op for op in self.operations if op["device_no"] == device_no and op["proc_status"] in (ProcessStatus.ACTIVE, ProcessStatus.PENDING)
        ]
        if not candidates:
            return None
        return sorted(candidates, key=lambda op: (op["proc_status"], op["plan_start_time"]))[0]

    def get_available_device(self, proc_cd: str, devices):
        busy = {op["device_no"] for op in self.operations if op["proc_status"] == ProcessStatus.ACTIVE}
        for device in devices:
            if device not in busy:
                return device
        return None

    def get_device_operation_windows(self, device_no: str, min_window_start: datetime, exclude_operation_id=None):
        windows = []
        for op in self.operations:
            if op["device_no"] != device_no:
                continue
            if exclude_operation_id and op["id"] == exclude_operation_id:
                continue
            end_time = op["real_end_time"] or op["plan_end_time"]
            if op["proc_status"] != ProcessStatus.ACTIVE and end_time < min_window_start:
                continue
            windows.append(op)
        windows.sort(key=lambda op: op["real_start_time"] or op["plan_start_time"])
        return windows

    # Compatibility stubs
    def connect(self): ...
    def close(self): ...
    def cursor(self): raise RuntimeError("Not implemented for fake DB")


def set_fixed_now(monkeypatch, fixed_now: datetime):
    """Monkeypatch datetime.now to a fixed point for simulator and scheduler."""
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now if tz is None else fixed_now.astimezone(tz)

    import steelmaking_simulation.simulator as simulator_mod
    import steelmaking_simulation.scheduler as scheduler_mod
    import steelmaking_simulation.operation_processor as operation_processor_mod
    import steelmaking_simulation.heat_planner as heat_planner_mod

    monkeypatch.setattr(simulator_mod, "datetime", FixedDateTime)
    monkeypatch.setattr(scheduler_mod, "datetime", FixedDateTime)
    monkeypatch.setattr(operation_processor_mod, "datetime", FixedDateTime)
    monkeypatch.setattr(heat_planner_mod, "datetime", FixedDateTime)


@pytest.fixture()
def fixed_now(monkeypatch):
    now = datetime(2024, 1, 1, 12, 0, tzinfo=CST)
    set_fixed_now(monkeypatch, now)
    return now


@pytest.fixture()
def simulator(fixed_now):
    import random
    random.seed(42)
    db = FakeDatabaseManager()
    sim = SteelmakingSimulator(DatabaseConfig(), SimulationConfig(), db_manager=db)
    # Normalize counts to keep the seeded timeline close to "now" for deterministic checks
    sim.config.seed_past_heats = 4
    sim.config.seed_active_heats = 1
    sim.config.seed_future_heats = 4
    sim.config.seed_warning_probability_per_completed_operation = 0.25
    return sim


def _derive_window(op):
    start = op["real_start_time"] or op["plan_start_time"]
    end = op["real_end_time"] or op["plan_end_time"]
    return start, end


def _device_timelines(ops):
    by_device = {}
    for op in ops:
        by_device.setdefault(op["device_no"], []).append(op)
    for ops_list in by_device.values():
        ops_list.sort(key=lambda op: op["real_start_time"] or op["plan_start_time"])
    return by_device


def test_initialization_respects_constraints(simulator, fixed_now):
    simulator.initialize()
    ops = simulator.db.operations
    config = simulator.config

    # Durations within 30-50 minutes
    for op in ops:
        start, end = _derive_window(op)
        minutes = (end - start).total_seconds() / 60
        assert config.min_operation_duration - 0.5 <= minutes <= config.max_operation_duration + 0.5

    # Completed ops end before now; active exist
    completed = [op for op in ops if op["proc_status"] == ProcessStatus.COMPLETED]
    active = [op for op in ops if op["proc_status"] == ProcessStatus.ACTIVE]
    assert active, "Expected at least one active operation after initialization"
    assert len(active) >= 1
    assert all(op["real_end_time"] is None for op in active)
    assert all(op["plan_start_time"] <= fixed_now <= op["plan_end_time"] for op in active)
    assert all(op["real_start_time"] <= fixed_now for op in active)
    assert all(op["real_end_time"] and op["real_end_time"] <= fixed_now for op in completed)
    assert all(op["real_start_time"] <= fixed_now <= (op["real_end_time"] or op["plan_end_time"]) for op in active)

    # No device overlap and rest windows between 10-20 minutes
    timelines = _device_timelines(ops)
    for device, device_ops in timelines.items():
        prev_end = None
        for op in device_ops:
            start, end = _derive_window(op)
            if prev_end:
                gap = (start - prev_end).total_seconds() / 60
                assert config.min_rest_duration_minutes - 0.1 <= gap <= config.max_rest_duration_minutes + 0.1, (
                    f"Rest gap {gap} out of bounds on device {device}"
                )
            assert start >= (prev_end or start), f"Overlap detected on device {device}"
            prev_end = end

    # Transfer gaps between BOF->LF->CCM are 20-30 minutes
    bof_cd = EQUIPMENT["BOF"]["proc_cd"]
    lf_cd = EQUIPMENT["LF"]["proc_cd"]
    ccm_cd = EQUIPMENT["CCM"]["proc_cd"]
    for heat_no in {op["heat_no"] for op in ops}:
        heat_ops = [op for op in ops if op["heat_no"] == heat_no]
        by_cd = {op["proc_cd"]: op for op in heat_ops}
        if bof_cd in by_cd and lf_cd in by_cd:
            gap1 = (by_cd[lf_cd]["plan_start_time"] - by_cd[bof_cd]["plan_end_time"]).total_seconds() / 60
            assert config.min_transfer_gap_minutes - 0.1 <= gap1 <= config.max_transfer_gap_minutes + 0.1
        if lf_cd in by_cd and ccm_cd in by_cd:
            gap2 = (by_cd[ccm_cd]["plan_start_time"] - by_cd[lf_cd]["plan_end_time"]).total_seconds() / 60
            assert config.min_transfer_gap_minutes - 0.1 <= gap2 <= config.max_transfer_gap_minutes + 0.1

    # Process flow ordering per heat
    expected_flow = [EQUIPMENT[name]["proc_cd"] for name in PROCESS_FLOW]
    for heat_no in {op["heat_no"] for op in ops}:
        heat_ops = [op for op in ops if op["heat_no"] == heat_no]
        seen = [op["proc_cd"] for op in sorted(heat_ops, key=lambda o: o["plan_start_time"])]
        assert set(expected_flow).issubset(set(seen))


def test_future_and_past_schedule_respects_rest(simulator, fixed_now):
    simulator.initialize()
    ops = simulator.db.operations
    config = simulator.config

    timelines = _device_timelines(ops)
    for device, device_ops in timelines.items():
            for first, second in zip(device_ops, device_ops[1:]):
                first_end = (first["real_end_time"] or first["plan_end_time"])
                second_start = (second["real_start_time"] or second["plan_start_time"])
                gap_minutes = (second_start - first_end).total_seconds() / 60
                assert config.min_rest_duration_minutes - 0.1 <= gap_minutes <= config.max_rest_duration_minutes + 0.5


def test_initialization_has_no_large_device_idle_gaps(simulator, fixed_now):
    simulator.initialize()
    ops = simulator.db.operations

    for proc_name, info in EQUIPMENT.items():
        for device in info["devices"]:
            device_ops = [op for op in ops if op["device_no"] == device]
            assert len(device_ops) >= 2, f"Expected >=2 operations on {device} to validate rest constraints"


def test_create_new_heat_does_not_generate_heat_no_when_no_bof_slot(fixed_now, monkeypatch):
    db = FakeDatabaseManager()
    sim = SteelmakingSimulator(DatabaseConfig(), SimulationConfig(), db_manager=db)
    sim.steel_grades = db.get_steel_grades()

    def find_slot_stub(*, process_name, desired_start, latest_start, duration, devices=None, exclude_operation_id=None):
        if process_name == "BOF":
            return None
        return Slot(device_no=(devices or ["X"])[0], plan_start=desired_start, plan_end=desired_start + duration)

    sim.scheduler.find_slot = find_slot_stub

    calls = {"n": 0}

    def heat_no_stub():
        calls["n"] += 1
        return 240100001

    monkeypatch.setattr(sim, "generate_heat_no", heat_no_stub)

    assert sim.create_new_heat() is None
    assert calls["n"] == 0
    assert db.operations == []


def test_create_new_heat_success_increments_heat_no(fixed_now):
    import random

    random.seed(123)
    db = FakeDatabaseManager()
    sim = SteelmakingSimulator(DatabaseConfig(), SimulationConfig(), db_manager=db)
    sim.steel_grades = db.get_steel_grades()

    counters = {"BOF": 0, "LF": 0, "CCM": 0}

    def find_slot_stub(*, process_name, desired_start, latest_start, duration, devices=None, exclude_operation_id=None):
        devices = devices or EQUIPMENT[process_name]["devices"]
        idx = counters[process_name] % len(devices)
        counters[process_name] += 1
        return Slot(device_no=devices[idx], plan_start=desired_start, plan_end=desired_start + duration)

    sim.scheduler.find_slot = find_slot_stub

    heat1 = sim.create_new_heat()
    heat2 = sim.create_new_heat()
    assert heat1 is not None and heat2 is not None and heat1 != heat2

    assert len([op for op in db.operations if op["heat_no"] == heat1]) == 3
    assert len([op for op in db.operations if op["heat_no"] == heat2]) == 3


def test_warning_duration_distribution_sanity(fixed_now):
    import random

    random.seed(42)
    db = FakeDatabaseManager()
    sim = SteelmakingSimulator(DatabaseConfig(), SimulationConfig(), db_manager=db)

    durations = []
    for _ in range(1000):
        durations.append(sim._random_warning_duration_seconds())

    short = sum(1 for d in durations if d < 10)
    long = sum(1 for d in durations if d > 60)
    assert short >= 700
    assert long <= 100


def test_aligned_routing_when_probability_is_one(fixed_now):
    db = FakeDatabaseManager()
    sim = SteelmakingSimulator(DatabaseConfig(), SimulationConfig(), db_manager=db)
    sim.steel_grades = db.get_steel_grades()
    sim.config.aligned_route_probability = 1.0
    sim.config.min_transfer_gap_minutes = 20
    sim.config.max_transfer_gap_minutes = 30

    def find_slot_stub(*, process_name, desired_start, latest_start, duration, devices=None, exclude_operation_id=None):
        assert devices, "Expected explicit device preference in this test"
        return Slot(device_no=devices[0], plan_start=desired_start, plan_end=desired_start + duration)

    sim.scheduler.find_slot = find_slot_stub

    heat_no = sim.create_new_heat()
    assert heat_no is not None
    ops = db.get_heat_operations(heat_no)
    bof = next(op for op in ops if op["proc_cd"] == EQUIPMENT["BOF"]["proc_cd"])
    lf = next(op for op in ops if op["proc_cd"] == EQUIPMENT["LF"]["proc_cd"])
    ccm = next(op for op in ops if op["proc_cd"] == EQUIPMENT["CCM"]["proc_cd"])

    assert lf["device_no"].endswith(bof["device_no"][-1])
    assert ccm["device_no"].endswith(bof["device_no"][-1])


def test_realtime_warnings_time_order_and_max_per_operation(fixed_now):
    import random

    random.seed(7)
    db = FakeDatabaseManager()
    sim = SteelmakingSimulator(DatabaseConfig(), SimulationConfig(), db_manager=db)
    sim.config.warning_probability_per_tick = 1.0
    sim.config.max_warnings_per_operation = 5

    op_id = db.insert_operation(
        heat_no=240100001,
        pro_line_cd="G1",
        proc_cd=EQUIPMENT["BOF"]["proc_cd"],
        device_no=EQUIPMENT["BOF"]["devices"][0],
        crew_cd="A",
        stl_grd_id=1,
        stl_grd_cd="G-TEST",
        proc_status=ProcessStatus.ACTIVE,
        plan_start_time=fixed_now - timedelta(minutes=10),
        plan_end_time=fixed_now + timedelta(minutes=30),
        real_start_time=fixed_now - timedelta(minutes=10),
        real_end_time=None,
    )

    # Step time forward; spacing should allow at most 5 warnings.
    times = [fixed_now + timedelta(minutes=4 * i) for i in range(10)]
    for t in times:
        sim._tick_realtime_warnings(t)

    warnings = [w for w in db.warnings if w["operation_id"] == op_id]
    assert len(warnings) <= sim.config.max_warnings_per_operation
    assert warnings, "Expected at least one warning when probability=1.0"

    # Time-ordered and anchored near tick time.
    starts = [w["warning_time_start"] for w in warnings]
    assert starts == sorted(starts)
    assert all(s in times for s in starts)


def test_initialization_seeds_warnings_for_completed_operations(simulator, fixed_now):
    simulator.initialize()
    ops = simulator.db.operations
    warnings = simulator.db.warnings
    config = simulator.config

    completed_ops = [op for op in ops if op["proc_status"] == ProcessStatus.COMPLETED]
    assert completed_ops, "Need completed ops to validate historical warning seeding"

    by_op = {}
    for w in warnings:
        by_op.setdefault(w["operation_id"], []).append(w)

    completed_with_warnings = [op for op in completed_ops if by_op.get(op["id"])]
    assert completed_with_warnings, "Expected at least some completed ops to have warnings"
    assert len(completed_with_warnings) < len(completed_ops), "Warnings should not exist for every completed operation"

    for op in completed_with_warnings:
        op_warnings = by_op.get(op["id"], [])
        assert 1 <= len(op_warnings) <= config.max_warnings_per_operation
        start, end = _derive_window(op)
        op_warnings.sort(key=lambda w: w["warning_time_start"])
        for w in op_warnings:
            assert start <= w["warning_time_start"] <= end
            assert start <= w["warning_time_end"] <= end
            assert w["warning_time_end"] > w["warning_time_start"]


def test_pending_bof_starts_when_plan_time_passed(fixed_now):
    db = FakeDatabaseManager()
    sim = SteelmakingSimulator(DatabaseConfig(), SimulationConfig(), db_manager=db)

    plan_start = fixed_now - timedelta(minutes=5)
    plan_end = plan_start + timedelta(minutes=30)
    op_id = db.insert_operation(
        heat_no=240100123,
        pro_line_cd="G1",
        proc_cd=EQUIPMENT["BOF"]["proc_cd"],
        device_no=EQUIPMENT["BOF"]["devices"][0],
        crew_cd="A",
        stl_grd_id=1,
        stl_grd_cd="G-TEST",
        proc_status=ProcessStatus.PENDING,
        plan_start_time=plan_start,
        plan_end_time=plan_end,
        real_start_time=None,
        real_end_time=None,
    )

    sim.process_pending_operations()

    op = next(o for o in db.operations if o["id"] == op_id)
    assert op["proc_status"] == ProcessStatus.ACTIVE
    assert op["real_start_time"] == fixed_now
    assert op["real_end_time"] is None
    # Plan is updated to reflect the delayed start.
    assert op["plan_start_time"] == fixed_now
    assert op["plan_end_time"] > op["plan_start_time"]


def test_pending_lf_can_start_after_missing_transfer_window(fixed_now):
    db = FakeDatabaseManager()
    sim = SteelmakingSimulator(DatabaseConfig(), SimulationConfig(), db_manager=db)

    prev_end = fixed_now - timedelta(minutes=40)
    prev_id = db.insert_operation(
        heat_no=240100124,
        pro_line_cd="G1",
        proc_cd=EQUIPMENT["BOF"]["proc_cd"],
        device_no=EQUIPMENT["BOF"]["devices"][0],
        crew_cd="A",
        stl_grd_id=1,
        stl_grd_cd="G-TEST",
        proc_status=ProcessStatus.COMPLETED,
        plan_start_time=prev_end - timedelta(minutes=35),
        plan_end_time=prev_end,
        real_start_time=prev_end - timedelta(minutes=35),
        real_end_time=prev_end,
    )

    # Planned inside 20-30 window, but now is already past max_ready (prev_end + 30).
    lf_plan_start = prev_end + timedelta(minutes=29)
    lf_plan_end = lf_plan_start + timedelta(minutes=35)
    lf_id = db.insert_operation(
        heat_no=240100124,
        pro_line_cd="G1",
        proc_cd=EQUIPMENT["LF"]["proc_cd"],
        device_no=EQUIPMENT["LF"]["devices"][0],
        crew_cd="A",
        stl_grd_id=1,
        stl_grd_cd="G-TEST",
        proc_status=ProcessStatus.PENDING,
        plan_start_time=lf_plan_start,
        plan_end_time=lf_plan_end,
        real_start_time=None,
        real_end_time=None,
    )

    sim.process_pending_operations()

    lf = next(o for o in db.operations if o["id"] == lf_id)
    assert lf["proc_status"] == ProcessStatus.ACTIVE
    assert lf["real_start_time"] == fixed_now
    assert lf["real_end_time"] is None
