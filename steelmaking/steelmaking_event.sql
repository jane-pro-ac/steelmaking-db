CREATE TABLE steelmaking.steelmaking_event (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    heat_no       BIGINT NOT NULL,
    pro_line_cd   TEXT NOT NULL,
    proc_cd       TEXT NOT NULL,
    device_no     TEXT NOT NULL,

    event_code  TEXT NOT NULL,
    event_name  TEXT NOT NULL,
    event_msg   TEXT NOT NULL,
    event_time_start  TIMESTAMPTZ NOT NULL,
    event_time_end       TIMESTAMPTZ NOT NULL,

    extra         JSONB,

    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_stlmk_event_heat_device
    ON steelmaking.steelmaking_event (heat_no, device_no);