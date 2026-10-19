# HTTPS diagnosis and local verification

Scope: dedicated deployment on `enterprise-tenancy`, based on commit `4533da9`.
The original checkout was inspected read-only. Changes are isolated in the
temporary repository's `fix/https` branch, with the redirect follow-up on
`fix/https-review` and complete local testing on `fix/https-local-tests`.
The only push destination is `mohammedrajeb/AQREM-temp`; the original checkout
and its production branches were not changed.

## Request path

The dedicated stack does not wire in Front Door, Application Gateway, or App
Service. Its public URL is the web Container App's generated
`azurecontainerapps.io` FQDN. Container Apps ingress terminates public TLS and
forwards HTTP to Nginx on port 80. Nginx serves the SPA and proxies `/api/` and
`/health` to the internal API ingress, which forwards to FastAPI on port 8000.
The API remains inaccessible from outside its Container Apps environment.

The separate, older shared-client stack has optional Front Door and custom-domain
modules. They are not invoked by `stacks/dedicated` and are outside this change.
No deployed hostname, DNS records, Azure state, or live error was supplied.

## Diagnosis coverage

| Part of the request path | Evidence and conclusion |
| --- | --- |
| DNS and domain validation | The dedicated stack uses generated Container Apps FQDNs and has no custom-domain binding or DNS record to repair. Local `localhost` resolution was verified as loopback. Actual Azure DNS remains unverified without the deployed hostname. |
| Public TLS and certificates | Public TLS terminates at Container Apps ingress, with insecure ingress disabled. No missing custom certificate was assumed. Local requests validate a temporary CA and hostname; tests reject expired, untrusted, and mismatched upstream certificates. The deployed certificate/expiry remains unverified. |
| Ports and exposure | Web ingress targets Nginx port 80; API ingress targets FastAPI port 8000 and remains internal. Public port 443 belongs to the Azure ingress. No network rules or public exposure were loosened. |
| Internal TLS and host routing | The old web upstream used HTTP despite HTTPS-enforced API ingress. Using HTTPS also requires SNI and certificate verification. Both proxied locations now use those settings; upstream Host still selects the API ingress. |
| Redirects and forwarded headers | Before/after requests reproduce internal redirect leakage and a no-SNI 502. Public-host forwarding is sanitized and internal absolute redirects now retain the public HTTPS authority, path, and query. External redirects are preserved. |
| Application origins, CORS, mixed content | The production web bundle uses same-origin API requests when no build override is set. The dedicated stack now supplies its public HTTPS origin to API/worker configuration; this also supplies the existing CORS and invitation/reset URL mechanisms. No CORS wildcard or TLS bypass was added. |
| Terraform dependencies | The public origin is derived from the environment DNS suffix and existing web app name, avoiding an API-to-web dependency cycle. Validation and two plan-only mocked-provider tests pass. A real state-aware Azure plan remains required. |

These are confirmed configuration defects and local reproductions. They do not
establish the current condition of an unidentified Azure deployment.

## Failures reproduced locally

Real Nginx 1.27 integration tests against local HTTP and TLS servers established:

* HTTPS upstream requests did not send SNI. A shared ingress needs the upstream
  hostname to select its TLS endpoint.
* Untrusted and wrong-host upstream certificates were accepted (HTTP 200 instead
  of a rejected upstream connection).
* A supplied `X-Forwarded-Host` passed through unchanged. Without that header,
  requests only carried the internal upstream `Host`. The application's invitation
  URL fallback reads these headers, so its public origin was not reliably preserved.

The dedicated Terraform configuration also selected `http://<client>-api` while
the API ingress retained the default HTTPS enforcement. The fix uses the API's
computed ingress FQDN over HTTPS, avoiding dependence on HTTP redirect behavior.
It adds SNI and CA/hostname verification to both proxied locations, and overwrites
`X-Forwarded-Host` with the public request's host for API requests. The upstream
`Host` still selects the internal API correctly.

The final review added real FastAPI redirect tests and reproduced another failure:
an automatic trailing-slash redirect returned the internal `http://<api-host>/...`
URL even when forwarded headers were present. An internal HTTPS redirect used
Nginx's default redirect rewriting and included its listener port. Neither result
preserved the browser's public HTTPS origin behind TLS termination. Explicit
`proxy_redirect` rules now map only HTTP/HTTPS redirects from the configured
upstream authority to `https://<public-request-host>/...`, preserving path/query.
Redirects to unrelated external HTTPS hosts remain unchanged. No broader proxy
trust or application authentication changes were needed.

