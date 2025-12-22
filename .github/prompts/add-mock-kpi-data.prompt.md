---
agent: 'agent'
model: 'Claude Opus 4.5'
tools:
  ['vscode', 'execute', 'read', 'edit', 'search', 'web', 'copilot-container-tools/*', 'chrome-devtools/*', 'postgres-mcp/*', 'agent', 'todo']
description: 'Add mocking data for steelmaking kpi stats.'
---

# Background
- I have added mocked data for steelmaking kpi definitions using sql file `steelmaking/seed_steelmaking_kpi_def.sql`.
- There is a new table called `steelmaking_kpi_stats` that is intended to store the KPI statistics for steelmaking process. The schema is defined in `steelmaking/steelmaking_kpi_stats.sql`.
  - heat_no: 炉次号
  - pro_line_cd: 生产线代码, Should be G1 -> 炼钢
  - proc_cd: 工序代码, Should be BOF -> G12, LF -> G13, RH -> G15, CCM -> G16
  - device_no: 设备座次号
  - kpi_code: KPI代码, This code comes from the steelmaking_kpi_def table. Represents which KPI this statistic is for.
  - kpi_value: KPI值, The actual value of the KPI. Should be meaningful and match the real world situations.
  - sample_time: 采样时间, Timestamp of when the KPI was sampled.
  - created_at: 创建时间, Timestamp of when the record was created. Triggered automatically.
  - updated_at: 更新时间, Timestamp of when the record was last updated. Triggered automatically
- The table `steelmaking_kpi_stats` is expected to be inserted with data during the simulation of steelmaking operations.
- The simulator currently does not generate any KPI statistics data.

# Requirements
- During the steelmaking process, each operation (BOF, LF, RH, CCM) should have real time KPI statistics generated for it.
- Each operation have multiple KPIs associated with it, as defined in the `steelmaking_kpi_def` table. Fetch related KPI definitions from the table based on the `proc_cd` of the operation.
- For each generated KPI statistic:
  - The `heat_no`, `pro_line_cd`, `proc_cd`, and `device_no` should match those of the associated operation.
  - The `kpi_code` should be one of the KPI codes associated with the operation's `proc_cd`.
  - The `kpi_value` should be a realistic value based on the KPI definition (considering int_digits, decimal_digits, upper_limit, lower_limit). The value can exceed the limits occasionally to simulate real world scenarios.
  - The `sample_time` should be the current simulation time when the statistic is generated.
- All KPI defs should have corresponding stats generated during the operation.

# What you need to do
- Add new feature to the steelmaking simulator to generate and insert KPI statistics data into the `steelmaking_kpi_stats` table not only during the initialization (for completed operations) but also during the tick loop (for active operations).
- Ensure the generated data is realistic and follows the requirements outlined above.
- Create separate functions or modules as necessary to keep the code organized and maintainable.
- Do not change existing functionality of the simulator.
- Add unit tests to verify the correctness of the generated KPI statistics data.
- Make sure all current tests pass after your changes.
- Make the module as configurable as possible.

# Debug Tools
- You can use postgres-mcp mcp tool to access the table steelmaking.steelmaking_kpi_def and steelmaking.steelmaking_kpi_stats.
  