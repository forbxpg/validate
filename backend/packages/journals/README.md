# vld-journals

Journals and the registries that list them. Today: the schema `journals` with the
shared journal identity and every table of the VAK list; the import use cases come
next.

## The schema

Shared by every registry, never deleted:

| Table | Holds |
|---|---|
| `journal` | a journal: identity only, its title belongs to each edition |
| `journal_issn` | whose an ISSN is: one journal per ISSN, given by an import or chosen by a moderator |
| `speciality` | a speciality: code and branch of science (no branch when it could not be read) |

The VAK registry, one edition at a time:

| Table | Holds |
|---|---|
| `vak_document` | every PDF of the list we imported: SHA-256, size, where from |
| `vak_document_file` | the bytes of the latest PDF only |
| `vak_snapshot` | an edition as one parser version read it; unique per document and parser version |
| `vak_parse`, `vak_parse_warning` | the parse result (gzip of the vld-vak JSON) and its warnings |
| `vak_listing` | a numbered entry of the edition, tied to its journal, with its title as printed |
| `vak_listing_issn`, `vak_former_title`, `vak_former_issn` | ISSNs and former titles as printed |
| `vak_group`, `vak_group_speciality` | speciality groups with their «с/по» dates, and each speciality with its name as printed |
| `vak_current` | the pointer to the current snapshot: one row once something is published |
| `vak_publication` | every move of the pointer: publication or rollback, who, when, why |

A snapshot is a draft until a publication points at it. Nothing of a snapshot is
ever changed or deleted: the app role may only add rows, except on three tables —
`journal_issn` (a moderator reassigns an ISSN), `vak_document_file` (the latest PDF
replaced) and `vak_current` (the pointer moved). The migration revokes the rest and
a test reads the grants back.

The science branch and the warning code are PostgreSQL enums with the values of
`ScienceBranch` and `WarningCode` of vld-vak: a value added to the parser needs a
migration, and a test that compares the labels turns red until it is written.

## Layout

```
domain/                        Channel, DocumentSource, IssnSource, PublicationKind
infrastructure/models/         one module per entity; names of tables and constraints in _tables.py
migrations/versions/           the revisions of the schema
```

## Tests

```bash
uv run pytest packages/journals
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5452/postgres \
    uv run pytest -m integration packages/journals
```

The integration tests migrate a `test_journals_*` database with `vld-migrate` and
check the enums, the grants of the app role, the constraints, and the four questions
the prototype answered: the current list, a journal by ISSN with its specialities,
the specialities with their names, and «was journal X listed for speciality Y on
date D».