Nginx continues to listen on port 80 behind Container Apps TLS termination. There
are no changes to resource names, certificate resources, DNS, public exposure,
network rules, secret storage, or provider versions. The Terraform change updates
the web app's environment configuration; the deployed plan still needs review.

## Actual application run and additional startup failures

The current FastAPI application was run with Python 3.12.13, an isolated
PostgreSQL 16.2/pgvector 0.6.2 database, the built React/Vite frontend, and real
Nginx 1.27.5. All listeners and the scratch database bind only to loopback.
Synthetic local settings and a deterministic development LLM were used; no owner
credentials, cloud credentials, or `.env` files were used. Production continues
to reject mock LLM providers and local-disk storage.

The TLS test ingress models the existing Azure termination/routing boundary;
it is not an Azure emulator. A temporary CA is trusted only by the test client,
and both hostname and certificate verification stay enabled. The actual run
captured the following results over TLS 1.3:

| Configuration/request | Result |
| --- | --- |
| Original HTTP upstream, `/api/v1/version` | 307 to an internal-origin address |
| Original proxy with HTTPS upstream but no SNI | 502; upstream handshake reports `unrecognized name` |
| Corrected proxy, `/api/v1/version` | 200 from the real application, schema version 7 |
| Corrected proxy, `/api/v1/projects/?probe=1` | 307 to the same public HTTPS authority, preserving the query |
| Corrected proxy, `/login` | 200, built frontend served successfully |

Browser screenshots captured the actual 502 response and working login page.
The browser rendering checks used a loopback HTTP viewer of the same Nginx
configuration; HTTPS itself was checked separately with strict TLS clients.
No browser certificate validation was disabled and no machine trust store was changed.

Two additional production startup defects were reproduced and fixed:

* The API/worker startup check required a storage connection string although
  Terraform supplies a managed-identity storage account URL. It now accepts
  either existing supported method and still rejects missing blob configuration.
* The dedicated root stack never supplied `PUBLIC_BASE_URL`, although production
  API startup requires it. The stack now derives the existing web app's HTTPS
  origin from the Container Apps environment domain, with an optional explicit
  origin for a hostname that is already bound. It creates no DNS or certificate resources.

The broader test run also exposed an undefined organization variable during
answer approval, an incorrect keyword-only password-reset email call, a license
file cache that could retain old contents after an equal-size/timestamp replacement,
and deleted conversations being resurrected by late saves. Each was corrected
and covered by existing regressions or the new equal-timestamp license regression.
Test-only fixes isolate lifespan bootstrap writes in the rollback transaction,
configure synthetic production dependencies, explicitly select the existing
document-ACL mode for its tests, and remove Windows path/interpreter assumptions.
No production authorization or licensing guards were relaxed. The existing
`PRODUCT_V1` behavior and default were preserved.

