# Security Policy

## Reporting a vulnerability

Please report security issues privately to **nick@microrobotica.org**, with a description, steps to
reproduce, the affected versions, and a suggested fix if you have one.

- **Acknowledgement**: within 3 business days
- **Initial assessment**: within 7 business days
- **Fix or mitigation**: best effort, prioritised by severity

## Supported versions

No version has been released yet.

## Scope

Vesalius reads and writes files; it opens no network sockets and runs no code from the files it reads.

- **Trusted inputs.** Vesalius assumes the files it is given are trusted, and validates records only
  against the record schema. A USD stage can pull in other files through its composition (sublayers,
  references, payloads) and through the host's asset resolver, so reading a stage may read any file that
  stage names. Every USD layer Vesalius ships is self-contained (no composition arcs, no asset paths).
  Loading third-party records and stages, and the security of the asset resolver, are the
  responsibility of the integrating application (`docs/regulatory/intended_use.md`).
- **No code from data.** Records and family test vectors are data. Family reference implementations are
  code shipped in the package and are never loaded from a record.
- **Silent data errors.** A wrong value, unit, convention or resolution is a correctness defect and is tracked in
  `docs/validation/known_anomalies.yaml`, not here, unless it can be triggered deliberately by a crafted
  file.
- **Supply chain.** Dependencies are kept minimal (numpy, a JSON Schema validator, and optionally
  OpenUSD). Security-relevant
  dependency updates are recorded in the **Security** section of `CHANGELOG.md`.
