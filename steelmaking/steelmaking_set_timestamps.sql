CREATE OR REPLACE FUNCTION base.set_timestamps()
RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    NEW.created_at := now();
    NEW.updated_at := now();
  ELSIF TG_OP = 'UPDATE' THEN
    NEW.updated_at := now();
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 检测字段差异
CREATE OR REPLACE FUNCTION base.set_updated_at_if_changed()
RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'UPDATE' THEN
    IF row(NEW.*) IS DISTINCT FROM row(OLD.*) THEN
      NEW.updated_at := now();
    END IF;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 为所有包含 created_at 和 updated_at 字段的表添加触发器
CREATE TRIGGER trg_stlmk_event_timestamps
BEFORE INSERT OR UPDATE
ON steelmaking.steelmaking_event
FOR EACH ROW
EXECUTE FUNCTION steelmaking.set_timestamps();

CREATE TRIGGER trg_stlmk_operation_timestamps
BEFORE INSERT OR UPDATE
ON steelmaking.steelmaking_operation
FOR EACH ROW
EXECUTE FUNCTION steelmaking.set_timestamps();

CREATE TRIGGER trg_stlmk_warning_timestamps
BEFORE INSERT OR UPDATE
ON steelmaking.steelmaking_warning
FOR EACH ROW
EXECUTE FUNCTION steelmaking.set_timestamps();

CREATE TRIGGER trg_stlmk_kpi_def_set_timestamps
BEFORE INSERT OR UPDATE
ON steelmaking.steelmaking_kpi_def
FOR EACH ROW
EXECUTE FUNCTION steelmaking.set_timestamps();

CREATE TRIGGER trg_stlmk_kpi_stats_set_timestamps
BEFORE INSERT OR UPDATE
ON steelmaking.steelmaking_kpi_stats
FOR EACH ROW
EXECUTE FUNCTION steelmaking.set_timestamps();