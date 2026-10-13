-- Catalog version triggers. The migration creates the table first.
-- Bookkeeping columns do not bump a version. Review fields do.

CREATE OR REPLACE FUNCTION catalog_entity_type(table_name text)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT CASE table_name
        WHEN 'organizations' THEN 'organization'
        WHEN 'locations' THEN 'location'
        WHEN 'activities' THEN 'activity'
        WHEN 'activity_pricing' THEN 'pricing'
        WHEN 'activity_schedule' THEN 'schedule'
        ELSE table_name
    END
$$;

CREATE OR REPLACE FUNCTION catalog_tracked(data jsonb)
RETURNS jsonb
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT COALESCE(data, '{}'::jsonb) - ARRAY[
        'updated_at',
        'version',
        'media_version',
        'name_key',
        'last_imported_at',
        'import_job_id',
        'status_changed_at',
        'created_at'
    ]
$$;

CREATE OR REPLACE FUNCTION catalog_changed_fields(old_data jsonb, new_data jsonb)
RETURNS text[]
LANGUAGE plpgsql
AS $$
DECLARE
    key text;
    leftj jsonb := catalog_tracked(old_data);
    rightj jsonb := catalog_tracked(new_data);
    changed text[] := ARRAY[]::text[];
BEGIN
    FOR key IN
        SELECT jsonb_object_keys(leftj)
        UNION
        SELECT jsonb_object_keys(rightj)
    LOOP
        IF (leftj -> key) IS DISTINCT FROM (rightj -> key) THEN
            changed := array_append(changed, key);
        END IF;
    END LOOP;
    RETURN changed;
END;
$$;

CREATE OR REPLACE FUNCTION catalog_audit_differs(previous jsonb, current jsonb)
RETURNS boolean
LANGUAGE plpgsql
AS $$
DECLARE
    key text;
    leftj jsonb := catalog_tracked(COALESCE(previous, '{}'::jsonb));
    rightj jsonb := catalog_tracked(COALESCE(current, '{}'::jsonb));
    value jsonb;
