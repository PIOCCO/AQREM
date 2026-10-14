# Brevo sender domain (D16)

Configure for the platform `EMAIL_FROM_ADDRESS` domain (single shared sender; per-client URLs via `PUBLIC_BASE_URL`).

## SPF

Publish one TXT record (example):

```text
v=spf1 include:spf.brevo.com ~all
```

## DKIM

In Brevo → Domains → authenticate domain; add the CNAME/TXT records Brevo provides for selector(s).

## DMARC

Start with monitoring, tighten after SPF/DKIM pass:

```text
v=DMARC1; p=none; rua=mailto:dmarc-reports@yourdomain.example; pct=100; adkim=s; aspf=s
```

Move to `p=quarantine` then `p=reject` when confident.

## Operational

- Store `BREVO_API_KEY` only in **platform** Key Vault; Container Apps reference via secret URI + managed identity.
- Do not commit keys or DNS secrets to git.
