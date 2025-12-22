CREATE TABLE steelmaking.steelmaking_kpi_stats (
  id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

  heat_no       bigint NOT NULL,           -- 炉次号（确认你系统里就是数字）
  pro_line_cd   text   NOT NULL,            -- 产线，如 G1
  proc_cd       text   NOT NULL,            -- 工序代码 G12/G13/G15/G16
  device_no     text   NOT NULL,            -- 座次号
  kpi_code      text   NOT NULL,            -- 指标编码

  stat_value    numeric(18,6),              -- 指标值
  sample_time   timestamptz NOT NULL,       -- 取样时间（latest 依据）

  extra         jsonb,

  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_kpi_stats_latest
ON steelmaking.steelmaking_kpi_stats
(
  heat_no,
  proc_cd,
  device_no,
  kpi_code,
  sample_time DESC,
  id DESC
);