References: [Container Apps ingress](https://learn.microsoft.com/en-us/azure/container-apps/ingress-overview),
[inter-app communication](https://learn.microsoft.com/en-us/azure/container-apps/connect-apps),
and [Nginx HTTPS upstream directives](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_ssl_server_name).

## Repeat local checks

With Python, backend dependencies (`cryptography`, FastAPI and its TestClient),
Nginx 1.27, and `sh`:

```sh
python -m unittest discover -s tests/infra -p test_web_https.py -v
```

If needed, set `AQREM_TEST_NGINX` and `AQREM_TEST_SHELL` to the executables' paths.
Tests generate short-lived test certificates in a temporary directory and remove
them afterwards. HTTPS clients validate the local test CA. The local TLS edge
models Container Apps termination; it does not verify Azure itself. Tests cover
SNI, public-host forwarding, request path/query preservation, both proxy locations,
HTTP compatibility, and rejection of expired, untrusted, and wrong-host certificates.
They also cover FastAPI slash redirects, internal HTTPS redirects, and preservation
of external HTTPS redirects.

With Terraform 1.11.4 and the stack's locked providers (AzureRM 4.81.0, Random 3.9.1):

```sh
terraform fmt -check infra/terraform/modules/dedicated_env/apps.tf infra/terraform/stacks/dedicated/tests/https.tftest.hcl
terraform -chdir=infra/terraform/stacks/dedicated init -backend=false
terraform -chdir=infra/terraform/stacks/dedicated validate
terraform -chdir=infra/terraform/stacks/dedicated test
```

The test explicitly uses `command = plan` with a mocked Azure provider and synthetic
inputs. Random runs locally because Terraform 1.11 does not mock ephemeral
resources. No Azure authentication, backend state, deployment, or apply is used.
The assertions check the HTTPS upstream reference, internal API, HTTPS enforcement,
public ingress forwarding to Nginx on port 80, and derived/explicit public origins.
Windows validation used a
disposable copy for platform-specific provider lock hashes; tracked lock files
were preserved.

The original proxy failed four of the initial five integration tests before the
fix. Two new redirect tests failed on `4a6cf6b` before the follow-up correction.
Final local verification (2026-10-19):

| Check | Result |
| --- | --- |
| Full backend suite, Python 3.12/PostgreSQL 16/pgvector | 680 passed, zero failed, 302 seconds |
| Frontend TypeScript/Vite production build and unit/bundle tests | Build passed; 78 tests passed across 28 files |
| Real Chromium public browser tests against the running app | 11 passed, zero failed |
| Nginx HTTPS regression integration tests | 9 passed, zero failed |
| Actual FastAPI/Nginx before/after probe | Original failures captured; corrected API/login 200 and public-origin redirect 307 over verified TLS 1.3 |
| Terraform recursive formatting and dedicated stack validation | Passed |
| Terraform plan-only mock-provider tests | 2 passed, zero failed; no Azure resources created |
| Modified production Python files: fatal/undefined-name/import checks | Passed (`ruff --select F,E9,I`) |
| Tracked/staged/history secret scan | Zero high-severity findings; synthetic development/test placeholders only |

The backend emits existing dependency deprecation warnings (8,016 warnings in
this run). Broader lint also reports existing style findings in the license
parser; neither is presented as a fully clean repository-wide lint run.

Docker Desktop could not start because Windows virtualization support is
unavailable. The test-only `https-container-validation.yml` workflow builds all
three existing images (API, worker, web), exercises the API/worker entrypoint
imports and Nginx configuration, and now runs backend tests with disposable
PostgreSQL/pgvector and Redis services on Linux. It uses no Azure credentials,
deployments, image pushes, environment approvals, or production state. The first
image validation run passed for all three components:
[run 39329389020](https://github.com/mohammedrajeb/AQREM-temp/actions/runs/39329389020).

For the full backend suite, supply only a disposable PostgreSQL/pgvector test
database, `APP_ENV=development`, `LLM_PROVIDER=mock`,
`DATABASE_URL` and `TEST_DATABASE_URL` for that database,
`PUBLIC_BASE_URL=https://testserver`, a synthetic local signing key, and a local
Redis URL. Then run:

```sh
python -m pytest tests/backend -c backend/pyproject.toml -p pytest_asyncio.plugin -q
```

`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` was set for the isolated Windows run, explicitly
loading the async plugin as shown. The fixture drops/recreates tables: never point
it at an owner or production database. `npm test` now first builds the frontend,
as its bundle regression tests require build output.

Local Redis was unavailable. Broker-failure checks still exercised that failure,
while upload tests unrelated to broker availability isolate that boundary with
their existing style of test doubles. The real local app honestly reports a
degraded broker dependency. Actual Redis-backed execution is checked by CI.
Public browser tests cover sign-in, brand/theme, named controls, focus,
registration denial, invalid invitation handling, and anonymous route guards.
Authenticated employee walkthroughs that require private QA session files were
not run; backend API tests cover authentication and tenant/ACL boundaries with
synthetic users. The shared-mode setup-status 404 observed in the browser is an
expected unavailable dedicated-only route, not a TLS failure.

## Checks still required against the deployment

A real Terraform plan needs the intended non-secret configuration, authorized
deployment access, and existing state. It was not run with invented production
values. No apply, deployment, or production DNS change was performed.

After an owner-approved rollout, verify the actual public hostname's DNS and
certificate chain/expiry, the HTTP-to-HTTPS redirect, `/health`, and
`/api/v1/version`. From inside the environment, verify the API FQDN resolves,
its TLS chain validates, and Nginx logs have no upstream handshake errors. Confirm
generated invitations use the public HTTPS origin. Live HTTPS is not verified.
