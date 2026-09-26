-- Roles and the database of the stand, as in production (apps/migrator/README.md):
-- the migrator owns the schemas, the API and the worker use validate_app.
-- Runs only on an empty volume: after editing, `make reset`.
CREATE ROLE validate_migrator LOGIN PASSWORD 'validate_migrator';
CREATE ROLE validate_app LOGIN PASSWORD 'validate_app';
CREATE DATABASE validate OWNER validate_migrator;
REVOKE ALL ON DATABASE validate FROM PUBLIC;
GRANT CONNECT ON DATABASE validate TO validate_app;
