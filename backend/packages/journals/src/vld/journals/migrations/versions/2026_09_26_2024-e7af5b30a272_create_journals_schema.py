"""Create the journals schema: journals, specialities and the VAK registry.

Revision ID: e7af5b30a272
Revises: b2a07c5e1f30
Create Date: 2026-09-26

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from vld.journals.infrastructure.models import (
    CHANNEL,
    DOCUMENT_SOURCE,
    ISSN_SOURCE,
    JOURNAL,
    JOURNAL_ISSN,
    PUBLICATION_KIND,
    SCHEMA,
    SCIENCE_BRANCH,
    SPECIALITY,
    VAK_CURRENT,
    VAK_DOCUMENT,
    VAK_DOCUMENT_FILE,
    VAK_FORMER_ISSN,
    VAK_FORMER_TITLE,
    VAK_GROUP,
    VAK_GROUP_SPECIALITY,
    VAK_LISTING,
    VAK_LISTING_ISSN,
    VAK_PARSE,
    VAK_PARSE_WARNING,
    VAK_PUBLICATION,
    VAK_SNAPSHOT,
    VAK_WARNING_CODE,
)
from vld.migrator.ops import app_role, create_domain_schema, drop_domain_schema

revision = "e7af5b30a272"
down_revision = "b2a07c5e1f30"
branch_labels = None
depends_on = None

irreversible = False

# Journal numbers and pages stay in the thousands, places in a cell or a group under
# a hundred: a wider integer would only fatten the facts.
squawk_ignore = ("prefer-bigint-over-int", "prefer-bigint-over-smallint")

_SCIENCE_BRANCH: sa.Enum = postgresql.ENUM(
    "agriculture",
    "architecture",
    "art_history",
    "biology",
    "chemistry",
    "cultural_studies",
    "economics",
    "geography",
    "geology_mineralogy",
    "history",
    "law",
    "medicine",
    "military",
    "pedagogy",
    "pharmacy",
    "philology",
    "philosophy",
    "physics_mathematics",
    "political_science",
    "psychology",
    "sociology",
    "technical",
    "theology",
    "veterinary",
    name=SCIENCE_BRANCH,
    schema=SCHEMA,
    create_type=False,
)
_VAK_WARNING_CODE: sa.Enum = postgresql.ENUM(
    "column_shift",
    "row_unrecognized",
    "numbering_gap",
    "title_unparsed",
    "title_repaired",
    "issn_missing",
    "issn_unrecognized",
    "issn_checksum",
    "issn_repaired",
    "journal_without_specialities",
    "speciality_unrecognized",
    "branch_missing",
    "branch_unknown",
    "branch_repaired",
    "date_unrecognized",
    "date_repaired",
    name=VAK_WARNING_CODE,
    schema=SCHEMA,
    create_type=False,
)
_CHANNEL: sa.Enum = postgresql.ENUM(
    "cli",
    name=CHANNEL,
    schema=SCHEMA,
    create_type=False,
)
_DOCUMENT_SOURCE: sa.Enum = postgresql.ENUM(
    "download",
    "file",
    name=DOCUMENT_SOURCE,
    schema=SCHEMA,
    create_type=False,
)
_ISSN_SOURCE: sa.Enum = postgresql.ENUM(
    "import",
    "moderator",
    name=ISSN_SOURCE,
    schema=SCHEMA,
    create_type=False,
)
_PUBLICATION_KIND: sa.Enum = postgresql.ENUM(
    "publish",
    "rollback",
    name=PUBLICATION_KIND,
    schema=SCHEMA,
    create_type=False,
)
_ENUMS = (
    _SCIENCE_BRANCH,
    _VAK_WARNING_CODE,
    _CHANNEL,
    _DOCUMENT_SOURCE,
    _ISSN_SOURCE,
    _PUBLICATION_KIND,
)

# The app role adds rows; only three tables have rows that change: an ISSN a
# moderator reassigns, the latest PDF replaced by the next, the pointer moved.
_INSERT_ONLY = "UPDATE, DELETE, TRUNCATE"
_REVOKED = {
    JOURNAL: _INSERT_ONLY,
    JOURNAL_ISSN: "DELETE, TRUNCATE",
    SPECIALITY: _INSERT_ONLY,
    VAK_DOCUMENT: _INSERT_ONLY,
    VAK_DOCUMENT_FILE: "UPDATE, TRUNCATE",
    VAK_SNAPSHOT: _INSERT_ONLY,
    VAK_PARSE: _INSERT_ONLY,
    VAK_PARSE_WARNING: _INSERT_ONLY,
    VAK_LISTING: _INSERT_ONLY,
    VAK_LISTING_ISSN: _INSERT_ONLY,
    VAK_FORMER_TITLE: _INSERT_ONLY,
    VAK_FORMER_ISSN: _INSERT_ONLY,
    VAK_GROUP: _INSERT_ONLY,
    VAK_GROUP_SPECIALITY: _INSERT_ONLY,
    VAK_CURRENT: "DELETE, TRUNCATE",
    VAK_PUBLICATION: _INSERT_ONLY,
}


def upgrade() -> None:
    """Apply the revision."""
    create_domain_schema(SCHEMA)
    bind = op.get_bind()
    for enum in _ENUMS:
        enum.create(bind)
    _ = op.create_table(
        JOURNAL,
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="When the journal was first seen.",
        ),
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_journal")),
        schema=SCHEMA,
    )
    _ = op.create_table(
        SPECIALITY,
        sa.Column("code", sa.Text(), nullable=False, comment="5.9.5 or 10.02.01."),
        sa.Column(
            "branch",
            _SCIENCE_BRANCH,
            nullable=True,
            comment="The branch of science; none when it could not be read.",
        ),
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "code ~ '^[0-9]{1,2}\\.[0-9]{1,2}\\.[0-9]{1,2}$'",
            name=op.f("ck_speciality_code_format"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_speciality")),
        sa.UniqueConstraint(
            "code",
            "branch",
            name="uq_speciality_code_branch",
            postgresql_nulls_not_distinct=True,
        ),
        schema=SCHEMA,
    )
    _ = op.create_table(
        VAK_DOCUMENT,
        sa.Column(
            "sha256",
            sa.LargeBinary(),
            nullable=False,
            comment="SHA-256 of the file: its identity.",
        ),
        sa.Column("size", sa.BigInteger(), nullable=False, comment="Size in bytes."),
        sa.Column(
            "source",
            _DOCUMENT_SOURCE,
            nullable=False,
            comment="Downloaded from the site of VAK, or given as a file.",
        ),
        sa.Column("url", sa.Text(), nullable=True, comment="Where it was downloaded."),
        sa.Column(
            "file_name",
            sa.Text(),
            nullable=True,
            comment="The file it came from.",
        ),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="When it was fetched or read.",
        ),
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "octet_length(sha256) = 32",
            name=op.f("ck_vak_document_sha256_length"),
        ),
        sa.CheckConstraint("size > 0", name=op.f("ck_vak_document_size_positive")),
        sa.CheckConstraint(
            "url IS NOT NULL OR file_name IS NOT NULL",
            name=op.f("ck_vak_document_has_origin"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vak_document")),
        sa.UniqueConstraint("sha256", name=op.f("uq_vak_document_sha256")),
        schema=SCHEMA,
    )
    _ = op.create_table(
        JOURNAL_ISSN,
        sa.Column("issn", sa.Text(), nullable=False, comment="NNNN-NNNC."),
        sa.Column(
            "journal_id",
            sa.UUID(),
            nullable=False,
            comment="The journal the ISSN belongs to.",
        ),
        sa.Column(
            "source",
            _ISSN_SOURCE,
            nullable=False,
            comment="An import gave it, or a moderator chose it.",
        ),
        sa.Column(
            "assigned_by",
            sa.Text(),
            nullable=False,
            comment="Who gave it: user@host.",
        ),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="When it was given.",
        ),
        sa.CheckConstraint(
            "issn ~ '^[0-9]{4}-[0-9]{3}[0-9X]$'",
            name=op.f("ck_journal_issn_issn_format"),
        ),
        sa.ForeignKeyConstraint(
            ["journal_id"],
            [f"{SCHEMA}.{JOURNAL}.id"],
            name=op.f("fk_journal_issn_journal_id_journal"),
        ),
        sa.PrimaryKeyConstraint("issn", name=op.f("pk_journal_issn")),
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_journals_journal_issn_journal_id"),
        JOURNAL_ISSN,
        ["journal_id"],
        unique=False,
        schema=SCHEMA,
    )
    _ = op.create_table(
        VAK_DOCUMENT_FILE,
        sa.Column("document_id", sa.UUID(), nullable=False, comment="The document."),
        sa.Column("data", sa.LargeBinary(), nullable=False, comment="The PDF."),
        sa.ForeignKeyConstraint(
            ["document_id"],
            [f"{SCHEMA}.{VAK_DOCUMENT}.id"],
            name=op.f("fk_vak_document_file_document_id_vak_document"),
        ),
        sa.PrimaryKeyConstraint("document_id", name=op.f("pk_vak_document_file")),
        schema=SCHEMA,
    )
    _ = op.create_table(
        VAK_SNAPSHOT,
        sa.Column(
            "document_id",
            sa.UUID(),
            nullable=False,
            comment="The document read.",
        ),
        sa.Column(
            "parser_version",
            sa.Text(),
            nullable=False,
            comment="Version of vld-vak.",
        ),
        sa.Column(
            "edition_date",
            sa.Date(),
            nullable=False,
            comment="«По состоянию на».",
        ),
        sa.Column("channel", _CHANNEL, nullable=False, comment="Where it came from."),
        sa.Column(
            "operator",
            sa.Text(),
            nullable=False,
            comment="Who imported it: user@host.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="When it was imported.",
        ),
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            [f"{SCHEMA}.{VAK_DOCUMENT}.id"],
            name=op.f("fk_vak_snapshot_document_id_vak_document"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vak_snapshot")),
        sa.UniqueConstraint(
            "document_id",
            "parser_version",
            name="uq_vak_snapshot_document_parser",
        ),
        schema=SCHEMA,
    )
    _ = op.create_table(
        VAK_CURRENT,
        sa.Column(
            "singleton",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
            comment="Always true: the key that allows one row.",
        ),
        sa.Column(
            "snapshot_id",
            sa.UUID(),
            nullable=False,
            comment="The current snapshot.",
        ),
        sa.CheckConstraint("singleton", name=op.f("ck_vak_current_one_row")),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            [f"{SCHEMA}.{VAK_SNAPSHOT}.id"],
            name=op.f("fk_vak_current_snapshot_id_vak_snapshot"),
        ),
        sa.PrimaryKeyConstraint("singleton", name=op.f("pk_vak_current")),
        schema=SCHEMA,
    )
    _ = op.create_table(
        VAK_LISTING,
        sa.Column("snapshot_id", sa.UUID(), nullable=False, comment="The edition."),
        sa.Column(
            "journal_id",
            sa.UUID(),
            nullable=False,
            comment="The journal the entry is.",
        ),
        sa.Column("number", sa.Integer(), nullable=False, comment="«№ п/п»."),
        sa.Column(
            "first_page",
            sa.Integer(),
            nullable=False,
            comment="First page of the entry.",
        ),
        sa.Column(
            "last_page",
            sa.Integer(),
            nullable=False,
            comment="Last page of the entry.",
        ),
        sa.Column(
            "title_printed",
            sa.Text(),
            nullable=False,
            comment="The title cell verbatim.",
        ),
        sa.Column(
            "title_main",
            sa.Text(),
            nullable=False,
            comment="The title without brackets.",
        ),
        sa.Column(
            "title_translation",
            sa.Text(),
            nullable=True,
            comment="The translation into Russian.",
        ),
        sa.Column(
            "issn_printed",
            sa.Text(),
            nullable=False,
            comment="The ISSN cell verbatim.",
        ),
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.CheckConstraint(
            "0 < first_page AND first_page <= last_page",
            name=op.f("ck_vak_listing_pages"),
        ),
        sa.CheckConstraint("number > 0", name=op.f("ck_vak_listing_number_positive")),
        sa.ForeignKeyConstraint(
            ["journal_id"],
            [f"{SCHEMA}.{JOURNAL}.id"],
            name=op.f("fk_vak_listing_journal_id_journal"),
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            [f"{SCHEMA}.{VAK_SNAPSHOT}.id"],
            name=op.f("fk_vak_listing_snapshot_id_vak_snapshot"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vak_listing")),
        sa.UniqueConstraint(
            "snapshot_id",
            "journal_id",
            name="uq_vak_listing_snapshot_journal",
        ),
        sa.UniqueConstraint(
            "snapshot_id",
            "number",
            name="uq_vak_listing_snapshot_number",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_journals_vak_listing_journal_id"),
        VAK_LISTING,
        ["journal_id", "snapshot_id"],
        unique=False,
        schema=SCHEMA,
    )
    _ = op.create_table(
        VAK_PARSE,
        sa.Column("snapshot_id", sa.UUID(), nullable=False, comment="The snapshot."),
        sa.Column(
            "format_version",
            sa.SmallInteger(),
            nullable=False,
            comment="format_version of the JSON.",
        ),
        sa.Column(
            "data",
            sa.LargeBinary(),
            nullable=False,
            comment="gzip of the JSON.",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            [f"{SCHEMA}.{VAK_SNAPSHOT}.id"],
            name=op.f("fk_vak_parse_snapshot_id_vak_snapshot"),
        ),
        sa.PrimaryKeyConstraint("snapshot_id", name=op.f("pk_vak_parse")),
        schema=SCHEMA,
    )
    _ = op.create_table(
        VAK_PARSE_WARNING,
        sa.Column("snapshot_id", sa.UUID(), nullable=False, comment="The snapshot."),
        sa.Column(
            "code",
            _VAK_WARNING_CODE,
            nullable=False,
            comment="What it is about.",
        ),
        sa.Column("page", sa.Integer(), nullable=True, comment="Page of the document."),
        sa.Column(
            "journal_number",
            sa.Integer(),
            nullable=True,
            comment="Number of the journal it is about.",
        ),
        sa.Column("printed", sa.Text(), nullable=False, comment="The text concerned."),
        sa.Column("message", sa.Text(), nullable=False, comment="Explanation."),
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            [f"{SCHEMA}.{VAK_SNAPSHOT}.id"],
            name=op.f("fk_vak_parse_warning_snapshot_id_vak_snapshot"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vak_parse_warning")),
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_journals_vak_parse_warning_snapshot_id"),
        VAK_PARSE_WARNING,
        ["snapshot_id", "code"],
        unique=False,
        schema=SCHEMA,
    )
    _ = op.create_table(
        VAK_PUBLICATION,
        sa.Column(
            "kind",
            _PUBLICATION_KIND,
            nullable=False,
            comment="Publication or rollback.",
        ),
        sa.Column(
            "from_snapshot_id",
            sa.UUID(),
            nullable=True,
            comment="The snapshot current before; none for the first publication.",
        ),
        sa.Column(
            "to_snapshot_id",
            sa.UUID(),
            nullable=False,
            comment="The snapshot current after.",
        ),
        sa.Column(
            "forced",
            sa.Boolean(),
            nullable=False,
            comment="Published over tripped quality checks.",
        ),
        sa.Column(
            "reason",
            sa.Text(),
            nullable=True,
            comment="Why: required for a rollback and a forced publication.",
        ),
        sa.Column("channel", _CHANNEL, nullable=False, comment="Where it came from."),
        sa.Column("operator", sa.Text(), nullable=False, comment="Who: user@host."),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="When the pointer moved.",
        ),
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.CheckConstraint(
            "(kind = 'publish' AND NOT forced) OR reason IS NOT NULL",
            name=op.f("ck_vak_publication_reason_when_forced_or_rolled_back"),
        ),
        sa.CheckConstraint(
            "from_snapshot_id IS DISTINCT FROM to_snapshot_id",
            name=op.f("ck_vak_publication_moves"),
        ),
        sa.ForeignKeyConstraint(
            ["from_snapshot_id"],
            [f"{SCHEMA}.{VAK_SNAPSHOT}.id"],
            name=op.f("fk_vak_publication_from_snapshot_id_vak_snapshot"),
        ),
        sa.ForeignKeyConstraint(
            ["to_snapshot_id"],
            [f"{SCHEMA}.{VAK_SNAPSHOT}.id"],
            name=op.f("fk_vak_publication_to_snapshot_id_vak_snapshot"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vak_publication")),
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_journals_vak_publication_to_snapshot_id"),
        VAK_PUBLICATION,
        ["to_snapshot_id"],
        unique=False,
        schema=SCHEMA,
    )
    _ = op.create_table(
        VAK_FORMER_TITLE,
        sa.Column("listing_id", sa.BigInteger(), nullable=False, comment="The entry."),
        sa.Column(
            "position",
            sa.SmallInteger(),
            nullable=False,
            comment="Place in the title.",
        ),
        sa.Column("title", sa.Text(), nullable=False, comment="The former title."),
        sa.Column("until", sa.Date(), nullable=True, comment="Used until this date."),
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.CheckConstraint(
            "position > 0",
            name=op.f("ck_vak_former_title_position_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["listing_id"],
            [f"{SCHEMA}.{VAK_LISTING}.id"],
            name=op.f("fk_vak_former_title_listing_id_vak_listing"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vak_former_title")),
        sa.UniqueConstraint(
            "listing_id",
            "position",
            name=op.f("uq_vak_former_title_listing_id"),
        ),
        schema=SCHEMA,
    )
    _ = op.create_table(
        VAK_GROUP,
        sa.Column("listing_id", sa.BigInteger(), nullable=False, comment="The entry."),
        sa.Column(
            "position",
            sa.SmallInteger(),
            nullable=False,
            comment="Place in the entry.",
        ),
        sa.Column(
            "dates_printed",
            sa.Text(),
            nullable=False,
            comment="The date cell verbatim.",
        ),
        sa.Column("included", sa.Date(), nullable=True, comment="The «с» date."),
        sa.Column("excluded", sa.Date(), nullable=True, comment="The «по» date."),
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.CheckConstraint("position > 0", name=op.f("ck_vak_group_position_positive")),
        sa.ForeignKeyConstraint(
            ["listing_id"],
            [f"{SCHEMA}.{VAK_LISTING}.id"],
            name=op.f("fk_vak_group_listing_id_vak_listing"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vak_group")),
        sa.UniqueConstraint(
            "listing_id",
            "position",
            name=op.f("uq_vak_group_listing_id"),
        ),
        schema=SCHEMA,
    )
    _ = op.create_table(
        VAK_LISTING_ISSN,
        sa.Column("listing_id", sa.BigInteger(), nullable=False, comment="The entry."),
        sa.Column(
            "position",
            sa.SmallInteger(),
            nullable=False,
            comment="Place in the cell, from 1.",
        ),
        sa.Column("issn", sa.Text(), nullable=False, comment="NNNN-NNNC as printed."),
        sa.CheckConstraint(
            "issn ~ '^[0-9]{4}-[0-9]{3}[0-9X]$'",
            name=op.f("ck_vak_listing_issn_issn_format"),
        ),
        sa.CheckConstraint(
            "position > 0",
            name=op.f("ck_vak_listing_issn_position_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["listing_id"],
            [f"{SCHEMA}.{VAK_LISTING}.id"],
            name=op.f("fk_vak_listing_issn_listing_id_vak_listing"),
        ),
        sa.PrimaryKeyConstraint(
            "listing_id",
            "position",
            name=op.f("pk_vak_listing_issn"),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_journals_vak_listing_issn_issn"),
        VAK_LISTING_ISSN,
        ["issn"],
        unique=False,
        schema=SCHEMA,
    )
    _ = op.create_table(
        VAK_FORMER_ISSN,
        sa.Column(
            "former_title_id",
            sa.BigInteger(),
            nullable=False,
            comment="The former title.",
        ),
        sa.Column(
            "position",
            sa.SmallInteger(),
            nullable=False,
            comment="Place in the bracket, from 1.",
        ),
        sa.Column("issn", sa.Text(), nullable=False, comment="NNNN-NNNC as printed."),
        sa.CheckConstraint(
            "issn ~ '^[0-9]{4}-[0-9]{3}[0-9X]$'",
            name=op.f("ck_vak_former_issn_issn_format"),
        ),
        sa.CheckConstraint(
            "position > 0",
            name=op.f("ck_vak_former_issn_position_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["former_title_id"],
            [f"{SCHEMA}.{VAK_FORMER_TITLE}.id"],
            name=op.f("fk_vak_former_issn_former_title_id_vak_former_title"),
        ),
        sa.PrimaryKeyConstraint(
            "former_title_id",
            "position",
            name=op.f("pk_vak_former_issn"),
        ),
        schema=SCHEMA,
    )
    _ = op.create_table(
        VAK_GROUP_SPECIALITY,
        sa.Column("group_id", sa.BigInteger(), nullable=False, comment="The group."),
        sa.Column(
            "position",
            sa.SmallInteger(),
            nullable=False,
            comment="Place in the group, from 1.",
        ),
        sa.Column(
            "speciality_id",
            sa.UUID(),
            nullable=False,
            comment="The speciality.",
        ),
        sa.Column(
            "name_printed",
            sa.Text(),
            nullable=False,
            comment="Its name in this row.",
        ),
        sa.Column(
            "printed",
            sa.Text(),
            nullable=False,
            comment="The speciality verbatim.",
        ),
        sa.CheckConstraint(
            "position > 0",
            name=op.f("ck_vak_group_speciality_position_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["group_id"],
            [f"{SCHEMA}.{VAK_GROUP}.id"],
            name=op.f("fk_vak_group_speciality_group_id_vak_group"),
        ),
        sa.ForeignKeyConstraint(
            ["speciality_id"],
            [f"{SCHEMA}.{SPECIALITY}.id"],
            name=op.f("fk_vak_group_speciality_speciality_id_speciality"),
        ),
        sa.PrimaryKeyConstraint(
            "group_id",
            "position",
            name=op.f("pk_vak_group_speciality"),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_journals_vak_group_speciality_speciality_id"),
        VAK_GROUP_SPECIALITY,
        ["speciality_id", "group_id"],
        unique=False,
        schema=SCHEMA,
    )
    role = app_role()
    for table, privileges in _REVOKED.items():
        op.execute(f"REVOKE {privileges} ON {SCHEMA}.{table} FROM PUBLIC, {role}")


def downgrade() -> None:
    """Undo the revision."""
    op.drop_table(VAK_GROUP_SPECIALITY, schema=SCHEMA)
    op.drop_table(VAK_FORMER_ISSN, schema=SCHEMA)
    op.drop_table(VAK_LISTING_ISSN, schema=SCHEMA)
    op.drop_table(VAK_GROUP, schema=SCHEMA)
    op.drop_table(VAK_FORMER_TITLE, schema=SCHEMA)
    op.drop_table(VAK_PUBLICATION, schema=SCHEMA)
    op.drop_table(VAK_PARSE_WARNING, schema=SCHEMA)
    op.drop_table(VAK_PARSE, schema=SCHEMA)
    op.drop_table(VAK_LISTING, schema=SCHEMA)
    op.drop_table(VAK_CURRENT, schema=SCHEMA)
    op.drop_table(VAK_SNAPSHOT, schema=SCHEMA)
    op.drop_table(VAK_DOCUMENT_FILE, schema=SCHEMA)
    op.drop_table(JOURNAL_ISSN, schema=SCHEMA)
    op.drop_table(VAK_DOCUMENT, schema=SCHEMA)
    op.drop_table(SPECIALITY, schema=SCHEMA)
    op.drop_table(JOURNAL, schema=SCHEMA)
    bind = op.get_bind()
    for enum in reversed(_ENUMS):
        enum.drop(bind)
    drop_domain_schema(SCHEMA)