BEGIN
    IF previous IS NULL THEN
        RETURN false;
    END IF;
    FOR key IN
        SELECT jsonb_object_keys(leftj)
        INTERSECT
        SELECT jsonb_object_keys(rightj)
    LOOP
        IF (leftj -> key) IS DISTINCT FROM (rightj -> key) THEN
            RETURN true;
        END IF;
    END LOOP;
    FOR key IN SELECT jsonb_object_keys(rightj)
    LOOP
        IF leftj ? key THEN
            CONTINUE;
        END IF;
        value := rightj -> key;
        IF value IS NULL OR value = 'null'::jsonb THEN
            CONTINUE;
        END IF;
        IF jsonb_typeof(value) = 'string' AND btrim(value #>> '{}') = '' THEN
            CONTINUE;
        END IF;
        IF jsonb_typeof(value) = 'array' AND jsonb_array_length(value) = 0 THEN
            CONTINUE;
        END IF;
        IF jsonb_typeof(value) = 'object' AND value = '{}'::jsonb THEN
            CONTINUE;
        END IF;
        RETURN true;
    END LOOP;
    RETURN false;
END;
$$;

CREATE OR REPLACE FUNCTION catalog_enrich_snapshot(table_name text, data jsonb)
RETURNS jsonb
LANGUAGE plpgsql
AS $$
DECLARE
    snap jsonb := catalog_tracked(data);
    row_id uuid;
    addr text;
    locs jsonb;
    slots jsonb;
BEGIN
    IF data IS NULL THEN
        RETURN '{}'::jsonb;
    END IF;
    BEGIN
        row_id := (data ->> 'id')::uuid;
    EXCEPTION WHEN others THEN
        row_id := NULL;
    END;
    IF table_name = 'activities' AND row_id IS NOT NULL THEN
        SELECT COALESCE(jsonb_agg(location_id ORDER BY location_id), '[]'::jsonb)
        INTO locs
        FROM activity_locations
        WHERE activity_id = row_id;
        snap := snap || jsonb_build_object('location_ids', COALESCE(locs, '[]'::jsonb));
    END IF;
    IF table_name = 'activity_schedule' AND row_id IS NOT NULL THEN
        SELECT COALESCE(
            jsonb_agg(
                jsonb_build_object(
                    'day_of_week_utc', day_of_week_utc,
                    'start_minutes_utc', start_minutes_utc,
                    'end_minutes_utc', end_minutes_utc
                )
                ORDER BY day_of_week_utc, start_minutes_utc, end_minutes_utc
            ),
            '[]'::jsonb
        )
        INTO slots
        FROM activity_schedule_entries
        WHERE schedule_id = row_id;
        snap := snap || jsonb_build_object('entries', COALESCE(slots, '[]'::jsonb));
    END IF;
    IF table_name IN ('activity_pricing', 'activity_schedule')
        AND data ? 'location_id' THEN
        BEGIN
            SELECT address INTO addr
            FROM locations
            WHERE id = (data ->> 'location_id')::uuid;
        EXCEPTION WHEN others THEN
            addr := NULL;
        END;
        snap := snap || jsonb_build_object('location_address', addr);
    END IF;
    RETURN snap;
END;
$$;

CREATE OR REPLACE FUNCTION catalog_import_job_id()
RETURNS uuid
LANGUAGE plpgsql
AS $$
DECLARE
    raw text;
BEGIN
    raw := NULLIF(current_setting('app.current_import_job_id', true), '');
    IF raw IS NULL THEN
        RETURN NULL;
    END IF;
    RETURN raw::uuid;
EXCEPTION WHEN others THEN
    RETURN NULL;
END;
$$;

CREATE OR REPLACE FUNCTION catalog_version_reason()
RETURNS text
LANGUAGE plpgsql
AS $$
DECLARE
    raw text;
BEGIN
    raw := NULLIF(current_setting('app.catalog_version_reason', true), '');
    PERFORM set_config('app.catalog_version_reason', '', true);
    RETURN raw;
END;
$$;

CREATE OR REPLACE FUNCTION catalog_org_id(table_name text, data jsonb)
RETURNS uuid
LANGUAGE plpgsql
AS $$
DECLARE
    org uuid;
BEGIN
    IF data IS NULL THEN
        RETURN NULL;
    END IF;
    IF table_name = 'organizations' THEN
        RETURN (data ->> 'id')::uuid;
    END IF;
    IF data ? 'org_id' AND NULLIF(data ->> 'org_id', '') IS NOT NULL THEN
        RETURN (data ->> 'org_id')::uuid;
    END IF;
    IF data ? 'activity_id' THEN
        SELECT activities.org_id INTO org
        FROM activities
        WHERE activities.id = (data ->> 'activity_id')::uuid;
        RETURN org;
    END IF;
    IF table_name = 'activity_schedule_entries' AND data ? 'schedule_id' THEN
        SELECT activities.org_id INTO org
        FROM activity_schedule
        JOIN activities ON activities.id = activity_schedule.activity_id
        WHERE activity_schedule.id = (data ->> 'schedule_id')::uuid;
        RETURN org;
    END IF;
    RETURN NULL;
EXCEPTION WHEN others THEN
    RETURN NULL;
END;
$$;

CREATE OR REPLACE FUNCTION catalog_upsert_version(
    etype text,
    eid uuid,
    org uuid,
    ver integer,
    act text,
    snap jsonb,
    changed text[],
    why text
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
    existing_txid bigint;
BEGIN
    SELECT txid INTO existing_txid
    FROM catalog_versions
    WHERE entity_type = etype
      AND entity_id = eid
      AND version = ver;
    IF existing_txid IS NOT NULL AND existing_txid <> txid_current() THEN
        RAISE EXCEPTION 'catalog version % of % is immutable', ver, etype
            USING ERRCODE = 'check_violation';
    END IF;
    INSERT INTO catalog_versions (
        entity_type,
        entity_id,
        org_id,
        version,
        action,
        snapshot,
        changed_fields,
        txid,
        user_id,
        request_id,
        import_job_id,
        reason
    ) VALUES (
        etype,
        eid,
        org,
        ver,
        act,
        snap,
        changed,
        txid_current(),
        NULLIF(current_setting('app.current_user_id', true), ''),
        NULLIF(current_setting('app.current_request_id', true), ''),
        catalog_import_job_id(),
        why
    )
    ON CONFLICT (entity_type, entity_id, version) DO UPDATE SET
        snapshot = EXCLUDED.snapshot,
        changed_fields = (
            SELECT ARRAY(
                SELECT DISTINCT unnest(
                    COALESCE(catalog_versions.changed_fields, '{}'::text[])
                    || COALESCE(EXCLUDED.changed_fields, '{}'::text[])
                )
            )
        ),
        action = CASE
            WHEN catalog_versions.action = 'deleted' THEN catalog_versions.action
            ELSE EXCLUDED.action
        END,
        txid = EXCLUDED.txid,
        user_id = COALESCE(EXCLUDED.user_id, catalog_versions.user_id),
        request_id = COALESCE(EXCLUDED.request_id, catalog_versions.request_id),
        import_job_id = COALESCE(EXCLUDED.import_job_id, catalog_versions.import_job_id),
        reason = COALESCE(EXCLUDED.reason, catalog_versions.reason);
END;
$$;

CREATE OR REPLACE FUNCTION catalog_rewrite_open_snapshot(etable text, eid uuid)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
    data jsonb;
    etype text;
BEGIN
    EXECUTE format('SELECT to_jsonb(t) FROM %I t WHERE id = $1', etable)
    INTO data
    USING eid;
    IF data IS NULL THEN
        RETURN;
    END IF;
    etype := catalog_entity_type(etable);
    UPDATE catalog_versions
    SET snapshot = catalog_enrich_snapshot(etable, data)
    WHERE entity_type = etype
      AND entity_id = eid
      AND txid = txid_current();
END;
$$;

CREATE OR REPLACE FUNCTION catalog_note_child(parent_table text, parent_id uuid)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
    etype text;
    existing_action text;
BEGIN
    IF parent_id IS NULL THEN
        RETURN;
    END IF;
    etype := catalog_entity_type(parent_table);
    SELECT action INTO existing_action
    FROM catalog_versions
    WHERE entity_type = etype
      AND entity_id = parent_id
      AND txid = txid_current()
    ORDER BY version DESC
    LIMIT 1;
    -- The organization row does not embed its children, so rewriting
    -- that snapshot once per child only locks history. Activities and
    -- schedules do embed joins and entries, including after the parent
    -- was already edited in this transaction.
    IF existing_action IS NOT NULL THEN
        IF parent_table IN ('activities', 'activity_schedule') THEN
            PERFORM catalog_rewrite_open_snapshot(parent_table, parent_id);
        END IF;
        RETURN;
    END IF;
    PERFORM set_config('app.catalog_version_reason', 'children', true);
    EXECUTE format(
        'UPDATE %I SET version = version + 1 WHERE id = $1',
        parent_table
    )
    USING parent_id;
END;
$$;

CREATE OR REPLACE FUNCTION catalog_version_bump()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    tracked_changed boolean;
    already boolean;
    media_changed boolean;
    media_already boolean;
BEGIN
    IF current_setting('app.catalog_backfill', true) = 'on' THEN
        RETURN NEW;
    END IF;
    tracked_changed := catalog_tracked(to_jsonb(OLD))
        IS DISTINCT FROM catalog_tracked(to_jsonb(NEW));
    SELECT EXISTS (
        SELECT 1 FROM catalog_versions
        WHERE entity_type = catalog_entity_type(TG_TABLE_NAME)
          AND entity_id = NEW.id
          AND txid = txid_current()
    ) INTO already;
    -- A roll-up sets version itself. That statement must not move
    -- updated_at; only a change to a tracked column does.
    IF tracked_changed AND NOT already AND NEW.version IS NOT DISTINCT FROM OLD.version THEN
        NEW.version := OLD.version + 1;
        IF TG_TABLE_NAME IN ('organizations', 'locations', 'activities') THEN
            NEW.updated_at := now();
        END IF;
    END IF;
    IF TG_TABLE_NAME = 'organizations' THEN
        media_changed := to_jsonb(OLD.media_urls) IS DISTINCT FROM to_jsonb(NEW.media_urls)
            OR to_jsonb(OLD.logo_media_url) IS DISTINCT FROM to_jsonb(NEW.logo_media_url);
        SELECT EXISTS (
            SELECT 1 FROM catalog_versions
            WHERE entity_type = 'media'
              AND entity_id = NEW.id
              AND txid = txid_current()
        ) INTO media_already;
        IF media_changed
            AND NOT media_already
            AND NEW.media_version IS NOT DISTINCT FROM OLD.media_version THEN
            NEW.media_version := OLD.media_version + 1;
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION catalog_version_record()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    data jsonb;
    ver integer;
    act text;
    changed text[];
    why text;
    etype text;
    eid uuid;
    org uuid;
    snap jsonb;
    media_snap jsonb;
BEGIN
    IF current_setting('app.catalog_backfill', true) = 'on' THEN
        RETURN COALESCE(NEW, OLD);
    END IF;
    IF TG_OP = 'DELETE' THEN
        data := to_jsonb(OLD);
        ver := COALESCE(OLD.version, 1) + 1;
        act := 'deleted';
        changed := NULL;
    ELSIF TG_OP = 'INSERT' THEN
        data := to_jsonb(NEW);
        ver := COALESCE(NEW.version, 1);
        act := 'created';
        changed := NULL;
    ELSE
        IF NEW.version IS NOT DISTINCT FROM OLD.version
            AND catalog_tracked(to_jsonb(OLD))
                IS NOT DISTINCT FROM catalog_tracked(to_jsonb(NEW)) THEN
            IF TG_TABLE_NAME <> 'organizations' THEN
                RETURN NEW;
            ELSIF NEW.media_version IS NOT DISTINCT FROM OLD.media_version THEN
                RETURN NEW;
            END IF;
        END IF;
        data := to_jsonb(NEW);
        ver := COALESCE(NEW.version, 1);
        act := 'updated';
        changed := catalog_changed_fields(to_jsonb(OLD), to_jsonb(NEW));
    END IF;
    etype := catalog_entity_type(TG_TABLE_NAME);
    eid := (data ->> 'id')::uuid;
    org := catalog_org_id(TG_TABLE_NAME, data);
    snap := catalog_enrich_snapshot(TG_TABLE_NAME, data);
    why := catalog_version_reason();
    PERFORM catalog_upsert_version(etype, eid, org, ver, act, snap, changed, why);
    IF TG_TABLE_NAME = 'organizations' THEN
        media_snap := jsonb_build_object(
            'media_urls', data -> 'media_urls',
            'logo_media_url', data -> 'logo_media_url'
        );
        IF TG_OP = 'DELETE' THEN
            PERFORM catalog_upsert_version(
                'media', eid, org, COALESCE(OLD.media_version, 1) + 1,
                'deleted', media_snap, NULL, NULL
            );
        ELSIF TG_OP = 'INSERT' OR OLD.media_version IS DISTINCT FROM NEW.media_version THEN
            PERFORM catalog_upsert_version(
                'media', eid, org, COALESCE(NEW.media_version, 1),
                CASE WHEN TG_OP = 'INSERT' THEN 'created' ELSE 'updated' END,
                media_snap,
                CASE
                    WHEN TG_OP = 'INSERT' THEN NULL
                    ELSE ARRAY['media_urls', 'logo_media_url']::text[]
                END,
                NULL
            );
        END IF;
    END IF;
    IF TG_TABLE_NAME IN ('locations', 'activities') THEN
        PERFORM catalog_note_child('organizations', org);
    ELSIF TG_TABLE_NAME IN ('activity_pricing', 'activity_schedule')
        AND data ? 'activity_id' THEN
        PERFORM catalog_note_child('activities', (data ->> 'activity_id')::uuid);
    END IF;
    RETURN COALESCE(NEW, OLD);
END;
$$;

CREATE OR REPLACE FUNCTION catalog_join_touch()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    activity uuid;
BEGIN
    IF current_setting('app.catalog_backfill', true) = 'on' THEN
        RETURN COALESCE(NEW, OLD);
    END IF;
    activity := COALESCE(NEW.activity_id, OLD.activity_id);
    PERFORM catalog_note_child('activities', activity);
    RETURN COALESCE(NEW, OLD);
END;
$$;

CREATE OR REPLACE FUNCTION catalog_entry_touch()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    sid uuid;
BEGIN
    IF current_setting('app.catalog_backfill', true) = 'on' THEN
        RETURN COALESCE(NEW, OLD);
    END IF;
    sid := COALESCE(NEW.schedule_id, OLD.schedule_id);
    PERFORM catalog_note_child('activity_schedule', sid);
    RETURN COALESCE(NEW, OLD);
END;
$$;

CREATE OR REPLACE FUNCTION catalog_contact_keys()
RETURNS text[]
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT ARRAY[
        'phone_country_code',
        'phone_number',
        'email',
        'whatsapp',
        'facebook',
        'instagram',
        'tiktok',
        'twitter',
        'xiaohongshu',
        'wechat'
    ]::text[]
$$;

CREATE OR REPLACE FUNCTION catalog_snapshot_is_contact_redaction(
    previous jsonb,
    next jsonb
)
RETURNS boolean
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT (next - catalog_contact_keys())
            IS NOT DISTINCT FROM (previous - catalog_contact_keys())
        AND NOT EXISTS (
            SELECT 1
            FROM unnest(catalog_contact_keys()) AS key
            WHERE next ? key
              AND next -> key IS DISTINCT FROM 'null'::jsonb
        )
$$;

CREATE OR REPLACE FUNCTION catalog_versions_guard()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.txid = txid_current() THEN
        RETURN NEW;
    END IF;
    IF NEW.entity_type IS DISTINCT FROM OLD.entity_type
        OR NEW.entity_id IS DISTINCT FROM OLD.entity_id
        OR NEW.org_id IS DISTINCT FROM OLD.org_id
        OR NEW.version IS DISTINCT FROM OLD.version
        OR NEW.action IS DISTINCT FROM OLD.action
        OR NEW.changed_fields IS DISTINCT FROM OLD.changed_fields
        OR NEW.txid IS DISTINCT FROM OLD.txid
        OR NEW.user_id IS DISTINCT FROM OLD.user_id
        OR NEW.request_id IS DISTINCT FROM OLD.request_id
        OR NEW.import_job_id IS DISTINCT FROM OLD.import_job_id
        OR NEW.created_at IS DISTINCT FROM OLD.created_at
    THEN
        RAISE EXCEPTION 'catalog version % is immutable', OLD.version
            USING ERRCODE = 'check_violation';
    END IF;
    IF OLD.reason = 'merged' AND NEW.reason IS DISTINCT FROM OLD.reason THEN
        RAISE EXCEPTION 'merged catalog version is immutable'
            USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.reason IS DISTINCT FROM OLD.reason
        AND NEW.reason IS NOT NULL
        AND NEW.reason NOT IN ('forgotten', 'merged', 'children')
    THEN
        RAISE EXCEPTION 'catalog version reason cannot be changed'
            USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.reason = 'forgotten'
        AND OLD.reason IS DISTINCT FROM 'forgotten'
        AND EXISTS (
            SELECT 1
            FROM catalog_versions
            WHERE entity_type = NEW.entity_type
              AND entity_id = NEW.entity_id
              AND reason = 'merged'
        )
    THEN
        RAISE EXCEPTION 'merged catalog version cannot be forgotten'
            USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.snapshot IS DISTINCT FROM OLD.snapshot
        AND NOT catalog_snapshot_is_contact_redaction(OLD.snapshot, NEW.snapshot)
    THEN
        RAISE EXCEPTION 'catalog version snapshot is immutable'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION catalog_versions_delete_guard()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.txid = txid_current() THEN
        RETURN OLD;
    END IF;
    RAISE EXCEPTION 'catalog version % is immutable', OLD.version
        USING ERRCODE = 'check_violation';
END;
$$;

-- Forget hides version 1 from import and strips contact fields.
-- A merged organization keeps its history.
CREATE OR REPLACE FUNCTION catalog_forget_entity(etype text, eid uuid)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
BEGIN
    UPDATE catalog_versions AS row
    SET reason = 'forgotten',
        snapshot = row.snapshot - catalog_contact_keys()
    WHERE row.version = 1
      AND row.reason IS DISTINCT FROM 'merged'
      AND NOT EXISTS (
          SELECT 1
          FROM catalog_versions AS other
          WHERE other.entity_type = row.entity_type
            AND other.entity_id = row.entity_id
            AND other.reason = 'merged'
      )
      AND (
          (row.entity_type = etype AND row.entity_id = eid)
          OR (etype = 'organization' AND row.org_id = eid)
      );
    UPDATE catalog_versions AS row
    SET snapshot = row.snapshot - catalog_contact_keys()
    WHERE (row.entity_type = etype AND row.entity_id = eid)
       OR (etype = 'organization' AND row.org_id = eid);
END;
$$;

DROP TRIGGER IF EXISTS catalog_versions_guard ON catalog_versions;
DROP TRIGGER IF EXISTS catalog_versions_delete_guard ON catalog_versions;
CREATE TRIGGER catalog_versions_guard
BEFORE UPDATE ON catalog_versions
FOR EACH ROW EXECUTE FUNCTION catalog_versions_guard();
CREATE TRIGGER catalog_versions_delete_guard
BEFORE DELETE ON catalog_versions
FOR EACH ROW EXECUTE FUNCTION catalog_versions_delete_guard();

DROP TRIGGER IF EXISTS organizations_version_bump ON organizations;
DROP TRIGGER IF EXISTS organizations_version_record ON organizations;
DROP TRIGGER IF EXISTS locations_version_bump ON locations;
DROP TRIGGER IF EXISTS locations_version_record ON locations;
DROP TRIGGER IF EXISTS activities_version_bump ON activities;
DROP TRIGGER IF EXISTS activities_version_record ON activities;
DROP TRIGGER IF EXISTS activity_pricing_version_bump ON activity_pricing;
DROP TRIGGER IF EXISTS activity_pricing_version_record ON activity_pricing;
DROP TRIGGER IF EXISTS activity_schedule_version_bump ON activity_schedule;
DROP TRIGGER IF EXISTS activity_schedule_version_record ON activity_schedule;
DROP TRIGGER IF EXISTS activity_locations_version_touch ON activity_locations;
DROP TRIGGER IF EXISTS activity_schedule_entries_version_touch ON activity_schedule_entries;

CREATE TRIGGER organizations_version_bump
BEFORE UPDATE ON organizations
FOR EACH ROW EXECUTE FUNCTION catalog_version_bump();
CREATE TRIGGER organizations_version_record
AFTER INSERT OR UPDATE OR DELETE ON organizations
FOR EACH ROW EXECUTE FUNCTION catalog_version_record();

CREATE TRIGGER locations_version_bump
BEFORE UPDATE ON locations
FOR EACH ROW EXECUTE FUNCTION catalog_version_bump();
CREATE TRIGGER locations_version_record
AFTER INSERT OR UPDATE OR DELETE ON locations
FOR EACH ROW EXECUTE FUNCTION catalog_version_record();

CREATE TRIGGER activities_version_bump
BEFORE UPDATE ON activities
FOR EACH ROW EXECUTE FUNCTION catalog_version_bump();
CREATE TRIGGER activities_version_record
AFTER INSERT OR UPDATE OR DELETE ON activities
FOR EACH ROW EXECUTE FUNCTION catalog_version_record();

CREATE TRIGGER activity_pricing_version_bump
BEFORE UPDATE ON activity_pricing
FOR EACH ROW EXECUTE FUNCTION catalog_version_bump();
CREATE TRIGGER activity_pricing_version_record
AFTER INSERT OR UPDATE OR DELETE ON activity_pricing
FOR EACH ROW EXECUTE FUNCTION catalog_version_record();

CREATE TRIGGER activity_schedule_version_bump
BEFORE UPDATE ON activity_schedule
FOR EACH ROW EXECUTE FUNCTION catalog_version_bump();
CREATE TRIGGER activity_schedule_version_record
AFTER INSERT OR UPDATE OR DELETE ON activity_schedule
FOR EACH ROW EXECUTE FUNCTION catalog_version_record();

CREATE TRIGGER activity_locations_version_touch
AFTER INSERT OR DELETE ON activity_locations
FOR EACH ROW EXECUTE FUNCTION catalog_join_touch();

CREATE TRIGGER activity_schedule_entries_version_touch
AFTER INSERT OR UPDATE OR DELETE ON activity_schedule_entries
FOR EACH ROW EXECUTE FUNCTION catalog_entry_touch();

DROP INDEX IF EXISTS catalog_versions_v1_name_idx;
CREATE INDEX catalog_versions_v1_name_idx
ON catalog_versions (
    lower(regexp_replace(btrim(snapshot ->> 'name'), '\s+', ' ', 'g'))
)
WHERE version = 1 AND entity_type IN ('organization', 'activity');

CREATE INDEX IF NOT EXISTS catalog_versions_v1_place_idx
ON catalog_versions ((snapshot ->> 'place_id'))
WHERE version = 1
  AND entity_type = 'organization'
  AND snapshot ->> 'place_id' IS NOT NULL;

CREATE INDEX IF NOT EXISTS catalog_versions_v1_source_idx
ON catalog_versions ((snapshot ->> 'source'), (snapshot ->> 'source_id'))
WHERE version = 1
  AND entity_type = 'organization'
  AND snapshot ->> 'source_id' IS NOT NULL;

CREATE INDEX IF NOT EXISTS catalog_versions_v1_address_idx
ON catalog_versions (lower(btrim(snapshot ->> 'address')))
WHERE version = 1 AND entity_type = 'location';
