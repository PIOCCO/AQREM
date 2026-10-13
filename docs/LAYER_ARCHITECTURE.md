# AQREM three-layer architecture (trust boundaries)

```mermaid
flowchart TB
  subgraph public["Public edge"]
    L3["L3 Employee chat / RAG\n/chat, /api/v1/chat, evidence, …"]
    L2["L2 Customer admin\n/admin, /api/v1/org-admin"]
  end

  subgraph restricted["Restricted edge"]
    L1["L1 Platform master\n/master-admin, /api/v1/admin, /api/v1/master"]
  end

  subgraph identity["Identity"]
    IdP["JWT issuer\n/login, /accept-invitation"]
  end

  subgraph data["Data plane (tenant scoped)"]
    PG[(PostgreSQL\norgs, memberships, evidence, audit)]
    Blob[(Blob storage\nclient documents)]
    Idx[(Vector index\npgvector per org)]
  end

  subgraph secrets["Secrets"]
    KV[(Key Vault / memory store\nmodel tokens only)]
  end

  IdP -->|aud: aqrem-employee| L3
  IdP -->|aud: aqrem-org-admin| L2
  IdP -->|aud: aqrem-master| L1

  L2 -->|upload| Blob
  L2 -->|write token| KV
  L2 -->|allow-listed telemetry| PG
  L1 -->|provision metadata| PG
  L1 -->|license PATCH| PG

  L3 -->|retrieve organization_id| Idx
  L3 -->|read| PG
  Worker -->|index| Idx
  Worker -->|read blob| Blob

  L3 -.->|LLM today: global config| LLM[(Model API)]
  KV -.->|not wired to chat yet| LLM

  classDef boundary stroke:#c00,stroke-width:2px
  class L1,L2,L3 boundary
```

**Crosses trust boundary (allowed):** license metadata, seat counts, health/version, credential expiry date (no secret), setup flags.

**Must not cross:** document text, questions, answers, raw tokens, embeddings content to L1.
