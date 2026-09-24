-- Seed data for Hong Kong activities

INSERT INTO organizations (id, name, description, manager_id, review_status)
SELECT '11111111-1111-1111-1111-111111111111', 'Harbor Arts Studio',
       'Art classes focused on painting and crafts.',
       '{{SEED_MANAGER_SUB}}', 'approved'
WHERE NOT EXISTS (
  SELECT 1 FROM organizations WHERE id = '11111111-1111-1111-1111-111111111111'
);

INSERT INTO organizations (id, name, description, manager_id, review_status)
SELECT '22222222-2222-2222-2222-222222222222', 'Kowloon Kids Dance',
       'Dance and movement programs for children.',
       '{{SEED_MANAGER_SUB}}', 'approved'
WHERE NOT EXISTS (
  SELECT 1 FROM organizations WHERE id = '22222222-2222-2222-2222-222222222222'
);

INSERT INTO activity_categories (id, parent_id, name, display_order)
SELECT '99999999-9999-9999-9999-999999999999', NULL, 'Sport', 1
WHERE NOT EXISTS (
  SELECT 1 FROM activity_categories
  WHERE id = '99999999-9999-9999-9999-999999999999'
);

INSERT INTO locations (id, org_id, area_id, address, lat, lng)
SELECT 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', '11111111-1111-1111-1111-111111111111',
       (SELECT id FROM geographic_areas WHERE name = 'Central and Western' AND level = 'district' LIMIT 1),
       '10 Example Lane', 22.282, 114.158
WHERE NOT EXISTS (
  SELECT 1 FROM locations WHERE id = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
);

INSERT INTO locations (id, org_id, area_id, address, lat, lng)
SELECT 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', '11111111-1111-1111-1111-111111111111',
       (SELECT id FROM geographic_areas WHERE name = 'Wan Chai' AND level = 'district' LIMIT 1),
       '88 Hennessy Road', 22.276, 114.172
WHERE NOT EXISTS (
  SELECT 1 FROM locations WHERE id = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'
);

INSERT INTO locations (id, org_id, area_id, address, lat, lng)
SELECT 'cccccccc-cccc-cccc-cccc-cccccccccccc', '22222222-2222-2222-2222-222222222222',
       (SELECT id FROM geographic_areas WHERE name = 'Yau Tsim Mong' AND level = 'district' LIMIT 1),
       '18 Nathan Road', 22.298, 114.172
WHERE NOT EXISTS (
  SELECT 1 FROM locations WHERE id = 'cccccccc-cccc-cccc-cccc-cccccccccccc'
);

INSERT INTO activities (id, org_id, category_id, name, description, age_range)
SELECT 'dddddddd-dddd-dddd-dddd-dddddddddddd', '11111111-1111-1111-1111-111111111111',
       '99999999-9999-9999-9999-999999999999',
       'Creative Painting', 'Painting classes for young artists.',
       int4range(4, 9, '[]')
WHERE NOT EXISTS (
  SELECT 1 FROM activities WHERE id = 'dddddddd-dddd-dddd-dddd-dddddddddddd'
);

INSERT INTO activities (id, org_id, category_id, name, description, age_range)
SELECT 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee', '22222222-2222-2222-2222-222222222222',
       '99999999-9999-9999-9999-999999999999',
       'Beginner Dance', 'Introductory dance sessions.',
       int4range(3, 7, '[]')
WHERE NOT EXISTS (
  SELECT 1 FROM activities WHERE id = 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee'
);

INSERT INTO activity_locations (activity_id, location_id)
SELECT 'dddddddd-dddd-dddd-dddd-dddddddddddd', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
WHERE NOT EXISTS (
  SELECT 1 FROM activity_locations
  WHERE activity_id = 'dddddddd-dddd-dddd-dddd-dddddddddddd'
    AND location_id = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
);

INSERT INTO activity_locations (activity_id, location_id)
SELECT 'dddddddd-dddd-dddd-dddd-dddddddddddd', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'
WHERE NOT EXISTS (
  SELECT 1 FROM activity_locations
  WHERE activity_id = 'dddddddd-dddd-dddd-dddd-dddddddddddd'
    AND location_id = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'
);

