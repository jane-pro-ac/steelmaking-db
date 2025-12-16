# Steelmaking Simulation – Agent Guide

- **Purpose**: Continuously simulate steelmaking operations for demo/testing environments. It seeds and drives data in `steelmaking.steelmaking_operation` (and truncates `steelmaking_warning`) to mimic BOF → LF → CCM flows with realistic timing and crew assignments.

- **Project layout**:
  - `steelmaking_simulation/config.py`: Environment-configurable settings, equipment lists, process flow, and `CREW_CODES`.
  - `steelmaking_simulation/database.py`: Thin Postgres access layer; handles inserts/updates/queries plus demo truncation of operation/warning tables.
  - `steelmaking_simulation/simulator.py`: Orchestration layer wiring seeding, warnings, runtime processing, and heat creation.
  - `steelmaking_simulation/seeding.py`: Initialization seeding of operations + historical warnings (enforces all timing constraints).
  - `steelmaking_simulation/warning_engine.py`: Warning generation (historical seeding + real-time tick emissions + throttling).
  - `steelmaking_simulation/operation_processor.py`: Runtime progression (complete active ops, start pending ops when ready, **does not mutate** `plan_start_time/plan_end_time`).
  - `steelmaking_simulation/heat_planner.py`: New heat creation (BOF starts now; LF/CCM planned within transfer window; aligned routing bias).
  - `steelmaking_simulation/scheduler.py`: Slot finder enforcing non-overlap and rest bounds (upper rest bound is planning-only; runtime enforces minimum rest only).
  - `steelmaking_simulation/time_utils.py`: Shared time constants (e.g., CST).
  - `steelmaking_simulation/main.py`: CLI entrypoint; wires config/logging and starts the simulator.
  - Root docs: `README.md` (how to run) and `example_steelmaking_operation.md` (schema example).

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
    - Demo seeding: `DEMO_SEED_*` knobs primarily shape the seeded time horizon/density around “now”.

- **Data model expectations**:
  - `steelmaking.steelmaking_operation` columns used: `heat_no`, `pro_line_cd`, `proc_cd`, `device_no`, `crew_cd`, `stl_grd_id`, `stl_grd_cd`, `proc_status`, `plan_start_time`, `plan_end_time`, `real_start_time`, `real_end_time`, `extra`. `crew_cd` must be one of `CREW_CODES` (A/B/C/D); `stl_grd_id` references `base.steel_grade.id`.
  - `steelmaking.steelmaking_warning` is populated during seeding and ticks (truncated on startup together with operations); `heat_no` is BIGINT to mirror the operation table; schema uses `warning_time_start` and `warning_time_end`. Warning messages are generated in中文.
  - Heat number format: `YYMMNNNNN` where the last 5 digits auto-increment per month.

- **Simulation behavior**:
  - Seeding: On startup, truncates warnings/operations, then seeds a **continuous timeline of heats around “now”**. Each operation’s status is derived from its planned window relative to “now”:
    - `COMPLETED`: `plan_end_time <= now` and `real_start_time/real_end_time` are set (both before now)
    - `ACTIVE`: `plan_start_time <= now < plan_end_time`, `real_start_time` is set, and `real_end_time` is NULL
    - `PENDING`: `plan_start_time > now` and real times are NULL
    This ensures initialization always contains in-progress operations while keeping completed rows strictly in the past.
  - Tick loop: Processes active ops (may complete them), starts pending ops once predecessors and device availability allow, and may create a new heat per tick with probability `NEW_HEAT_PROBABILITY`. Active ops may emit real-time-ish 中文 warnings anchored to the current tick time.
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
    - Runtime: Warnings are generated **near real-time** during ticks (anchored to “now”), and inserted in time order (not backfilled at random times within the historical plan window).
    - Max **N warnings per operation** (`MAX_WARNINGS_PER_OPERATION`, default 5) and throttled to keep them reasonably dispersed across the operation runtime.
    - Duration distribution: almost always short (<10s), occasionally up to 1 minute, rarely longer; codes/messages are chosen from process-specific templates (plus common fallbacks).

- **Development tips**:
  - Keep schema alignment tight; update `database.py`, `simulator.py`, and docs whenever table columns change.
  - Prefer adding new configuration flags to `.env`-driven dataclasses in `config.py`.
  - Logging is configured in `main.py`; adjust there for verbosity.
  - Avoid destructive DB commands beyond the intentional truncate in `DatabaseManager.clear_operations()`.
  - If you add warning generation, reuse `DatabaseManager.cursor()` for transactional safety and ensure both `warning_time_start` and `warning_time_end` are written.
  - Unit checks: see `tests/test_simulator_constraints.py` for constraint coverage (no-overlap, device rest bounds, transfer gaps 20–30, active semantics, aligned routing preference, heat number generation behavior, real-time warning ordering/max, warning duration distribution).

- **Maintenance checks**:
  - Sanity-test connection with `psql`/`poetry run python -c "from steelmaking_simulation import DatabaseConfig, DatabaseManager; DatabaseManager(DatabaseConfig()).connect()"`.
  - When changing process flow or equipment, update `PROCESS_FLOW`, `EQUIPMENT`, and any downstream logic that assumes BOF → LF → CCM order.
  - Validate generated timestamps stay within configured duration/gap bounds and honor sequential process rules before shipping changes.
