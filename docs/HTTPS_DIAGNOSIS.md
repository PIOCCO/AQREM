# HTTPS diagnosis and local verification

Scope: dedicated deployment on `enterprise-tenancy`, based on commit `4533da9`.
The original checkout was inspected read-only. Changes are isolated in the
temporary repository's `fix/https` branch.

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

Nginx continues to listen on port 80 behind Container Apps TLS termination. There
are no changes to resource names, certificate resources, DNS, public exposure,
network rules, secret storage, or provider versions. The Terraform change updates
the web app's environment configuration; the deployed plan still needs review.

References: [Container Apps ingress](https://learn.microsoft.com/en-us/azure/container-apps/ingress-overview),
[inter-app communication](https://learn.microsoft.com/en-us/azure/container-apps/connect-apps),
and [Nginx HTTPS upstream directives](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_ssl_server_name).

## Repeat local checks

With Python, `cryptography` (already a backend dependency), Nginx 1.27, and `sh`:

```sh
python -m unittest discover -s tests/infra -p test_web_https.py -v
```

If needed, set `AQREM_TEST_NGINX` and `AQREM_TEST_SHELL` to the executables' paths.
Tests generate short-lived test certificates in a temporary directory and remove
them afterwards. HTTPS clients validate the local test CA. The local TLS edge
models Container Apps termination; it does not verify Azure itself. Tests cover
SNI, public-host forwarding, request path/query preservation, both proxy locations,
HTTP compatibility, and rejection of expired, untrusted, and wrong-host certificates.

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
and public ingress forwarding to Nginx on port 80. Windows validation used a
disposable copy for platform-specific provider lock hashes; tracked lock files
were preserved.

Results: six Nginx HTTPS integration tests passed; one Terraform plan-only test
passed; Terraform formatting/validation, shell syntax, and staged/history secret
scans passed. The original proxy failed four of the initial five integration
tests before the fix. A Docker image build and the full database-backed
application suite were not run because the Docker daemon and test database were
unavailable. The Nginx tests exercise the actual generated proxy configuration.

## Checks still required against the deployment

A real Terraform plan needs the intended non-secret configuration, authorized
deployment access, and existing state. It was not run with invented production
values. No apply, deployment, or production DNS change was performed.

After an owner-approved rollout, verify the actual public hostname's DNS and
certificate chain/expiry, the HTTP-to-HTTPS redirect, `/health`, and
`/api/v1/version`. From inside the environment, verify the API FQDN resolves,
its TLS chain validates, and Nginx logs have no upstream handshake errors. Confirm
generated invitations use the public HTTPS origin. Live HTTPS is not verified.
