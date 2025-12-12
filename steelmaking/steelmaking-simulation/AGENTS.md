# Steelmaking Simulation – Agent Guide

- **Purpose**: Continuously simulate steelmaking operations for demo/testing environments. It seeds and drives data in `steelmaking.steelmaking_operation` (and truncates `steelmaking_warning`) to mimic BOF → LF → CCM flows with realistic timing and crew assignments.

- **Project layout**:
  - `steelmaking_simulation/config.py`: Environment-configurable settings, equipment lists, process flow, and `CREW_CODES`.
  - `steelmaking_simulation/database.py`: Thin Postgres access layer; handles inserts/updates/queries plus demo truncation of operation/warning tables.
  - `steelmaking_simulation/simulator.py`: Core simulation loop, seeding past/future data, ticking through active/pending operations, and creating new heats.
  - `steelmaking_simulation/main.py`: CLI entrypoint; wires config/logging and starts the simulator.
  - Root docs: `README.md` (how to run) and `example_steelmaking_operation.md` (schema example).

- **Setup & run**:
  - Requirements: Python 3.10+, Poetry, reachable Postgres.
  - Install deps: `poetry install`.
  - Configure environment (copy `.env.example` → `.env` if present): `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, plus optional `SIMULATION_INTERVAL`, `NEW_HEAT_PROBABILITY`, `DEMO_SEED_PAST_HEATS`, `DEMO_SEED_FUTURE_HEATS`.
  - Start simulator: `poetry run simulate` (or `poetry shell` then `python -m steelmaking_simulation.main`).

- **Data model expectations**:
  - `steelmaking.steelmaking_operation` columns used: `heat_no`, `pro_line_cd`, `proc_cd`, `device_no`, `crew_cd`, `stl_grd_id`, `stl_grd_cd`, `proc_status`, `plan_start_time`, `plan_end_time`, `real_start_time`, `real_end_time`, `extra`. `crew_cd` must be one of `CREW_CODES` (A/B/C/D); `stl_grd_id` references `base.steel_grade.id`.
  - `steelmaking.steelmaking_warning` is populated during seeding and ticks (truncated on startup together with operations); `heat_no` is BIGINT to mirror the operation table; schema uses `warning_time_start` and `warning_time_end`. Warning messages are generated in中文.
  - Heat number format: `YYMMNNNNN` where the last 5 digits auto-increment per month.

- **Simulation behavior**:
  - Seeding: On startup, truncates warnings/operations, seeds completed flows within the last 12 hours and planned flows within the next 12 hours. Each heat uses one random crew and steel grade; completed operations may get 1–5 warnings within their real start/end times.
  - Tick loop: Processes active ops (may complete them), starts pending ops once predecessors and device availability allow, and may create a new heat per tick with probability `NEW_HEAT_PROBABILITY`. Active ops may emit random中文warnings between their real start time and “now”.
  - Timing: Durations randomized between 10–30 minutes; gaps between operations 1–10 minutes; respects device availability per `EQUIPMENT` definitions.

- **Development tips**:
  - Keep schema alignment tight; update `database.py`, `simulator.py`, and docs whenever table columns change.
  - Prefer adding new configuration flags to `.env`-driven dataclasses in `config.py`.
  - Logging is configured in `main.py`; adjust there for verbosity.
  - Avoid destructive DB commands beyond the intentional truncate in `DatabaseManager.clear_operations()`.
  - If you add warning generation, reuse `DatabaseManager.cursor()` for transactional safety and ensure both `warning_time_start` and `warning_time_end` are written.

- **Maintenance checks**:
  - Sanity-test connection with `psql`/`poetry run python -c "from steelmaking_simulation import DatabaseConfig, DatabaseManager; DatabaseManager(DatabaseConfig()).connect()"`.
  - When changing process flow or equipment, update `PROCESS_FLOW`, `EQUIPMENT`, and any downstream logic that assumes BOF → LF → CCM order.
  - Validate generated timestamps stay within configured duration/gap bounds and honor sequential process rules before shipping changes.
