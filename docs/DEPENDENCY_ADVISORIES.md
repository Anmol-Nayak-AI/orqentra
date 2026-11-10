# Dependency advisory review — 2026-10-31

Status: unresolved build-tool finding; no risk acceptance or production security approval is implied.

`npm audit --json` during 2A container verification reports three moderate package findings, zero high and zero critical. All three findings share one chain:

```text
openapi-typescript 7.13.0
└── @redocly/openapi-core 1.34.22
    └── minimatch 5.1.9
```

[GHSA-g3hv-75wg-m249](https://github.com/advisories/GHSA-g3hv-75wg-m249) lists minimatch versions below 11.0.1 as affected by a pattern-amplification denial of service; 11.0.1 is the published patched version. Advisory publication/review changed after the original 2A install audit, so its historical zero-finding result does not describe the current audit.

Local review: the generator is a root development dependency, operates on locally exported FastAPI OpenAPI, and is not copied into the final nginx image. Neither the Python API nor built UI exposes a spec-generation endpoint or accepts external specs for this tool. This limits exposure without resolving the reported dependency finding.

The registry currently lists 7.13.0 as the latest openapi-typescript release. Npm proposes a major downgrade to 6.7.6. Redocly currently calls minimatch as a CommonJS function; newer minimatch majors change that interface. A blanket override or `npm audit fix --force` has therefore not been applied. No compatible patched replacement has been verified.

Follow-up owner: platform/backend lead. Upgrade the generator through a supported compatible release, or review a replacement and verify OpenAPI 3.1/schema support, deterministic generated types, drift checking, TypeScript, build and container tests. Resolve/review before accepting untrusted specifications or treating the build pipeline as production-approved. Do not suppress the finding or report a clean audit in the meantime.
