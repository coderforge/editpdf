# Cloud Builder Functions: what editpdf needs, and what is proposed

editpdf is meant to run as a Cloud Builder Function published at
`https://editpdf.coderforge.org`. Building it showed what the Functions
platform has to offer for a public web service that handles users' documents.
This document lists what is missing or unclear, in priority order, each with a
concrete proposal. The deployment in `infra/terraform` is written against these
proposals where it had to be (F1), and works without them where it could.

What editpdf relies on today:

| | Status |
|---|---|
| A Python runtime, entry file `main.py` with handler `handler`, a zip package (`coderforge_function`, `executable { filename, source_code_hash, handler, runtime_type, runtime_version }`) | in use (the `reverse-string` example) |
| The function's environment from a parameter (`env_param_rid`), as container services have | **missing** (the provider refuses `env_param_rid`), F5; editpdf runs on its defaults |
| A public HTTP trigger: a domain routed to the function | **missing** (the provider refuses `function_rid` on a route), F1 |
| A documented HTTP event and result, binary safe | **to confirm**, F2 |

## P0: needed to go live

### F1. Gateway routes that target a function

**Problem.** A secure-gateway route sends a domain to `host:port` backends in
the gateway's network. A function has no host and port, and invoking it goes
through the Cloud Builder API with a user's bearer token. There is no way to
put a function behind a public domain.

**Proposal.** A route backend can be a function:

```hcl
resource "coderforge_gateway_route" "editpdf" {
  container_service_rid   = data.coderforge_container_service.gateway.rid
  name                    = "editpdf.coderforge.org"
  domains                 = ["editpdf.coderforge.org"]
  function_rid            = coderforge_function.editpdf.rid   # instead of backends
  certificate_secret_name = "editpdf.coderforge.org"
}
```

The gateway (or cloud-builder-manager behind it) turns each HTTP request into
the event of F2, invokes the function anonymously on the route's behalf, and
turns the result back into an HTTP response. Invocation through a route needs
no user token; the route is the authorisation. An optional `auth = "token"` on
the route would keep a function private while still reachable over HTTP.

### F2. A documented, versioned HTTP event

**Problem.** A handler has to know exactly what it receives and what to return;
for PDFs and ZIPs the body is binary.

**Proposal.** Adopt the shape most tooling already speaks (API Gateway payload
format 2.0) and version it with `payload_format_version = "2.0"` on the
function or the route:

```json
{
  "version": "2.0",
  "rawPath": "/api/v1/pdf/merge",
  "rawQueryString": "",
  "headers": { "content-type": "multipart/form-data; boundary=...", "x-request-id": "..." },
  "requestContext": { "http": { "method": "POST", "sourceIp": "..." }, "requestId": "...", "domainName": "editpdf.coderforge.org" },
  "body": "<base64>",
  "isBase64Encoded": true
}
```

and the result `{ "statusCode", "headers", "body", "isBase64Encoded" }`.
`backend/src/editpdf/function.py` already accepts this shape (and payload 1.0,
and a plain `{method, path, headers, body}`), so it adapts to whichever the
platform settles on.

### F3. Per-function limits

**Problem.** The function has to state, and the platform to enforce, how much
a request may carry and how long it may run. The first `coderforge_function`
schema had `timeout` and `max_ram_size`; the executable-based one does not
show them.

**Proposal.** `timeout_seconds`, `memory_mb`, `max_request_bytes` and
`max_response_bytes` on `coderforge_function`, enforced by the platform with
clear errors (413, 504). The timeout must stay under Cloudflare's 100 seconds
for anything published through it. editpdf would take `max_request_bytes = 26214400`
and `timeout_seconds = 60`.

### F4. Where functions run, for private data

**Problem.** The platform has processors (`/api/v1/function/process`,
`/api/v1/function/processors`, a pool with idle and warm processors). editpdf
handles documents people upload: contracts, invoices, IDs. Whoever operates a
processor sees them. If a processor can be a browser page or a machine outside
the platform's control, editpdf must not run there.

**Proposal.** A function states where it may run, `processor_pool = "platform"`
(platform-operated, trusted processors only) versus a public pool, and the
platform documents its isolation: no state shared between invocations of
different functions, nothing written to disk, memory not reused across
tenants. The Terms and Conditions of editpdf say files are processed in memory
and not stored; the platform has to make that true.

### F5. Environment from the parameter store and the vault

**Problem.** editpdf reads its settings from the environment
(`EDITPDF_MAX_UPLOAD_BYTES`, `EDITPDF_PUBLIC_URL`...). Container services take
`env_param_rid` / `env_secret_rid`; functions should too. And, as fundamentals
showed, a changed environment must redeploy, or the running code never sees it.

**Proposal.** `env_param_rid` and `env_secret_rid` on `coderforge_function`,
and the provider folds the parameter's value and the secret's keys into the
change it plans, so that editing a setting is a planned redeploy without
hashing the environment into `source_code_hash` by hand (as fundamentals has
to). editpdf would then take:

```hcl
resource "coderforge_param" "env" {
  name = "editpdf-env"
  value = jsonencode({
    EDITPDF_PUBLIC_URL       = "https://editpdf.coderforge.org"
    EDITPDF_MAX_UPLOAD_BYTES = "26214400"
  })
}

resource "coderforge_function" "editpdf" {
  # ...
  env_param_rid = coderforge_param.env.id
}
```

## P1: needed to run it well

### F6. Concurrency and warm instances

`min_warm` and `max_concurrency` per function; when the queue is full, a 503
with `Retry-After` rather than a timeout. A PDF merge takes from milliseconds
to seconds: a cold start on every request would dominate.

### F7. Caching of static responses

editpdf serves its web interface from the same function. Its assets have
content-hashed names and `Cache-Control: public, max-age=31536000, immutable`.
The gateway should cache `GET` answers that say so (Cloudflare does in front,
but not for LAN users), so that the interface does not cost invocations.
Alternatively: routes that serve a path prefix from a storage bucket.

### F8. Rate limits on public routes

An anonymous route needs a per-client rate limit (`rate_limit = { requests = 30, per_seconds = 60 }`
on the route), or a documented Cloudflare WAF rule set for every public
function.

### F9. Python dependencies

editpdf vendors pypdf into its zip (`backend/scripts/build_function.py`,
pure-Python wheels only). The platform could install a `requirements.txt` at
deploy time, or offer layers, and should document which Python versions
exist and whether packages with native code can run.

## P2: nice to have

- **F10. Logs and metrics.** Function stdout/stderr into log groups, as
  container services have; invocation count, duration and errors; the
  `X-Request-Id` of the request passed through to the event and the logs.
- **F11. Versions and aliases.** Immutable published versions and an alias the
  route points at, for a rollback that does not need a rebuild.
- **F12. Large files.** Presigned upload to storage and an event that refers to
  the object, for documents larger than a request may carry.
- **F13. Route certificates.** Every new route needs a CA-Manage certificate,
  and every CA-Manage certificate needs automatic renewal. A route could name
  the CA-Manage profile and let the platform issue and renew its certificate.
