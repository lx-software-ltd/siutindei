"""Topics, fixed roots, hidden categories, and the school cut.

Revision ID: 0066_family_guide_taxonomy
Revises: 0065_activity_kind_facts

Upgrade, in one transaction:

1. Add ``activity_categories.hidden_from_public``.
2. Insert nine topics (wizard roots), five fixed roots, and the leaves
   under Places to play and Nurseries and kindergartens. Schools and
   Members-only clubs are hidden from public search. The three school
   leaves from ``0040`` keep their ids and move under Schools.
3. Move every other ``0040`` group and leaf to its new row: activities,
   category suggestions, and category reviews. Those suggestion and
   review columns are ``ON DELETE SET NULL``, so they move before the
   old rows are deleted. A category an admin added under an old row
   moves under that row's replacement.
4. Set ``kind`` from the new position, and drop facts the new kind
   does not allow.
5. Delete the seven old groups and their other 23 leaves.
6. Reject, as not relevant, every organization that is not already
   rejected, has activities, and has all of them in hidden categories.
7. Add an import alias for every old English or Chinese name that no
   longer names a category, unless a suggestion row already holds it.

Every write runs as ``migration:0066`` and writes catalog versions.

Downgrade is lossy. It re-creates the ``0040`` rows, moves the school
leaves back under Early years and schools, and moves references back.
Where several old rows merged into one new row, they all return to the
first old leaf that maps to it. A row with no old counterpart returns
to the nearest old group. It deletes the aliases this revision added
and the new rows, and drops the column. It does not undo rejections or
kinds.

Seed assessment: ``seed_data.sql`` inserts two sample activities on
the old leaves Visual arts (``…1233``) and Dance and ballet
(``…1232``), which this revision deletes. They move to Art and making
(``…1304``) and Music, dance and drama (``…1305``) in the seed.
``hidden_from_public`` has a default, so no other seed row changes.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Sequence
from typing import Any, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0066_family_guide_taxonomy"
down_revision: Union[str, None] = "0065_activity_kind_facts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ACTOR = "migration:0066"
_PREFIX = "c1111111-1111-1111-1111-11111111"

# suffix, English, zh-HK, display_order
_TOPICS = (
    ("1301", "Baby and toddler", "嬰幼兒及親子", 10),
    ("1302", "Sports", "運動", 20),
    ("1303", "Swimming and water sports", "游泳及水上活動", 30),
    ("1304", "Art and making", "藝術及手作", 40),
    ("1305", "Music, dance and drama", "音樂、舞蹈及戲劇", 50),
    ("1306", "Languages", "語言", 60),
    ("1307", "STEM and coding", "STEM 及編程", 70),
    ("1308", "Tutoring and exam preparation", "補習及應試", 80),
    ("1309", "Outdoors, scouts and community", "戶外、童軍及社區", 90),
)

# suffix, English, zh-HK, display_order, hidden_from_public
_FIXED_ROOTS = (
    ("1401", "Places to play", "遊樂好去處", 110, False),
    ("1402", "Nurseries and kindergartens", "幼兒中心及幼稚園", 120, False),
    ("1403", "Eat with kids", "親子餐廳", 130, False),
    ("1404", "Schools", "學校", 140, True),
    ("1405", "Members-only clubs", "會員制會所", 150, True),
)

# suffix, parent suffix, English, zh-HK, display_order
_NEW_LEAVES = (
    ("1411", "1401", "Playground and park", "遊樂場及公園", 1),
    ("1412", "1401", "Beach and countryside", "沙灘及郊野", 2),
    ("1413", "1401", "Indoor play", "室內遊樂場", 3),
    ("1414", "1401", "Pool, pitch and court", "泳池及運動場地", 4),
    ("1415", "1401", "Library", "圖書館", 5),
    ("1416", "1401", "Museum and heritage", "博物館及古蹟", 6),
    ("1421", "1402", "Nursery and childcare", "幼兒中心及託兒", 1),
    ("1422", "1402", "Kindergarten", "幼稚園", 2),
)

_SCHOOLS_ROOT = "1404"
_SCHOOL_LEAVES = ("1213", "1214", "1215")

# 0040 rows: suffix, parent suffix or None, English, zh-HK, display_order
_OLD_GROUPS = (
    ("1201", None, "Early years and schools", "幼兒及學校", 10),
    ("1202", None, "Learning and tutoring", "學習及補習", 20),
    ("1203", None, "Arts and performance", "藝術及表演", 30),
    ("1204", None, "Sports and movement", "運動", 40),
    ("1205", None, "Play and outdoors", "遊樂及戶外", 50),
    ("1206", None, "Culture", "文化", 60),
    ("1207", None, "Community and support", "社區及支援", 70),
)
_OLD_LEAVES = (
    ("1211", "1201", "Kindergarten and nursery", "幼稚園及幼兒園", 1),
    ("1212", "1201", "Day crèche and childcare", "日間托兒", 2),
    ("1213", "1201", "Primary school", "小學", 3),
    ("1214", "1201", "Secondary school", "中學", 4),
    ("1215", "1201", "International and prep schools", "國際及預備學校", 5),
    ("1221", "1202", "Tutoring centre", "補習中心", 1),
    ("1222", "1202", "Language classes", "語言班", 2),
    ("1223", "1202", "STEM and coding", "STEM及編程", 3),
    ("1224", "1202", "Parent and family education", "親子及家長教育", 4),
    ("1231", "1203", "Music lessons", "音樂課程", 1),
    ("1232", "1203", "Dance and ballet", "舞蹈及芭蕾", 2),
    ("1233", "1203", "Visual arts", "視覺藝術", 3),
    ("1234", "1203", "Drama", "戲劇", 4),
    ("1241", "1204", "Sports centre", "體育館", 1),
    ("1242", "1204", "Swimming pool", "游泳池", 2),
    ("1243", "1204", "Sports grounds and courts", "運動場及球場", 3),
    ("1244", "1204", "Martial arts and boxing", "武術及拳擊", 4),
    ("1245", "1204", "Cycling", "單車", 5),
    ("1251", "1205", "Playground and park", "遊樂場及公園", 1),
    ("1252", "1205", "Indoor playhouse", "室內遊樂場", 2),
    ("1253", "1205", "Beach and countryside", "海灘及郊野", 3),
    ("1261", "1206", "Public library", "公共圖書館", 1),
    ("1262", "1206", "Museum and exhibition", "博物館及展覽", 2),
    ("1263", "1206", "Heritage and performing-arts venue", "文物及表演場地", 3),
    ("1271", "1207", "Community centre", "社區中心", 1),
    ("1272", "1207", "Special needs support", "特殊需要支援", 2),
)

# Old suffix to new suffix, in the plan's table order. The downgrade
# sends a new row back to the first old leaf listed for it.
_MOVES = (
    ("1201", "1422"),
    ("1202", "1308"),
    ("1203", "1305"),
    ("1204", "1302"),
    ("1205", "1411"),
    ("1206", "1416"),
    ("1207", "1309"),
    ("1211", "1422"),
    ("1212", "1421"),
    ("1221", "1308"),
    ("1222", "1306"),
    ("1223", "1307"),
    ("1224", "1309"),
    ("1231", "1305"),
    ("1232", "1305"),
    ("1233", "1304"),
    ("1234", "1305"),
    ("1241", "1414"),
    ("1242", "1414"),
    ("1243", "1414"),
    ("1244", "1302"),
    ("1245", "1302"),
    ("1251", "1411"),
    ("1252", "1413"),
    ("1253", "1412"),
    ("1261", "1415"),
    ("1262", "1416"),
    ("1263", "1416"),
    ("1271", "1309"),
    ("1272", "1309"),
)

# New rows with no old leaf go back to the nearest old group.
_DOWNGRADE_GROUPS = {
    "1301": "1201",
    "1303": "1204",
    "1401": "1205",
    "1402": "1201",
    "1403": "1207",
    "1404": "1201",
    "1405": "1207",
}

_KIND_ROOTS = (("1401", "place"), ("1402", "preschool"), ("1403", "eat"))

# Keep in step with FACT_KEYS in backend/src/app/services/listing_kinds.py.
_CLASS_FACTS = ("drop_in", "parent_stays", "sen_friendly")
_FACT_KEYS = {
    "class": _CLASS_FACTS,
    "camp": (*_CLASS_FACTS, "lunch_included"),
    "place": (
        "toilets",
        "changing_table",
        "shade",
        "fenced",
        "stroller_access",
        "water_play",
        "lifeguard",
        "parking",
        "food_nearby",
    ),
    "preschool": (),
    "eat": (
        "high_chairs",
        "kids_menu",
        "changing_table",
        "stroller_access",
        "room_to_run",
        "outdoor_seating",
    ),
}

_REFERENCES = (
    ("activities", "category_id"),
    ("category_suggestions", "suggested_parent_id"),
    ("category_suggestions", "maps_to_category_id"),
    ("category_suggestions", "created_category_id"),
    ("category_suggestions", "merged_into_category_id"),
    ("activity_category_reviews", "current_category_id"),
    ("activity_category_reviews", "proposed_category_id"),
    ("activity_category_reviews", "previous_category_id"),
)

_INSERT = sa.text(
    """
    INSERT INTO activity_categories (
      id, parent_id, name, name_translations, display_order, show_in_wizard
    ) VALUES (
      CAST(:id AS uuid),
      CAST(:parent_id AS uuid),
      :name,
      CAST(:translations AS jsonb),
      :display_order,
      :show_in_wizard
    )
    ON CONFLICT (id) DO NOTHING
    """
)

# Same rules as normalize_category_key in
# backend/src/app/services/category_suggestions/resolve.py.
_PUNCT_RE = re.compile(r"[^\w\s]+", re.UNICODE)
_SPACE_RE = re.compile(r"\s+")


def _id(suffix: str) -> str:
    return _PREFIX + suffix


def _ids(suffixes: Iterable[str]) -> list[str]:
    return [_id(suffix) for suffix in suffixes]


def _normalize(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).casefold()
    text = _PUNCT_RE.sub(" ", text)
    return _SPACE_RE.sub(" ", text).strip()


def _insert_category(
    bind: Any,
    suffix: str,
    parent: str | None,
    name: str,
    name_zh: str,
    display_order: int,
    show_in_wizard: bool,
) -> None:
    translations = '{"zh":"' + name_zh + '","zh-HK":"' + name_zh + '"}'
    bind.execute(
        _INSERT,
        {
            "id": _id(suffix),
            "parent_id": _id(parent) if parent else None,
            "name": name,
            "translations": translations,
            "display_order": display_order,
            "show_in_wizard": show_in_wizard,
        },
    )


def _as_actor(bind: Any) -> None:
    bind.execute(
        sa.text("SELECT set_config('app.current_user_id', :actor, true)"),
        {"actor": _ACTOR},
    )


def _move_references(bind: Any, pairs: Sequence[tuple[str, str]]) -> None:
    """Point every category reference at its mapped row."""
    params = {
        "old_ids": [_id(old) for old, _new in pairs],
        "new_ids": [_id(new) for _old, new in pairs],
    }
    mapping = (
        "SELECT * FROM unnest(CAST(:old_ids AS uuid[]), CAST(:new_ids AS uuid[])) "
        "AS m(old_id, new_id)"
    )
    for table, column in _REFERENCES:
        bind.execute(
            sa.text(
                f"UPDATE {table} SET {column} = m.new_id "
                f"FROM ({mapping}) AS m WHERE {table}.{column} = m.old_id"
            ),
            params,
        )
    bind.execute(
        sa.text(
            "UPDATE activity_categories SET parent_id = m.new_id "
            f"FROM ({mapping}) AS m "
            "WHERE activity_categories.parent_id = m.old_id "
            "AND activity_categories.id <> ALL(CAST(:moved AS uuid[]))"
        ),
        {**params, "moved": params["old_ids"] + params["new_ids"]},
    )


def upgrade() -> None:
    """Add the hidden flag, the new tree, then move and reject."""
    bind = op.get_bind()
    _as_actor(bind)
    op.add_column(
        "activity_categories",
        sa.Column(
            "hidden_from_public",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Public search leaves out this category and its descendants",
        ),
    )
    for suffix, name, name_zh, order in _TOPICS:
        _insert_category(bind, suffix, None, name, name_zh, order, True)
    for suffix, name, name_zh, order, _hidden in _FIXED_ROOTS:
        _insert_category(bind, suffix, None, name, name_zh, order, False)
    for suffix, parent, name, name_zh, order in _NEW_LEAVES:
        _insert_category(bind, suffix, parent, name, name_zh, order, False)
    bind.execute(
        sa.text(
            "UPDATE activity_categories SET hidden_from_public = true "
            "WHERE id = ANY(CAST(:ids AS uuid[]))"
        ),
        {"ids": _ids(row[0] for row in _FIXED_ROOTS if row[4])},
    )
    bind.execute(
        sa.text(
            "UPDATE activity_categories SET parent_id = CAST(:root AS uuid) "
            "WHERE id = ANY(CAST(:ids AS uuid[]))"
        ),
        {"root": _id(_SCHOOLS_ROOT), "ids": _ids(_SCHOOL_LEAVES)},
    )
    _move_references(bind, _MOVES)
    _set_kinds(bind)
    old_ids = _ids(old for old, _new in _MOVES)
    bind.execute(
        sa.text(
            "UPDATE activity_categories SET show_in_wizard = false "
            "WHERE id = ANY(CAST(:ids AS uuid[]))"
        ),
        {"ids": old_ids},
    )
    for rows in (_OLD_LEAVES, _OLD_GROUPS):
        bind.execute(
            sa.text(
                "DELETE FROM activity_categories WHERE id = ANY(CAST(:ids AS uuid[]))"
            ),
            {"ids": [_id(row[0]) for row in rows if row[0] not in _SCHOOL_LEAVES]},
        )
    _reject_hidden_only_organizations(bind)
    _add_aliases(bind)


def _set_kinds(bind: Any) -> None:
    """Kind follows the fixed root. A topic allows only class or camp."""
    tree = (
        "WITH RECURSIVE tree AS ("
        " SELECT id, id AS root_id FROM activity_categories WHERE parent_id IS NULL"
        " UNION ALL"
        " SELECT c.id, tree.root_id FROM activity_categories c"
        " JOIN tree ON c.parent_id = tree.id"
        ") "
    )
    for root, kind in _KIND_ROOTS:
        bind.execute(
            sa.text(
                tree + "UPDATE activities SET kind = :kind FROM tree "
                "WHERE activities.category_id = tree.id "
                "AND tree.root_id = CAST(:root AS uuid) AND activities.kind <> :kind"
            ),
            {"kind": kind, "root": _id(root)},
        )
    bind.execute(
        sa.text(
            tree + "UPDATE activities SET kind = 'class' FROM tree "
            "WHERE activities.category_id = tree.id "
            "AND tree.root_id = ANY(CAST(:roots AS uuid[])) "
            "AND activities.kind IN ('place', 'preschool', 'eat')"
        ),
        {"roots": _ids(row[0] for row in _TOPICS)},
    )
    for kind, keys in _FACT_KEYS.items():
        bind.execute(
            sa.text(
                "UPDATE activities SET facts = COALESCE(("
                " SELECT jsonb_object_agg(item.key, item.value)"
                " FROM jsonb_each(activities.facts) AS item"
                " WHERE item.key = ANY(CAST(:keys AS text[]))"
                "), '{}'::jsonb) "
                "WHERE kind = :kind AND EXISTS ("
                " SELECT 1 FROM jsonb_object_keys(activities.facts) AS k"
                " WHERE k <> ALL(CAST(:keys AS text[]))"
                ")"
            ),
            {"kind": kind, "keys": list(keys)},
        )


def _reject_hidden_only_organizations(bind: Any) -> None:
    bind.execute(
        sa.text(
            "WITH RECURSIVE hidden AS ("
            " SELECT id FROM activity_categories WHERE hidden_from_public"
            " UNION ALL"
            " SELECT c.id FROM activity_categories c JOIN hidden ON c.parent_id = hidden.id"
            ") "
            "UPDATE organizations SET review_status = 'rejected', "
            "review_reason = 'not_relevant', reviewed_by = :actor, reviewed_at = now() "
            "WHERE review_status <> 'rejected' "
            "AND EXISTS (SELECT 1 FROM activities a WHERE a.org_id = organizations.id) "
            "AND NOT EXISTS ("
            " SELECT 1 FROM activities a WHERE a.org_id = organizations.id"
            " AND a.category_id NOT IN (SELECT id FROM hidden)"
            ")"
        ),
        {"actor": _ACTOR},
    )


def _add_aliases(bind: Any) -> None:
    """Old labels in an import file still resolve after the old rows go."""
    new_by_old = dict(_MOVES)
    live_keys: set[str] = set()
    for name, translations in bind.execute(
        sa.text("SELECT name, name_translations FROM activity_categories")
    ):
        live_keys.add(_normalize(name))
        if isinstance(translations, dict):
            live_keys.update(
                _normalize(value)
                for value in translations.values()
                if isinstance(value, str)
            )
    taken = set(
        bind.execute(sa.text("SELECT fingerprint FROM category_suggestions")).scalars()
    )
    for suffix, _parent, name, name_zh, _order in (*_OLD_GROUPS, *_OLD_LEAVES):
        target = new_by_old.get(suffix)
        if target is None:
            continue
        for label in (name, name_zh):
            fingerprint = _normalize(label)
            if not fingerprint or fingerprint in live_keys or fingerprint in taken:
                continue
            taken.add(fingerprint)
            bind.execute(
                sa.text(
                    "INSERT INTO category_suggestions ("
                    " fingerprint, requested_name, source, status,"
                    " merged_into_category_id, decided_by, decided_at, decision_notes"
                    ") VALUES ("
                    " :fingerprint, :name, 'import', 'merged',"
                    " CAST(:target AS uuid), :actor, now(), :notes"
                    ")"
                ),
                {
                    "fingerprint": fingerprint,
                    "name": label,
                    "target": _id(target),
                    "actor": _ACTOR,
                    "notes": "Category from before the family guide taxonomy",
                },
            )


def _downgrade_pairs() -> list[tuple[str, str]]:
    """New suffix to old suffix: the first old leaf, else the nearest group."""
    group_suffixes = {row[0] for row in _OLD_GROUPS}
    back: dict[str, str] = {}
    for old, new in _MOVES:
        if old in group_suffixes or new in back:
            continue
        back[new] = old
    for new, old in _DOWNGRADE_GROUPS.items():
        back.setdefault(new, old)
    return list(back.items())


def downgrade() -> None:
    """Restore the 0040 tree. Lossy where old rows merged; see the docstring."""
    bind = op.get_bind()
    _as_actor(bind)
    for suffix, parent, name, name_zh, order in _OLD_GROUPS:
        _insert_category(bind, suffix, parent, name, name_zh, order, True)
    for suffix, parent, name, name_zh, order in _OLD_LEAVES:
        _insert_category(bind, suffix, parent, name, name_zh, order, False)
    bind.execute(
        sa.text(
            "UPDATE activity_categories SET parent_id = CAST(:group AS uuid) "
            "WHERE id = ANY(CAST(:ids AS uuid[]))"
        ),
        {"group": _id("1201"), "ids": _ids(_SCHOOL_LEAVES)},
    )
    _move_references(bind, _downgrade_pairs())
    bind.execute(
        sa.text("DELETE FROM category_suggestions WHERE decided_by = :actor"),
        {"actor": _ACTOR},
    )
    for ids in (
        _ids(row[0] for row in _NEW_LEAVES),
        _ids(row[0] for row in (*_TOPICS, *_FIXED_ROOTS)),
    ):
        bind.execute(
            sa.text(
                "DELETE FROM activity_categories WHERE id = ANY(CAST(:ids AS uuid[]))"
            ),
            {"ids": ids},
        )
    op.drop_column("activity_categories", "hidden_from_public")
