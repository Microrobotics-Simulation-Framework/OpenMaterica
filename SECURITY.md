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

OpenMaterica reads and writes files and runs no code from the files it reads. It opens no network sockets: its
MCP server speaks over stdio only. The one planned exception is registry drafting in `openmaterica-authoring`,
which fetches a source's metadata only when a person runs it with an explicit flag.

- **Trusted inputs.** OpenMaterica assumes the files it is given are trusted, and validates records only
  against the record schema. A USD stage can pull in other files through its composition (sublayers,
  references, payloads) and through the host's asset resolver, so reading a stage may read any file that
  stage names. Every USD layer OpenMaterica ships is self-contained (no composition arcs, no asset paths).
  Loading third-party records and stages, and the security of the asset resolver, are the
  responsibility of the integrating application (`docs/regulatory/intended_use.md`).
- **No code from data.** Records and family test vectors are data. Family reference implementations are
  code shipped in the package and are never loaded from a record.
- **MCP tooling.** The MCP server (not built yet) ships in the core's wheel and runs only with the `[mcp]`
  extra. It loads tools only from a closed list (the core, `openmaterica-authoring` and
  `openmaterica-families`), so another installed package adds none. Content returned to an agent (papers,
  records) is data. The MCP tools can only write drafts: they cannot publish, merge, set tiers or
  redistribution statuses, or write check points except by baking them. An agent acting on instructions
  injected through a document can at worst produce a bad draft, which review and `materica check` exist to
  stop. The server speaks over stdio only, opens no socket, holds no keys, and loads no tool that makes a
  network request.
- **Silent data errors.** A wrong value, unit, convention or resolution is a correctness defect and is tracked
  in `docs/validation/known_anomalies.yaml`, not here, unless it can be triggered deliberately by a crafted
  file.
- **Supply chain.** The core has no run-time dependency beyond Python's standard library; `jsonschema` comes
  only with the `[check]` extra and numpy with `[sample]`; OpenUSD with `[usd]` (`usd-core`) or from the host
  application's own build; an MCP server library only with `[mcp]`. Security-relevant dependency updates are
  recorded in the **Security** section of the changelog of the distribution concerned (`CHANGELOG.md` for
  the core).
