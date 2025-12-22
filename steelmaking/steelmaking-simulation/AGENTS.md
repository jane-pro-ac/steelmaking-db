# Steelmaking Simulation – Agent Guide

- **Purpose**: Continuously simulate steelmaking operations for demo/testing environments. It seeds and drives data in `steelmaking.steelmaking_operation`, `steelmaking.steelmaking_warning`, `steelmaking.steelmaking_event`, and `steelmaking.steelmaking_kpi_stats` tables to mimic BOF → LF → CCM flows with realistic timing, crew assignments, event sequences, and KPI statistics.

- **Project layout** (Engineering-grade modular structure):
  
  The project follows a modular package structure with clear separation of concerns.

  **Config Package** (`steelmaking_simulation/config/`):
  - `settings.py`: Environment-configurable settings (`DatabaseConfig`, `SimulationConfig`)
  - `constants.py`: Process status enum, PRO_LINE_CD, CREW_CODES
  - `equipment.py`: Equipment definitions and process flow configuration
  - `__init__.py`: Package exports

  **Database Package** (`steelmaking_simulation/database/`):
  - `manager.py`: `DatabaseManager` class with connection management
  - `operations.py`: Operations-related database queries
  - `warnings.py`: Warning-related database queries
  - `events.py`: Event-related database queries
  - `kpi_stats.py`: KPI statistics database queries (`KpiStatsQueries`)
  - `__init__.py`: Package exports

  **Utils Package** (`steelmaking_simulation/utils/`):
  - `time_utils.py`: Shared time constants (CST timezone)
  - `__init__.py`: Package exports

  **Events Package** (`steelmaking_simulation/events/`):
  - `codes.py`: Event code definitions (`EVENT_CODES`, `PROC_CD_TO_NAME`)
  - `sequences.py`: Event sequence configurations (`EventSequenceConfig`, `EVENT_SEQUENCE_CONFIGS`)
  - `messages.py`: Chinese message template generator (`EventMessageGenerator`)
  - `generator.py`: Core event generation logic (`Event`, `EventGenerator`, `EventSequenceResult`, `SpecialEventType`)
  - `engine.py`: Event engine for historical seeding and real-time tick (`EventEngine`, `EventEngineConfig`)
  - `__init__.py`: Package exports

  **Warnings Package** (`steelmaking_simulation/warnings/`):
  - `templates.py`: Warning templates and payload dataclass (`WARNING_TEMPLATES`, `WarningPayload`)
  - `engine.py`: Warning engine for historical seeding and real-time tick (`WarningEngine`)
  - `__init__.py`: Package exports

  **KPI Stats Package** (`steelmaking_simulation/kpi_stats/`):
  - `generator.py`: KPI value generation logic (`KpiValueGenerator`, `KpiStat`)
  - `engine.py`: KPI stats engine for historical seeding and real-time tick (`KpiStatsEngine`, `KpiStatsEngineConfig`)
  - `__init__.py`: Package exports

  **Core Package** (`steelmaking_simulation/core/`):
  - `simulator.py`: Main orchestration layer (`SteelmakingSimulator`)
  - `scheduler.py`: Device slot finder (`DeviceScheduler`, `Slot`)
  - `processor.py`: Runtime operation progression (`OperationProcessor`, `OperationProcessorContext`)
  - `__init__.py`: Package exports

  **Seeding Package** (`steelmaking_simulation/seeding/`):
  - `seeder.py`: Initialization seeding logic (`OperationSeeder`, `SeedContext`)
  - `__init__.py`: Package exports

  **Planning Package** (`steelmaking_simulation/planning/`):
  - `heat_planner.py`: New heat creation logic (`HeatPlanner`, `HeatPlanContext`)
  - `__init__.py`: Package exports

  **Root Package** (`steelmaking_simulation/`):
  - `main.py`: CLI entrypoint; wires config/logging and starts the simulator
  - `__init__.py`: Package-level exports (re-exports all symbols from subpackages for convenience)

  **Tests** (`tests/`):
  - `conftest.py`: Shared test fixtures and `FakeDatabaseManager` for in-memory testing
  - `core/test_simulator_constraints.py`: Comprehensive constraint coverage tests (24 tests)
  - `events/test_event_generator.py`: Event sequence validation and message generation tests (44 tests)
  - `kpi_stats/test_kpi_generator.py`: KPI value generation tests (16 tests)
  - `kpi_stats/test_kpi_engine.py`: KPI stats engine tests (16 tests)

  **Root Docs**: 
  - `README.md` (how to run)
  - `AGENTS.md` (this file - agent guide)
  - `pyproject.toml` (Poetry configuration)

  **Related Files** (in parent `steelmaking/` directory):
  - `kpi_code.json`: KPI code definitions JSON file containing process-specific KPI metadata (BOF, LF, RH, CCM). Includes `kpi_code`, `name_cn`, `name_en`, `unit`, `desc_cn`, and `level` for each KPI. Used as source data for seeding `steelmaking.steelmaking_kpi_def` table.
  - `seed_steelmaking_kpi_def.sql`: SQL script to seed KPI definitions into the database.
  - `steelmaking_kpi_def.sql`: Table schema for KPI definitions.
  - `steelmaking_kpi_stats.sql`: Table schema for KPI statistics.
  - `event_code_constraints.md`: Authoritative event sequence constraints documentation.

