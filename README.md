# editpdf

Merge, split and rotate PDF files with drag and drop, at
**https://editpdf.coderforge.org**.

- **Merge**: drop several PDFs, drag them into order, download one document.
- **Split**: one PDF per page, every N pages, or custom ranges (`1-3, 4-8, 9-`);
  click the scissors between two pages to cut there. You get a ZIP.
- **Rotate**: turn single pages or all of them, with a live preview.

Previews are rendered in the browser (pdf.js); the work is done by a Cloud
Builder Function in Python (pypdf). Files are processed in memory and never
stored. The interface is in English and Italian.

```
browser ── Cloudflare ── cf-edge ── secure-gateway ── Cloud Builder Function "editpdf"
                                                        ├─ /api/v1/...   the API (Python, pypdf)
                                                        └─ /...          the web interface (React)
```

## Repository

| Path | What |
|---|---|
| `openapi/editpdf-v1.yaml` | The API contract, OpenAPI 3.1. The source of truth for the backend and the interface's types. |
| `backend/` | The service in Python: `src/editpdf/`, tests in `tests/`, the Function package builder in `scripts/build_function.py`. |
| `frontend/` | The web interface: React + TypeScript (TSX) + Vite. |
| `infra/terraform/` | The deployment: the Function, its settings, the gateway route. |
| `legal/` | Terms and Conditions (English) and their version. |
| `docs/cloudbuilder-functions-improvements.md` | What the Functions platform needs for this service, as proposals. |
| `scripts/build.sh`, `scripts/build.ps1` | Build everything that is deployed. |

## API

Versioned in the path, `/api/v1`; the full description is
[`openapi/editpdf-v1.yaml`](openapi/editpdf-v1.yaml), also served at
`/api/v1/openapi.yaml`. Changes within v1 are additive only; a breaking change
becomes `/api/v2`, and v1 keeps answering for at least six months, announcing
its end with `Deprecation` and `Sunset` headers.

| Operation | |
|---|---|
| `POST /api/v1/pdf/merge` | `files` (2 or more PDFs, in order) → PDF |
| `POST /api/v1/pdf/split` | `file`, `mode` = `each` \| `every` (+ `size`) \| `ranges` (+ `ranges`) → ZIP |
| `POST /api/v1/pdf/rotate` | `file`, `angle` (+ `pages`) or `rotations` (JSON) → PDF |
| `POST /api/v1/pdf/inspect` | `file` → pages, sizes, rotations, metadata (JSON) |
| `GET /api/v1/info` | version, limits, Terms version |
| `GET /api/v1/health` | liveness |

Bodies are `multipart/form-data`; pages are 1-based; errors are RFC 9457
problem documents with a stable `code`.

```sh
curl -F files=@a.pdf -F files=@b.pdf -o merged.pdf https://editpdf.coderforge.org/api/v1/pdf/merge
curl -F file=@report.pdf -F ranges=1-3,4- -o parts.zip https://editpdf.coderforge.org/api/v1/pdf/split
curl -F file=@scan.pdf -F angle=90 -F pages=2,4 -o turned.pdf https://editpdf.coderforge.org/api/v1/pdf/rotate
```

## Development

Requirements: Python 3.10+ and Node.js 22+.

```sh
# Backend: the API on http://127.0.0.1:8787
python -m venv backend/.venv
backend/.venv/bin/pip install -e "backend[dev]"        # Windows: backend\.venv\Scripts\pip
backend/.venv/bin/python -m editpdf.server

# Interface: http://localhost:5173, sending /api to the backend
npm ci
npm run dev
```

Checks, as CI runs them:

```sh
backend/.venv/bin/ruff check backend && backend/.venv/bin/ruff format --check backend
backend/.venv/bin/python -m pytest backend
npm run typecheck && npm test
npm run lint:openapi
```

The backend has no dependency but pypdf; its multipart parser is the standard
library's job, so the Function package stays pure Python.

## Build and deploy

```sh
./scripts/build.sh          # Windows: .\scripts\build.ps1
```

builds the interface (`frontend/dist`) and the Function package
(`backend/dist/function`: `main.py`, `editpdf/`, `pypdf/`, `static/`;
handler `main.handler`), which Terraform deploys as the Cloud Builder
Function.

Then, with a `CODERFORGE_TOKEN` and the provider as for the other stacks
(`TF_CLI_CONFIG_FILE` pointing at the `dev.tfrc` override):

```sh
cd infra/terraform
terraform init
terraform apply
```

Before the domain answers:

1. **Certificate.** Issue `editpdf.coderforge.org` with CA-Manage and store it
   in the vault under that name, as for the other routes (tf-coderforge-stack
   trust ids). It needs automatic renewal like every CA-Manage certificate.
2. **Cloudflare.** A proxied record for `editpdf`, like `cloud` and `cloud-proc`.
3. **cf-edge.** Add `editpdf.coderforge.org` to `EDGE_DOMAINS` in fundamentals.
4. **Route.** `coderforge_gateway_route` with a function backend is proposal F1
   in [`docs/cloudbuilder-functions-improvements.md`](docs/cloudbuilder-functions-improvements.md);
   until the platform has it, apply with `-var expose_with_gateway_route=false`.

### Settings

Read from the Function's environment (`infra/terraform/main.tf` sets them):

| Variable | Default | |
|---|---|---|
| `EDITPDF_MAX_UPLOAD_BYTES` | `26214400` | largest request |
| `EDITPDF_MAX_FILES` | `20` | most documents in one merge |
| `EDITPDF_MAX_PAGES` | `2000` | most pages in one request |
| `EDITPDF_PUBLIC_URL` | `https://editpdf.coderforge.org` | base of problem types and the terms link |
| `EDITPDF_CORS_ORIGINS` | empty | other origins allowed to call the API from a browser |
| `EDITPDF_SERVE_UI` | `true` | serve the interface next to the API |

## Privacy and security

- Documents live in memory for the length of a request; nothing is written to
  disk, and logs never carry files or their names.
- Encrypted (password protected) PDFs are refused rather than half-processed.
- The interface sends a strict Content-Security-Policy; API answers are
  `no-store`.
- Processing a PDF invalidates its digital signatures: the Terms say so.

## License and terms

The code is under the [MIT License](LICENSE). Use of the service at
editpdf.coderforge.org is subject to its
[Terms and Conditions](legal/terms.en.md) (English only: the operator is a UK company):
it is provided as is, without warranty, and used at the user's own risk.