INSERT INTO activity_locations (activity_id, location_id)
SELECT 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee', 'cccccccc-cccc-cccc-cccc-cccccccccccc'
WHERE NOT EXISTS (
  SELECT 1 FROM activity_locations
  WHERE activity_id = 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee'
    AND location_id = 'cccccccc-cccc-cccc-cccc-cccccccccccc'
);

INSERT INTO activity_pricing (
  id,
  activity_id,
  location_id,
  pricing_type,
  amount,
  currency,
  sessions_count,
  free_trial_class_offered
)
SELECT 'f1111111-1111-1111-1111-111111111111', 'dddddddd-dddd-dddd-dddd-dddddddddddd',
       'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'per_class', 280.00, 'HKD', NULL, false
WHERE NOT EXISTS (
  SELECT 1 FROM activity_pricing WHERE id = 'f1111111-1111-1111-1111-111111111111'
);

INSERT INTO activity_pricing (
  id,
  activity_id,
  location_id,
  pricing_type,
  amount,
  currency,
  sessions_count,
  free_trial_class_offered
)
SELECT 'f2222222-2222-2222-2222-222222222222', 'dddddddd-dddd-dddd-dddd-dddddddddddd',
       'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'per_sessions', 1200.00, 'HKD', 6, true
WHERE NOT EXISTS (
  SELECT 1 FROM activity_pricing WHERE id = 'f2222222-2222-2222-2222-222222222222'
);

INSERT INTO activity_schedule (
  id, activity_id, location_id, schedule_type, languages
)
SELECT '51111111-1111-1111-1111-111111111111', 'dddddddd-dddd-dddd-dddd-dddddddddddd',
       'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'weekly', ARRAY['en','zh']
WHERE NOT EXISTS (
  SELECT 1 FROM activity_schedule WHERE id = '51111111-1111-1111-1111-111111111111'
);

INSERT INTO activity_schedule_entries (
  id, schedule_id, day_of_week_utc, start_minutes_utc, end_minutes_utc
)
SELECT gen_random_uuid(), '51111111-1111-1111-1111-111111111111', 6, 120, 240
WHERE NOT EXISTS (
  SELECT 1 FROM activity_schedule_entries
  WHERE schedule_id = '51111111-1111-1111-1111-111111111111'
    AND day_of_week_utc = 6
    AND start_minutes_utc = 120
    AND end_minutes_utc = 240
);

INSERT INTO activity_schedule (
  id, activity_id, location_id, schedule_type, languages
)
SELECT '52222222-2222-2222-2222-222222222222', 'dddddddd-dddd-dddd-dddd-dddddddddddd',
       'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'weekly', ARRAY['zh']
WHERE NOT EXISTS (
  SELECT 1 FROM activity_schedule WHERE id = '52222222-2222-2222-2222-222222222222'
);

INSERT INTO activity_schedule_entries (
  id, schedule_id, day_of_week_utc, start_minutes_utc, end_minutes_utc
)
SELECT gen_random_uuid(), '52222222-2222-2222-2222-222222222222', 2, 300, 420
WHERE NOT EXISTS (
  SELECT 1 FROM activity_schedule_entries
  WHERE schedule_id = '52222222-2222-2222-2222-222222222222'
    AND day_of_week_utc = 2
    AND start_minutes_utc = 300
    AND end_minutes_utc = 420
);

INSERT INTO activity_schedule (
  id, activity_id, location_id, schedule_type, languages
)
SELECT '53333333-3333-3333-3333-333333333333', 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee',
       'cccccccc-cccc-cccc-cccc-cccccccccccc', 'weekly', ARRAY['en']
WHERE NOT EXISTS (
  SELECT 1 FROM activity_schedule WHERE id = '53333333-3333-3333-3333-333333333333'
);

