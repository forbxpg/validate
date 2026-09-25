# validate

**Check a journal before you submit to it.** validate tells a graduate student whether a
journal is on Russia's VAK list or the “White List”, and for which specialities, then
builds the reference list: give it DOIs, get entries formatted to GOST R 7.0.100-2018
and a `.bib` file for LaTeX.

> **Status: moving in.** The service runs today from a private prototype. Its code is
> being moved here into a uv workspace, one domain at a time. Until that is done, this
> repository holds the project files only.

- Backend: Python, FastAPI, PostgreSQL, Redis, TaskIQ. Frontend: React and TypeScript.
  The interface is in Russian.
- Security reports: see [SECURITY.md](SECURITY.md). Contributing: [CONTRIBUTING.md](CONTRIBUTING.md).

Licensed under [AGPL-3.0](LICENSE). If you run a modified copy as a public service,
the licence requires you to offer its source to your users.
