"""Names of the journals schema, its tables, types and constraints."""

from __future__ import annotations

SCHEMA = "journals"

JOURNAL = "journal"
JOURNAL_ISSN = "journal_issn"
SPECIALITY = "speciality"
VAK_DOCUMENT = "vak_document"
VAK_DOCUMENT_FILE = "vak_document_file"
VAK_SNAPSHOT = "vak_snapshot"
VAK_PARSE = "vak_parse"
VAK_PARSE_WARNING = "vak_parse_warning"
VAK_LISTING = "vak_listing"
VAK_LISTING_ISSN = "vak_listing_issn"
VAK_FORMER_TITLE = "vak_former_title"
VAK_FORMER_ISSN = "vak_former_issn"
VAK_GROUP = "vak_group"
VAK_GROUP_SPECIALITY = "vak_group_speciality"
VAK_CURRENT = "vak_current"
VAK_PUBLICATION = "vak_publication"

SCIENCE_BRANCH = "science_branch"
VAK_WARNING_CODE = "vak_warning_code"
CHANNEL = "channel"
DOCUMENT_SOURCE = "document_source"
ISSN_SOURCE = "issn_source"
PUBLICATION_KIND = "publication_kind"

ISSN_PATTERN = "^[0-9]{4}-[0-9]{3}[0-9X]$"
SPECIALITY_CODE_PATTERN = "^[0-9]{1,2}\\.[0-9]{1,2}\\.[0-9]{1,2}$"

SPECIALITY_IDENTITY = f"uq_{SPECIALITY}_code_branch"
SNAPSHOT_IDENTITY = f"uq_{VAK_SNAPSHOT}_document_parser"
# Both unique keys of an entry start with its snapshot: the convention would name
# them alike.
LISTING_NUMBER = f"uq_{VAK_LISTING}_snapshot_number"
LISTING_JOURNAL = f"uq_{VAK_LISTING}_snapshot_journal"
PUBLICATION_REASON = "reason_when_forced_or_rolled_back"
CURRENT_SINGLETON = "one_row"
