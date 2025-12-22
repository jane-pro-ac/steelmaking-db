---
agent: 'agent'
model: 'Claude Opus 4.5'
tools:
  ['vscode', 'execute', 'read', 'edit', 'search', 'web', 'copilot-container-tools/*', 'chrome-devtools/*', 'postgres-mcp/*', 'agent', 'todo']
description: 'Add mocking data for steelmaking kpi def.'
---

# Background
- I have added a new table `steelmaking_kpi_def` to store the KPI definitions for steelmaking process. The schema is defined in `steelmaking/steelmaking_kpi_def.sql`.
  - proc_cd: 工序代码, Already defined in the simulator and should be BOF -> G12, LF -> G13, RH -> G15, CCM -> G16
  - kpi_code: KPI代码, A unique code for each KPI within a process.
  - kpi_name: KPI名称, The name of the KPI. In Chinese.
  - description: 描述, A brief description of the KPI. In Chinese.
  - unit: 单位, The unit of measurement for the KPI. Optional.
  - decription: 描述, A brief description of the KPI. In Chinese.
  - int_digits: 整数位数, The number of digits before the decimal point. Should be meaningful and match the real world situations.
  - decimal_digits: 小数位数, The number of digits after the decimal point. Should be meaningful and match the real world situations.
  - upper_limit: 上限, The upper limit for the KPI value. Optional. Should be meaningful and match the real world situations.
  - lower_limit: 下限, The lower limit for the KPI value. Optional. Should be meaningful and match the real world situations.
  - display_enabled: 是否显示, A boolean indicating whether this KPI should be displayed in the dashboard. Default to true.
  - show_in_config: 是否在配置界面中显示, A boolean indicating whether this KPI should be shown in the configuration interface. Default to true.
  - display_order: 显示顺序, An integer indicating the order in which this KPI should be displayed. Lower numbers are displayed first.
  - extra: 额外信息, A JSONB field to store any additional information about the KPI. Optional.
  - created_at: 创建时间, Timestamp of when the record was created. Triggered automatically.
  - updated_at: 更新时间, Timestamp of when the record was last updated. Triggered automatically 
- I have a json file `steelmaking/kpi_code.json` that contains a list of KPI definitions for each process. Each entry in the json file has the following structure: - kpi_code: KPI代码 - name_cn: KPI名称 - unit: 单位 - desc_cn: 描述
  - Some KPIs should have upper_limit and lower_limit, but not defined in the json file. You need to come up with meaningful limits based on real world situations.

# Tasks
- Generate a sql script to insert the KPI definitions from the json file into the `steelmaking_kpi_def` table.
- Make sure the definitions are meaningful and realistic.

# Debug Tools
- You can use postgres-mcp mcp tool to access the table steelmaking.steelmaking_kpi_def.