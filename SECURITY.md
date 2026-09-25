# Security policy

validate keeps accounts, their validation history and their reference lists, and it
fetches web pages on a user's behalf to complete citations. A leak between accounts or
a way to make the server fetch what it should not is the most serious bug it can have.
Thank you for reporting one privately.

## Reporting

Report through GitHub: **Security → Report a vulnerability** on this repository. Do not
open a public issue, discussion or pull request for a vulnerability.

Please include the commit or deployment you tested, the request or steps, what you could
read, change or reach, and what you expected to be stopped.

## What counts

- Reading or changing another account's data: validation history, reference lists,
  notifications, profile.
- Signing in as someone else, keeping a session after sign-out or password change, or
  getting a token the service should not issue.
- Making the server fetch an internal address or a URL outside the citation sources
  (SSRF), or reading a local file through a citation or import.
- Injection into SQL, into generated `.bib` or GOST output, or into the web interface.
- Secrets, tokens or personal data in logs, error responses or the frontend bundle.

A journal missing from the VAK list or the White List, or a wrong speciality, is a data
error, not a vulnerability: open an issue with the *Registry data is wrong* template.

## What happens next

We confirm receipt within 7 days and agree on a fix and a date. Disclosure is coordinated
and happens at the latest 90 days after the report, or earlier once the fix is deployed.
Reporters are credited in the advisory unless they ask otherwise.

## Supported versions

Only the latest commit on `main` and the running service receive security fixes.