- **Setup & run**:
  - Requirements: Python 3.10+, Poetry, reachable Postgres.
  - Install deps: `poetry install`.
  - Configure environment (copy `.env.example` → `.env` if present): `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, plus optional `SIMULATION_INTERVAL`, `NEW_HEAT_PROBABILITY`, `DEMO_SEED_PAST_HEATS`, `DEMO_SEED_FUTURE_HEATS`.
  - Start simulator: `poetry run simulate` (or `poetry shell` then `python -m steelmaking_simulation.main`).
  - Advanced knobs:
    - Operation duration: `MIN_OPERATION_DURATION_MINUTES` / `MAX_OPERATION_DURATION_MINUTES` (defaults 30/50)
    - Device rest (hard constraint): `MIN_REST_DURATION_MINUTES` (default 10), `MAX_REST_DURATION_MINUTES` (default 20)
    - Heat transfer gaps (BOF→LF→CCM): `MIN_TRANSFER_GAP_MINUTES` (default 20), `MAX_TRANSFER_GAP_MINUTES` (default 30)
    - Routing preference: `ALIGNED_ROUTE_PROBABILITY` (default 0.9) biases BOF#i → LF#i → CCM#i (rare cross-routing still allowed)
    - Warnings: `MAX_WARNINGS_PER_OPERATION` (default 5), `WARNING_PROBABILITY_PER_TICK` (default 0.1)
    - Seed warnings: `SEED_WARNING_PROBABILITY_PER_COMPLETED_OPERATION` (default 0.25) controls how often completed operations get historical warnings during initialization.
    - KPI stats: `SEED_KPI_STATS_PROBABILITY` (default 0.95), `MIN_KPI_SAMPLES_PER_OPERATION` (default 5), `MAX_KPI_SAMPLES_PER_OPERATION` (default 15), `KPI_PROBABILITY_PER_TICK` (default 0.4), `MIN_KPI_SAMPLE_INTERVAL_SECONDS` (default 30), `MAX_REALTIME_KPI_SAMPLES_PER_OPERATION` (default 50), `KPI_OUT_OF_RANGE_PROBABILITY` (default 0.05), `KPI_OUT_OF_RANGE_FACTOR` (default 0.15).
    - Demo seeding: `DEMO_SEED_*` knobs primarily shape the seeded time horizon/density around "now".

- **Data model expectations**:
  - `steelmaking.steelmaking_operation` columns used: `heat_no`, `pro_line_cd`, `proc_cd`, `device_no`, `crew_cd`, `stl_grd_id`, `stl_grd_cd`, `proc_status`, `plan_start_time`, `plan_end_time`, `real_start_time`, `real_end_time`, `extra`. `crew_cd` must be one of `CREW_CODES` (A/B/C/D); `stl_grd_id` references `base.steel_grade.id`.
    - `proc_status` values: 0=COMPLETED, 1=ACTIVE, 2=PENDING, 3=CANCELED (DB constraint allows 0-3).
  - `steelmaking.steelmaking_warning` is populated during seeding and ticks (truncated on startup together with operations). Schema columns now exclude `operation_id`; only `heat_no`, `pro_line_cd`, `proc_cd`, `device_no`, `warning_code`, `warning_msg`, `warning_level`, `warning_time_start`, `warning_time_end`, `extra` are written. `extra` carries contextual metadata (`operation_id`, `crew_cd`) for traceability. Warning messages are generated in中文.
  - `steelmaking.steelmaking_event` is populated during seeding and ticks (truncated on startup together with operations/warnings). Columns: `heat_no`, `pro_line_cd`, `proc_cd`, `device_no`, `event_code`, `event_name`, `event_msg`, `event_time_start`, `event_time_end`, `extra`. Event messages are generated in中文 with realistic parameters.
  - `steelmaking.steelmaking_kpi_stats` is populated during seeding and ticks (truncated on startup). Columns: `heat_no`, `pro_line_cd`, `proc_cd`, `device_no`, `kpi_code`, `stat_value`, `sample_time`, `extra`. KPI definitions are read from `steelmaking.steelmaking_kpi_def` table which contains `proc_cd`, `kpi_code`, `kpi_name`, `unit`, `int_digits`, `decimal_digits`, `upper_limit`, `lower_limit`, etc.
  - Heat number format: `YYMMNNNNN` where the last 5 digits auto-increment per month.

- **Simulation behavior**:
  - Seeding: On startup, truncates warnings/operations/events, then seeds a **continuous timeline of heats around "now"**. Each operation's status is derived from its planned window relative to "now":
    - `COMPLETED`: `plan_end_time <= now` and `real_start_time/real_end_time` are set (both before now)
    - `ACTIVE`: `plan_start_time <= now < plan_end_time`, `real_start_time` is set, and `real_end_time` is NULL
    - `PENDING`: `plan_start_time > now` and real times are NULL
    This ensures initialization always contains in-progress operations while keeping completed rows strictly in the past.
  - Tick loop: Processes active ops (may complete them), starts pending ops once predecessors and device availability allow, and may create a new heat per tick with probability `NEW_HEAT_PROBABILITY`. Active ops may emit real-time-ish 中文 warnings and events anchored to the current tick time.
    - Note: BOF (first stage) pending operations start when `now >= plan_start_time` and a BOF device is available (no predecessor gate).
    - Runtime does **not** reschedule or rewrite planned timestamps. If upstream delays happen, real execution drifts while plans remain stable.
  - Timing & constraints (applied uniformly to seeding and runtime):
    - Each operation duration is randomized between `MIN_OPERATION_DURATION_MINUTES`–`MAX_OPERATION_DURATION_MINUTES` (defaults **30–50 minutes**).
    - Devices are never double-booked (a device cannot run two processes at the same time).
    - For each device, the rest gap between consecutive operations is at least **10 minutes** (`MIN_REST_DURATION_MINUTES`).
      - Initialization/new-heat planning keeps the rest gap within **10–20 minutes** (`MAX_REST_DURATION_MINUTES`) to generate a continuous plan.
      - Runtime is **soft** on the upper bound: long idles must not block starting ready operations.
    - For each heat, transfer gaps **BOF→LF** and **LF→CCM** target **20–30 minutes** (`MIN_TRANSFER_GAP_MINUTES`/`MAX_TRANSFER_GAP_MINUTES`).
      - Initialization and new-heat planning try to keep transfers in-window.
      - Runtime is **soft**: if scheduling conflicts cause a miss, the next stage may start later than 30 minutes (never earlier than 20), while still honoring device rest and non-overlap constraints.
    - Routing is biased toward aligned lines (e.g., `G120`→`G130`→`G160`), with occasional cross-routing.
  - Warnings:
    - Initialization: **COMPLETED** operations get **historical warnings** seeded within their own operation time window for realistic demo data.
      - Historical warnings are intentionally **not** present on every completed operation; rate is controlled by `SEED_WARNING_PROBABILITY_PER_COMPLETED_OPERATION`.
    - Runtime: Warnings are generated **near real-time** during ticks (anchored to "now"), and inserted in time order (not backfilled at random times within the historical plan window).
    - Max **N warnings per operation** (`MAX_WARNINGS_PER_OPERATION`, default 5) and throttled to keep them reasonably dispersed across the operation runtime.
    - Duration distribution: almost always short (<10s), occasionally up to 1 minute, rarely longer; codes/messages are chosen from process-specific templates (plus common fallbacks).
  - Events:
    - Each operation generates a sequence of events following process-specific constraints defined in `steelmaking/event_code_constraints.md`.
    - Event sequences follow a strict pattern:
      1. **Start sequence**: Events like 钢包到达 → 处理开始 → 炉次开始
      2. **Middle events**: Processing events like 加料, 测温, 取样, 喷吹, etc. (randomized with constraints)
      3. **End sequence**: Events like 炉次结束 → 处理结束 → 钢包离开
    - Paired events (e.g., 氧枪喷吹开始/结束, 通电开始/结束) always occur together.
    - Follow-up events (e.g., 钢水取样 → 收到钢水化验) are emitted in sequence.
    - **Special Events (取消/回炉)**:
      - **取消 (Cancel)**: When a cancel event occurs (e.g., G12007 炉次取消), the current operation and all subsequent operations for the same heat are marked as `CANCELED` (proc_status=3). The event sequence ends early with a shortened end sequence.
      - **回炉 (Rework)**: When a rework event occurs (e.g., G13007 炉次回炉), the operation continues to normal completion but is flagged for rework.
      - Process-specific special events:
        - **BOF**: G12007 炉次取消 only (no rework)
        - **LF**: G13007 炉次回炉, G13008 炉次取消
        - **RH**: G15007 炉次回炉, G15008 炉次取消
        - **CCM**: G16015 炉次开浇取消 only (no rework)
      - Probabilities are configurable via environment variables:
        - `CANCEL_EVENT_PROBABILITY` (default 0.02 = 2% per operation)
        - `REWORK_EVENT_PROBABILITY` (default 0.03 = 3% per operation)
    - Event codes by process:
      - **BOF (G12)**: G12001-G12028 (钢包到达, 加废钢, 兑铁水, 氧枪喷吹, 出钢, etc.)
      - **LF (G13)**: G13001-G13025 (钢包到达, 加料, 喂丝, 通电, 吹氩, etc.)
      - **RH (G15)**: G15001-G15025 (钢包到达, 抽真空, 达到高真空, 破空, etc.)
      - **CCM (G16)**: G16001-G16022 (炉次到受包位, 炉次开浇, 中包测温, 铸坯产生, etc.)
    - Historical events: **COMPLETED** operations are always seeded and any missing required events are backfilled (start/middle/follow-up/paired/end).
    - **Partial events for ACTIVE operations**: During initialization, **ACTIVE** operations (which have been running for some time) get partial events seeded via `EventEngine.seed_partial_events_for_active_operation()`. This generates the start sequence events plus some middle events proportional to how long the operation has been running. This ensures ACTIVE operations realistically have some events already generated.
    - Real-time events: **ACTIVE** operations may emit events during ticks (max 15 per operation), with 30s minimum spacing.
    - **End sequence events on completion**: When an active operation completes at runtime, the `EventEngine.emit_end_sequence_events()` method backfills any missing required events (start/middle/follow-up/paired/end). This ensures operations always have complete event coverage regardless of how many real-time events were emitted during the operation.
    - Event messages are in Chinese and include realistic parameters (e.g., 温度值, 物料名称, 重量).
  - KPI Statistics:
    - KPI definitions are loaded from `steelmaking.steelmaking_kpi_def` table at startup and cached.
    - Each process (BOF/G12, LF/G13, RH/G15, CCM/G16) has its own set of KPI definitions.
    - **Historical KPI stats**: **COMPLETED** operations get historical KPI stats seeded with 95% probability (`SEED_KPI_STATS_PROBABILITY`). Each operation gets 5-15 sample points distributed across its duration.
    - **Partial KPI stats for ACTIVE operations**: During initialization, **ACTIVE** operations get partial KPI stats seeded via `KpiStatsEngine.seed_partial_kpi_stats_for_active_operation()`, proportional to elapsed time.
    - **Real-time KPI stats**: **ACTIVE** operations emit KPI stats during ticks with 40% probability (`KPI_PROBABILITY_PER_TICK`), respecting minimum 30s spacing (`MIN_KPI_SAMPLE_INTERVAL_SECONDS`) and max 50 samples per operation (`MAX_REALTIME_KPI_SAMPLES_PER_OPERATION`).
    - **Value generation**: Values are generated based on KPI definitions (upper_limit, lower_limit, int_digits, decimal_digits). Different KPI types have specialized generators:
      - Temperature KPIs: Gradual changes, operating range centered
      - Rate/flow KPIs: Variable, sometimes near zero
      - Cumulative KPIs: Increase with operation progress
      - Deviation KPIs: Centered around 0
      - Chemical composition KPIs: Target range with progress-based drift
    - **Out-of-range values**: 5% probability (`KPI_OUT_OF_RANGE_PROBABILITY`) of generating values exceeding limits by up to 15% (`KPI_OUT_OF_RANGE_FACTOR`) to simulate real-world anomalies.

- **Development tips**:
  - Keep schema alignment tight; update `database/` package and docs whenever table columns change.
  - Prefer adding new configuration flags to `.env`-driven dataclasses in `config/settings.py`.
  - Logging is configured in `main.py`; adjust there for verbosity.
  - Avoid destructive DB commands beyond the intentional truncate in `DatabaseManager.clear_operations()`.
  - If you add warning generation, reuse `DatabaseManager.cursor()` for transactional safety and ensure both `warning_time_start` and `warning_time_end` are written.
  - If you add new event codes or modify constraints, update `events/codes.py` (EVENT_CODES), `events/sequences.py` (EVENT_SEQUENCE_CONFIGS) and add corresponding tests.
  - Unit checks: see `tests/core/test_simulator_constraints.py` for constraint coverage (no-overlap, device rest bounds, transfer gaps 20–30, active semantics, aligned routing preference, heat number generation behavior, real-time warning ordering/max, warning duration distribution, **end event generation on operation completion**, **partial event seeding for active operations**).
  - Event tests: see `tests/events/test_event_generator.py` for event sequence validation, message generation, and constraint compliance.
  - **Module organization**: When adding new functionality, place it in the appropriate package:
    - Configuration: `config/`
    - Database operations: `database/`
    - Event-related: `events/`
    - Warning-related: `warnings/`
    - KPI stats-related: `kpi_stats/`
    - Core simulation logic: `core/`
    - Seeding logic: `seeding/`
    - Planning logic: `planning/`
  - **Import patterns**: Use modular imports:
    ```python
    # Recommended imports
    from steelmaking_simulation.config import DatabaseConfig, SimulationConfig
    from steelmaking_simulation.core import SteelmakingSimulator, DeviceScheduler, Slot
    from steelmaking_simulation.events import EventGenerator, EVENT_CODES
    from steelmaking_simulation.warnings import WarningEngine
    from steelmaking_simulation.kpi_stats import KpiStatsEngine, KpiValueGenerator
    from steelmaking_simulation.utils import CST
    
    # Or import directly from submodules for specific items
    from steelmaking_simulation.config.settings import DatabaseConfig
    from steelmaking_simulation.core.simulator import SteelmakingSimulator
    from steelmaking_simulation.kpi_stats.engine import KpiStatsEngine
    ```

- **Maintenance checks**:
  - Sanity-test connection with `psql`/`poetry run python -c "from steelmaking_simulation.database import DatabaseManager; from steelmaking_simulation.config import DatabaseConfig; DatabaseManager(DatabaseConfig()).connect()"`.
  - When changing process flow or equipment, update `config/equipment.py` (`PROCESS_FLOW`, `EQUIPMENT`), and any downstream logic that assumes BOF → LF → CCM order.
  - Validate generated timestamps stay within configured duration/gap bounds and honor sequential process rules before shipping changes.
  - When updating event constraints, refer to `steelmaking/event_code_constraints.md` for the authoritative sequence rules.
  - KPI stats tests: see `tests/kpi_stats/test_kpi_generator.py` for value generation tests and `tests/kpi_stats/test_kpi_engine.py` for engine tests.
  - Run tests with `poetry run pytest tests/ -v` to ensure all 100 tests pass before committing changes.
