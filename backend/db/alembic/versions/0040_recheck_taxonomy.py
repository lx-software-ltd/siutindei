"""Recheck flag, doubled scan budget, and the leaf taxonomy.

Revision ID: 0040_recheck_taxonomy
Revises: 0039_act_source_category

Seed assessment: ignore_current_category is NOT NULL with default
false, so existing scan runs stay valid. monthly_cost_limit_usd only
changes rows still on the old default of 25. New categories are
inserted by id. seed_data.sql re-points its two sample activities at
Visual arts and Dance and ballet; the Sport row stays because live
activities may still reference it until a recheck moves them. The four
former wizard roots lose show_in_wizard and are not deleted. The
partial unique index on root names does not change seed rows: Sport
and the new group names are distinct, and no seed column was added.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0040_recheck_taxonomy"
down_revision: Union[str, None] = "0039_act_source_category"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FORMER_WIZARD = (
    "c1111111-1111-1111-1111-111111111101",
    "c1111111-1111-1111-1111-111111111102",
    "c1111111-1111-1111-1111-111111111103",
    "c1111111-1111-1111-1111-111111111104",
)

# id, parent_id or None, English name, zh-HK, display_order, wizard flag
_GROUPS = (
    (
        "c1111111-1111-1111-1111-111111111201",
        None,
        "Early years and schools",
        "幼兒及學校",
        10,
        True,
    ),
    (
        "c1111111-1111-1111-1111-111111111202",
        None,
        "Learning and tutoring",
        "學習及補習",
        20,
        True,
    ),
    (
        "c1111111-1111-1111-1111-111111111203",
        None,
        "Arts and performance",
        "藝術及表演",
        30,
        True,
    ),
    (
        "c1111111-1111-1111-1111-111111111204",
        None,
        "Sports and movement",
        "運動",
        40,
        True,
    ),
    (
        "c1111111-1111-1111-1111-111111111205",
        None,
        "Play and outdoors",
        "遊樂及戶外",
        50,
        True,
    ),
    (
        "c1111111-1111-1111-1111-111111111206",
        None,
        "Culture",
        "文化",
        60,
        True,
    ),
    (
        "c1111111-1111-1111-1111-111111111207",
        None,
        "Community and support",
        "社區及支援",
        70,
        True,
    ),
)

_LEAVES = (
    (
        "c1111111-1111-1111-1111-111111111211",
        "c1111111-1111-1111-1111-111111111201",
        "Kindergarten and nursery",
        "幼稚園及幼兒園",
        1,
    ),
    (
        "c1111111-1111-1111-1111-111111111212",
        "c1111111-1111-1111-1111-111111111201",
        "Day crèche and childcare",
        "日間托兒",
        2,
    ),
    (
        "c1111111-1111-1111-1111-111111111213",
        "c1111111-1111-1111-1111-111111111201",
        "Primary school",
        "小學",
        3,
    ),
    (
        "c1111111-1111-1111-1111-111111111214",
        "c1111111-1111-1111-1111-111111111201",
        "Secondary school",
        "中學",
        4,
    ),
    (
        "c1111111-1111-1111-1111-111111111215",
        "c1111111-1111-1111-1111-111111111201",
        "International and prep schools",
        "國際及預備學校",
        5,
    ),
    (
        "c1111111-1111-1111-1111-111111111221",
        "c1111111-1111-1111-1111-111111111202",
        "Tutoring centre",
        "補習中心",
        1,
    ),
    (
        "c1111111-1111-1111-1111-111111111222",
        "c1111111-1111-1111-1111-111111111202",
        "Language classes",
        "語言班",
        2,
    ),
    (
        "c1111111-1111-1111-1111-111111111223",
        "c1111111-1111-1111-1111-111111111202",
        "STEM and coding",
        "STEM及編程",
        3,
    ),
    (
        "c1111111-1111-1111-1111-111111111224",
        "c1111111-1111-1111-1111-111111111202",
        "Parent and family education",
        "親子及家長教育",
        4,
    ),
    (
        "c1111111-1111-1111-1111-111111111231",
        "c1111111-1111-1111-1111-111111111203",
        "Music lessons",
        "音樂課程",
        1,
    ),
    (
        "c1111111-1111-1111-1111-111111111232",
        "c1111111-1111-1111-1111-111111111203",
        "Dance and ballet",
        "舞蹈及芭蕾",
        2,
    ),
    (
        "c1111111-1111-1111-1111-111111111233",
        "c1111111-1111-1111-1111-111111111203",
        "Visual arts",
        "視覺藝術",
        3,
    ),
    (
        "c1111111-1111-1111-1111-111111111234",
        "c1111111-1111-1111-1111-111111111203",
        "Drama",
        "戲劇",
        4,
    ),
    (
        "c1111111-1111-1111-1111-111111111241",
        "c1111111-1111-1111-1111-111111111204",
        "Sports centre",
        "體育館",
        1,
    ),
    (
        "c1111111-1111-1111-1111-111111111242",
        "c1111111-1111-1111-1111-111111111204",
        "Swimming pool",
        "游泳池",
        2,
    ),
    (
        "c1111111-1111-1111-1111-111111111243",
        "c1111111-1111-1111-1111-111111111204",
        "Sports grounds and courts",
        "運動場及球場",
        3,
    ),
    (
        "c1111111-1111-1111-1111-111111111244",
        "c1111111-1111-1111-1111-111111111204",
        "Martial arts and boxing",
        "武術及拳擊",
        4,
    ),
    (
        "c1111111-1111-1111-1111-111111111245",
        "c1111111-1111-1111-1111-111111111204",
        "Cycling",
        "單車",
        5,
    ),
    (
        "c1111111-1111-1111-1111-111111111251",
        "c1111111-1111-1111-1111-111111111205",
        "Playground and park",
        "遊樂場及公園",
        1,
    ),
    (
        "c1111111-1111-1111-1111-111111111252",
        "c1111111-1111-1111-1111-111111111205",
        "Indoor playhouse",
        "室內遊樂場",
        2,
    ),
    (
        "c1111111-1111-1111-1111-111111111253",
        "c1111111-1111-1111-1111-111111111205",
        "Beach and countryside",
        "海灘及郊野",
        3,
    ),
    (
        "c1111111-1111-1111-1111-111111111261",
        "c1111111-1111-1111-1111-111111111206",
        "Public library",
        "公共圖書館",
        1,
    ),
    (
        "c1111111-1111-1111-1111-111111111262",
        "c1111111-1111-1111-1111-111111111206",
        "Museum and exhibition",
        "博物館及展覽",
        2,
    ),
    (
        "c1111111-1111-1111-1111-111111111263",
        "c1111111-1111-1111-1111-111111111206",
        "Heritage and performing-arts venue",
        "文物及表演場地",
        3,
    ),
    (
        "c1111111-1111-1111-1111-111111111271",
        "c1111111-1111-1111-1111-111111111207",
        "Community centre",
        "社區中心",
        1,
    ),
    (
        "c1111111-1111-1111-1111-111111111272",
        "c1111111-1111-1111-1111-111111111207",
        "Special needs support",
        "特殊需要支援",
        2,
    ),
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


def _insert_category(
    category_id: str,
    parent_id: str | None,
    name: str,
    name_zh: str,
    display_order: int,
    show_in_wizard: bool,
) -> None:
    translations = '{"zh":"' + name_zh + '","zh-HK":"' + name_zh + '"}'
    op.execute(
        _INSERT.bindparams(
            id=category_id,
            parent_id=parent_id,
            name=name,
            translations=translations,
            display_order=display_order,
            show_in_wizard=show_in_wizard,
        )
    )


def upgrade() -> None:
    """Add the recheck flag, double the default budget, insert leaves."""
    op.add_column(
        "category_scan_runs",
        sa.Column(
            "ignore_current_category",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.alter_column(
        "category_suggestion_settings",
        "monthly_cost_limit_usd",
        server_default=sa.text("50"),
    )
    op.execute(
        "UPDATE category_suggestion_settings "
        "SET monthly_cost_limit_usd = 50 "
        "WHERE monthly_cost_limit_usd = 25"
    )
    for row in _GROUPS:
        _insert_category(row[0], row[1], row[2], row[3], row[4], row[5])
    for row in _LEAVES:
        _insert_category(row[0], row[1], row[2], row[3], row[4], False)
    former = ", ".join(f"'{item}'" for item in _FORMER_WIZARD)
    op.execute(
        "UPDATE activity_categories SET show_in_wizard = false "
        f"WHERE id IN ({former})"
    )
    op.create_index(
        "uq_activity_category_root_name",
        "activity_categories",
        ["name"],
        unique=True,
        postgresql_where=sa.text("parent_id IS NULL"),
    )


def downgrade() -> None:
    """Remove the leaf taxonomy, the flag, and the doubled default.

    Every activity on a new group or leaf moves to Sport. The previous
    leaf is not restored. Suggestion and review foreign keys set
    themselves to null when those categories are deleted.
    """
    leaf_ids = ", ".join(f"'{row[0]}'" for row in _LEAVES)
    group_ids = ", ".join(f"'{row[0]}'" for row in _GROUPS)
    op.execute(
        "UPDATE activities SET category_id = "
        "'99999999-9999-9999-9999-999999999999' "
        f"WHERE category_id IN ({leaf_ids}, {group_ids})"
    )
    op.execute(f"DELETE FROM activity_categories WHERE id IN ({leaf_ids})")
    op.execute(f"DELETE FROM activity_categories WHERE id IN ({group_ids})")
    former = ", ".join(f"'{item}'" for item in _FORMER_WIZARD)
    op.execute(
        "UPDATE activity_categories SET show_in_wizard = true "
        f"WHERE id IN ({former})"
    )
    op.execute(
        "UPDATE category_suggestion_settings "
        "SET monthly_cost_limit_usd = 25 "
        "WHERE monthly_cost_limit_usd = 50"
    )
    op.alter_column(
        "category_suggestion_settings",
        "monthly_cost_limit_usd",
        server_default=sa.text("25"),
    )
    op.drop_column("category_scan_runs", "ignore_current_category")
    op.drop_index(
        "uq_activity_category_root_name",
        table_name="activity_categories",
    )