INSERT INTO activity_schedule_entries (
  id, schedule_id, day_of_week_utc, start_minutes_utc, end_minutes_utc
)
SELECT gen_random_uuid(), '53333333-3333-3333-3333-333333333333', 1, 120, 210
WHERE NOT EXISTS (
  SELECT 1 FROM activity_schedule_entries
  WHERE schedule_id = '53333333-3333-3333-3333-333333333333'
    AND day_of_week_utc = 1
    AND start_minutes_utc = 120
    AND end_minutes_utc = 210
);

INSERT INTO feedback_labels (id, name, display_order)
SELECT 'fa111111-1111-1111-1111-111111111111', 'Service Quality', 1
WHERE NOT EXISTS (
  SELECT 1 FROM feedback_labels WHERE id = 'fa111111-1111-1111-1111-111111111111'
);

INSERT INTO feedback_labels (id, name, display_order)
SELECT 'fa222222-2222-2222-2222-222222222222', 'Value for Money', 2
WHERE NOT EXISTS (
  SELECT 1 FROM feedback_labels WHERE id = 'fa222222-2222-2222-2222-222222222222'
);

INSERT INTO feedback_labels (id, name, display_order)
SELECT 'fa333333-3333-3333-3333-333333333333', 'Facilities', 3
WHERE NOT EXISTS (
  SELECT 1 FROM feedback_labels WHERE id = 'fa333333-3333-3333-3333-333333333333'
);

INSERT INTO organization_feedback (
  id,
  organization_id,
  submitter_id,
  submitter_email,
  stars,
  label_ids,
  description,
  source_ticket_id
)
SELECT
  'fb111111-1111-1111-1111-111111111111',
  '11111111-1111-1111-1111-111111111111',
  '{{SEED_MANAGER_SUB}}',
  'parent@example.com',
  4,
  ARRAY[
    'fa111111-1111-1111-1111-111111111111'::uuid,
    'fa222222-2222-2222-2222-222222222222'::uuid
  ],
  'Friendly instructors and good class pacing.',
  'F00001'
WHERE NOT EXISTS (
  SELECT 1
  FROM organization_feedback
  WHERE id = 'fb111111-1111-1111-1111-111111111111'
);

INSERT INTO tickets (
  id,
  ticket_id,
  ticket_type,
  submitter_id,
  submitter_email,
  organization_name,
  message,
  status
)
SELECT
  'fc111111-1111-1111-1111-111111111111',
  'R00001',
  'access_request',
  '{{SEED_MANAGER_SUB}}',
  'newmanager@example.com',
  'Harbor Arts Studio',
  'I help run classes and need manager access.',
  'pending'
WHERE NOT EXISTS (
  SELECT 1 FROM tickets WHERE ticket_id = 'R00001'
);

-- Partner API keys for local development only.
-- Plaintext values (send as the x-partner-key header):
--   read  (full access): stk_dev_read_00000000000000000000000000000000
--   crud  (Harbor Arts Studio only):
--         stk_dev_crud_00000000000000000000000000000000
INSERT INTO api_keys (id, name, key_prefix, key_hash, scope, org_id)
SELECT
  'ad111111-1111-1111-1111-111111111111',
  'Dev read key (full access)',
  'stk_dev_read',
  'be20fa1ff8c5f25cfdbbc6a3cf1f962b8df5fe55a2e557f988b6c26ca52f465f',
  'read',
  NULL
WHERE NOT EXISTS (
  SELECT 1 FROM api_keys WHERE id = 'ad111111-1111-1111-1111-111111111111'
);

INSERT INTO api_keys (id, name, key_prefix, key_hash, scope, org_id)
SELECT
  'ad222222-2222-2222-2222-222222222222',
  'Dev crud key (Harbor Arts Studio)',
  'stk_dev_crud',
  '765af9bfa840ac05d524fe15e27c9cdb0e1f0e2e51809ee5e3461ae44115aae2',
  'crud',
  '11111111-1111-1111-1111-111111111111'
WHERE NOT EXISTS (
  SELECT 1 FROM api_keys WHERE id = 'ad222222-2222-2222-2222-222222222222'
);
