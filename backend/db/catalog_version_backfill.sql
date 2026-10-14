-- One-shot history for rows that already exist. Catalog triggers see
-- app.catalog_backfill and do not write a second history row. Audit
-- triggers stay enabled. Callers commit between batches.

CREATE OR REPLACE FUNCTION catalog_backfill_live(etable text, ids uuid[] DEFAULT NULL)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
    rec record;
    audit jsonb;
    current jsonb;
    eid uuid;
    org uuid;
    etype text;
    media_now jsonb;
    media_then jsonb;
BEGIN
    PERFORM set_config('app.catalog_backfill', 'on', true);
    FOR rec IN EXECUTE format(
        'SELECT to_jsonb(t) AS data FROM %I t '
        'WHERE ($1::uuid[] IS NULL OR id = ANY($1::uuid[]))',
        etable
    ) USING ids
    LOOP
        eid := (rec.data ->> 'id')::uuid;
        etype := catalog_entity_type(etable);
        org := catalog_org_id(etable, rec.data);
        current := catalog_enrich_snapshot(etable, rec.data);
        SELECT new_values INTO audit
        FROM audit_log
        WHERE table_name = etable
          AND record_id = eid::text
          AND action = 'INSERT'
        ORDER BY timestamp ASC
        LIMIT 1;
        IF catalog_audit_differs(audit, rec.data) THEN
            PERFORM catalog_upsert_version(
                etype, eid, org, 1, 'created',
                catalog_tracked(audit),
                NULL,
                NULL
            );
            PERFORM catalog_upsert_version(
                etype, eid, org, 2, 'updated',
                current,
                catalog_changed_fields(audit, rec.data),
                NULL
            );
            EXECUTE format('UPDATE %I SET version = 2 WHERE id = $1', etable)
            USING eid;
        ELSE
            PERFORM catalog_upsert_version(
                etype, eid, org, 1, 'created', current, NULL, NULL
            );
        END IF;
        IF etable = 'organizations' THEN
            media_now := jsonb_build_object(
                'media_urls', rec.data -> 'media_urls',
                'logo_media_url', rec.data -> 'logo_media_url'
            );
            media_then := jsonb_build_object(
                'media_urls', audit -> 'media_urls',
                'logo_media_url', audit -> 'logo_media_url'
            );
            IF audit IS NOT NULL AND media_then IS DISTINCT FROM media_now THEN
                PERFORM catalog_upsert_version(
                    'media', eid, org, 1, 'created', media_then, NULL, NULL
                );
                PERFORM catalog_upsert_version(
                    'media', eid, org, 2, 'updated', media_now,
                    ARRAY['media_urls', 'logo_media_url']::text[],
                    NULL
                );
                UPDATE organizations SET media_version = 2 WHERE id = eid;
            ELSE
                PERFORM catalog_upsert_version(
                    'media', eid, org, 1, 'created', media_now, NULL, NULL
                );
            END IF;
        END IF;
    END LOOP;
END;
$$;

CREATE OR REPLACE FUNCTION catalog_backfill_live_candidates(
    etable text,
    lim integer
)
RETURNS uuid[]
LANGUAGE plpgsql
AS $$
DECLARE
    ids uuid[];
BEGIN
    EXECUTE format(
        'SELECT array_agg(id ORDER BY id) FROM ('
        '    SELECT id FROM %1$I '
        '    WHERE NOT EXISTS ('
        '        SELECT 1 FROM catalog_versions '
        '        WHERE entity_id = %1$I.id '
        '          AND entity_type = catalog_entity_type($1) '
        '          AND version = 1'
        '    ) '
        '    ORDER BY id '
        '    LIMIT $2 '
        '    FOR UPDATE SKIP LOCKED'
        ') picked',
        etable
    )
    INTO ids
    USING etable, lim;
    RETURN ids;
END;
$$;

CREATE OR REPLACE FUNCTION catalog_backfill_live_batch(etable text)
RETURNS integer
LANGUAGE plpgsql
AS $$
DECLARE
    ids uuid[];
BEGIN
    ids := catalog_backfill_live_candidates(etable, 200);
    IF ids IS NULL THEN
        RETURN 0;
    END IF;
    PERFORM catalog_backfill_live(etable, ids);
    RETURN cardinality(ids);
END;
$$;

CREATE OR REPLACE FUNCTION catalog_backfill_deleted(
    etable text,
    ids text[] DEFAULT NULL
)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
    rec record;
    inserted jsonb;
    removed jsonb;
    eid uuid;
    org uuid;
    etype text;
    survivor uuid;
    org_name text;
    org_source text;
    org_source_id text;
    org_place text;
    still_there boolean;
