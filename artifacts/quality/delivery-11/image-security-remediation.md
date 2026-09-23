# Delivery 11 - runtime image security remediation

## Baseline

The Trivy SARIF artifact from GitHub Actions run `35872211024` is `image-security-sarif` (artifact ID `10755862679`, SHA-256 `f0fe82c8631b73c5ae8eee09e78554f2df44d46326a79f39c3e812afb47bcbf8`). It belongs to commit `69b51421f84b2121f134438e60203fc6e752fea7`, not the current starting commit `d6fd694a904307349496a3de48beb8cf813f06d2`; treat it as historical baseline only. The artifact remains available at [run 35872211024](https://github.com/Rubio120/AVICOLA_PRO/actions/runs/35872211024/artifacts/10755862679).

| Image | SARIF findings (image/CVE/package) | Distinct CVE identifiers | Distinct packages | Findings without a fixed version in this SARIF |
| --- | ---: | ---: | ---: | ---: |
| Backend | 62 | 23 | 21 | 60 |
| Frontend | 67 | 28 | 23 | 56 |
| Backup | 159 | 69 | 34 | 122 |
| Total | 288 | — | — | 238 |

The report contains HIGH/CRITICAL results only, as configured in the workflow. Most baseline entries are operating-system packages from Debian Bookworm. The frontend also includes npm CLI dependency findings (`tar`, `pacote`, `sigstore`, `brace-expansion`, and `ip-address`). The backup image includes vulnerable Go standard-library and module versions bundled into Restic. The historical backend SARIF reports `msgpack 1.1.2`; the current lockfile at `d6fd694` already selects `msgpack 1.2.2`, so that finding cannot be attributed to the current image without a fresh scan.

## Remediation applied; CI verification pending

- Move the supported Python 3.13, Node.js 22, and PostgreSQL 16 runtime bases to current Debian Trixie image tags while retaining their major runtime versions and non-root users.
- Remove unused npm, Corepack, and Yarn files from the frontend production image; the build stages retain npm for `npm ci` and the Next.js build.
- Replace the prebuilt Restic binary with a build of Restic `0.19.1` from pinned upstream commit `00e1171de5d2a17f21d2d13f9024ef2956e6afaa`, using Go `1.26.8` and explicit patched `x/crypto`, `x/net`, `x/text`, and gRPC versions. The image build runs Restic's Go tests before producing the binary.
- Preserve the HIGH/CRITICAL Trivy gate; no finding is ignored or suppressed.

These changes are not considered security-cleared until all three images rebuild and a new SARIF artifact for the same commit shows no actionable HIGH/CRITICAL results. Any remaining unfixable finding must remain visible and blocks Task 1 completion.

## Upstream tag references

- [Python official image tags](https://github.com/docker-library/official-images/blob/master/library/python)
- [Node.js official image tags](https://github.com/docker-library/official-images/blob/master/library/node)
- [PostgreSQL official image tags](https://github.com/docker-library/official-images/blob/master/library/postgres)
- [Go official image tags](https://github.com/docker-library/official-images/blob/master/library/golang)
- [Restic v0.19.1 source module manifest](https://github.com/restic/restic/blob/v0.19.1/go.mod)
