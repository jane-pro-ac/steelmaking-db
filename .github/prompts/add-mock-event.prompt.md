---
agent: 'agent'
model: 'Claude Opus 4.5 (Preview)'
tools:
  ['runCommands', 'runTasks', 'edit', 'runNotebooks', 'search', 'new', 'chrome-devtools/*', 'postgres-mcp/*', 'extensions', 'usages', 'vscodeAPI', 'problems', 'changes', 'testFailure', 'openSimpleBrowser', 'fetch', 'githubRepo', 'todos', 'runSubagent']
description: 'Add mocking data for steelmaking event.'
---

For now, the simulation only seeds data into the `steelmaking_operation` and `steelmaking_warning` tables. Now you need to extend the simulation to also seed data into the `steelmaking_event` table.

# Base Information
- `steelmaking_event` table: steelmaking/steelmaking_event.sql
- `event_code` info: steelmaking/event_code.txt
  - Containing all valid event codes, their parameters and belonged 产线和工序代码.
  - BOF -> G12
  - LF -> G13
  - RH -> G15
  - CCM -> G16
- `event_code_constraints` info: steelmaking/event_code_constraints.md
  - Containing the constraints and allowed sequences among event codes.

# Requirements
- Now the simulation seeds warning during each steelmaking operation. Now you need to also seed events during each steelmaking operation.
  - This means the `event_time_start` of generated events must be within the operation's `real_start_time` and `real_end_time`.
  - Only when the operation is active, it can generate events.
- Each operation must strictly follow the event code constraints and allowed sequences defined in `steelmaking/event_code_constraints.md`.
- Try to make the operation start by event driven, i.e. the first event should be the starting event defined in the constraints, and the last event should be the ending event defined in the constraints.
- Event:
  - `heat_no`: 炉次号
  - `pro_line_cd`: 产线代码 (from the operation)
  - `proc_cd`: 工序代码 (from the operation)
  - `device_no`: 设备座次号 (from the operation)
  - `event_code`: 事件代码 (from the corresponding and constrained event codes)
  - `event_msg`: 事件描述 (Always in Chinese. You need to come up with some realistic event messages that could occur during steelmaking operations. Using the 过程参数1	, 过程参数2, 过程参数3, 过程参数4 from steelmaking/event_code.txt to help generate the messages. For example, G12017 加废钢 has 过程参数1 as 物料名称, 过程参数2 as 料篮号, 过程参数3 as 废钢重量, so the message can be `执行加废钢操作，物料名称[重废]，料篮号[LB-03]，废钢重量[12.5 吨]`)
  - `event_time_start`: 事件开始时间 (must be within the operation's real start and end time)
  - `event_time_end`: 事件结束时间 (For now, set it to be the same as event_time_start)
- The whole event sequence for each operation must be valid according to the constraints. And try to make it configurable and extensible for future changes in the constraints.
- Make sure the code is clean, well structured and easy to maintain.
- Write thoughtful unit tests to verify the correctness of the event generation logic.
- Update the AGENTS.md.

# Debug Tools
- You can use postgres-mcp mcp tool to access the table steelmaking.steelmaking_event.