BEGIN
    PERFORM set_config('app.catalog_backfill', 'on', true);
    FOR rec IN
        SELECT DISTINCT record_id
        FROM audit_log
        WHERE table_name = etable
          AND action = 'DELETE'
          AND (ids IS NULL OR record_id = ANY(ids))
    LOOP
        BEGIN
            eid := rec.record_id::uuid;
        EXCEPTION WHEN others THEN
            CONTINUE;
        END;
        EXECUTE format(
            'SELECT EXISTS (SELECT 1 FROM %I WHERE id = $1)',
            etable
        )
        INTO still_there
        USING eid;
        IF still_there THEN
            CONTINUE;
        END IF;
        SELECT new_values INTO inserted
        FROM audit_log
        WHERE table_name = etable
          AND record_id = rec.record_id
          AND action = 'INSERT'
        ORDER BY timestamp ASC
        LIMIT 1;
        IF inserted IS NULL THEN
            CONTINUE;
        END IF;
        SELECT old_values INTO removed
        FROM audit_log
        WHERE table_name = etable
          AND record_id = rec.record_id
          AND action = 'DELETE'
        ORDER BY timestamp DESC
        LIMIT 1;
        etype := catalog_entity_type(etable);
        org := catalog_org_id(etable, COALESCE(removed, inserted));
        IF etable = 'organizations' THEN
            org := eid;
        END IF;
        PERFORM catalog_upsert_version(
            etype, eid, org, 1, 'created',
            catalog_tracked(inserted), NULL, NULL
        );
        PERFORM catalog_upsert_version(
            etype, eid, org, 2, 'deleted',
            catalog_tracked(COALESCE(removed, inserted)),
            NULL,
            NULL
        );
        IF etable <> 'organizations' THEN
            CONTINUE;
        END IF;
        SELECT survivor_org_id INTO survivor
        FROM organization_merges
        WHERE merged_org_id = eid
          AND kind = 'merge'
        ORDER BY merged_at DESC
        LIMIT 1;
        IF survivor IS NOT NULL THEN
            UPDATE catalog_versions
            SET reason = 'merged', related_id = survivor
            WHERE entity_type = 'organization'
              AND entity_id = eid
              AND action = 'deleted';
            CONTINUE;
        END IF;
        IF EXISTS (
            SELECT 1 FROM organization_merges WHERE merged_org_id = eid
        ) THEN
            CONTINUE;
        END IF;
        org_name := COALESCE(removed ->> 'name', inserted ->> 'name', '');
        org_source := NULLIF(COALESCE(removed ->> 'source', inserted ->> 'source'), '');
        org_source_id := NULLIF(
            COALESCE(removed ->> 'source_id', inserted ->> 'source_id'), ''
        );
        org_place := NULLIF(
            COALESCE(removed ->> 'place_id', inserted ->> 'place_id'), ''
        );
        INSERT INTO organization_merges (
            id,
            merged_org_id,
            survivor_org_id,
            kind,
            source,
            source_id,
            place_id,
            snapshot,
            moved_counts
        ) VALUES (
            gen_random_uuid(),
            eid,
            NULL,
            'delete',
            org_source,
            org_source_id,
            org_place,
            jsonb_build_object(
                'name', org_name,
                'names', jsonb_build_array(org_name)
            ),
            '{}'::jsonb
        );
    END LOOP;
END;
$$;

CREATE OR REPLACE FUNCTION catalog_backfill_deleted_candidates(
    etable text,
    lim integer
)
RETURNS text[]
LANGUAGE plpgsql
AS $$
DECLARE
    ids text[];
BEGIN
    -- Match catalog_backfill_deleted. A tombstone needs an INSERT audit
    -- row, and a live row belongs to the live backfill. Any other id
    -- writes nothing and would be picked again on the next call.
    EXECUTE format(
        'SELECT array_agg(record_id ORDER BY record_id) FROM ('
        '    SELECT DISTINCT audit_log.record_id'
        '    FROM audit_log'
        '    WHERE audit_log.table_name = $1'
        '      AND audit_log.action = ''DELETE'''
        '      AND audit_log.record_id ~* ''^[0-9a-f-]{36}$'''
        '      AND EXISTS ('
        '          SELECT 1 FROM audit_log inserted'
        '          WHERE inserted.table_name = $1'
        '            AND inserted.record_id = audit_log.record_id'
        '            AND inserted.action = ''INSERT'''
        '      )'
        '      AND NOT EXISTS ('
        '          SELECT 1 FROM %1$I live'
        '          WHERE live.id = audit_log.record_id::uuid'
        '      )'
        '      AND NOT EXISTS ('
        '          SELECT 1 FROM catalog_versions'
        '          WHERE entity_id = audit_log.record_id::uuid'
        '            AND entity_type = catalog_entity_type($1)'
        '            AND version = 1'
        '      )'
        '    ORDER BY audit_log.record_id'
        '    LIMIT $2'
        ') picked',
        etable
    )
    INTO ids
    USING etable, lim;
    RETURN ids;
END;
$$;

CREATE OR REPLACE FUNCTION catalog_backfill_deleted_batch(etable text)
RETURNS integer
LANGUAGE plpgsql
AS $$
DECLARE
    ids text[];
BEGIN
    ids := catalog_backfill_deleted_candidates(etable, 200);
    IF ids IS NULL THEN
        RETURN 0;
    END IF;
    PERFORM catalog_backfill_deleted(etable, ids);
    RETURN cardinality(ids);
END;
$$;
