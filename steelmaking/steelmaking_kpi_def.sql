CREATE TABLE steelmaking.steelmaking_kpi_def (
  id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  proc_cd         text NOT NULL,
  kpi_code        text NOT NULL,
  kpi_name        text NOT NULL,
  unit            text,
  description     text,

  int_digits      smallint NOT NULL DEFAULT 6 CHECK (int_digits BETWEEN 0 AND 18),
  decimal_digits  smallint NOT NULL DEFAULT 2 CHECK (decimal_digits BETWEEN 0 AND 6),

  upper_limit     numeric(18,6),
  lower_limit     numeric(18,6),

  display_enabled boolean NOT NULL DEFAULT true,
  show_in_config  boolean NOT NULL DEFAULT true,

  display_order   int NOT NULL DEFAULT 1000, -- 建议加
  extra           jsonb,

  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),

  UNIQUE (proc_cd, kpi_code)
);

CREATE INDEX idx_kpi_def_proc_enabled
  ON steelmaking.steelmaking_kpi_def(proc_cd, display_order)
  WHERE display_enabled;

CREATE INDEX idx_kpi_def_proc_config
  ON steelmaking.steelmaking_kpi_def(proc_cd, display_order)
  WHERE show_in_config;
