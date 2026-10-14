# Infra vs product PR strategy

## What `cursor/chatgpt-ui-redesign-81ca` contains vs `main`

| Branch | Contents (as of 2026-10-14) |
|--------|-----------------------------|
| **`main`** | Initial commit only (`README.md`) — not a deployable product tree. |
| **`cursor/chatgpt-ui-redesign-81ca`** | Full AQREM product: backend API, worker, frontend (ChatGPT-style UI), tests, docs — **~461 files** vs `main`. |

Infra branches (`cursor/azure-platform-stage1/2/3-81ca`) were cut from **`cursor/chatgpt-ui-redesign-81ca`**, not from `main`. They add `infra/terraform`, `infra/model-gateway`, platform DB migrations, and GitHub workflows on top of that product tip (and include a few mixed app fixes that landed on the same line).

## Separate PRs

- **Infra PR:** base **`main`** once `main` contains the shared backend (or base a long-lived **`develop`**), head `cursor/azure-platform-stage3-81ca`, paths mostly `infra/**`, `.github/workflows/*platform*`, `bootstrap-control-plane-db`, etc.
- **Product / Stage 4 PR:** base **`main`** (or product trunk), head `cursor/azure-app-stage4-81ca`, paths `backend/**`, `worker/**`, `docs/azure/**` — **no** `frontend/**` UI changes for Stage 4.

## Rebase infra onto `main` without UI work

**Today:** rebasing infra directly onto `main` would drop the entire application tree (only README on `main`). **Recommended:**

1. Merge or fast-forward **`main`** to a **backend-only** tag/commit from `chatgpt-ui-redesign` (or split a `product-core` branch without frontend), **or**
2. Rebase infra onto that core branch, **or**
3. Keep infra PR targeting `chatgpt-ui-redesign` temporarily and retarget to `main` after `main` catches up.

Infra does **not** require ChatGPT UI files to run Terraform; it only requires consistent client stack env names that Stage 4 implements in the API.
