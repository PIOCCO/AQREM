# RAG model evaluation set (provisional)

Before locking **`gpt-4.1-mini`** in production, run this **20-question** set against each candidate (e.g. `gpt-4.1-mini`, `gpt-4.1-nano`, `gpt-4o-mini` if still available) via the **same gateway aliases** and measure:

- Answer correctness (human 0/1)
- Citation present when required (0/1)
- Latency p95
- Prompt + completion tokens (cost)

| # | Question (employee-style) | Expected citation behavior |
|---|---------------------------|----------------------------|
| 1 | What is our remote work policy for hybrid days? | Must cite HR policy doc |
| 2 | Who approves expenses over €500? | Finance policy section |
| 3 | Summarize onboarding steps for new hires in engineering. | Onboarding handbook |
| 4 | What PPE is required in the warehouse? | Safety manual |
| 5 | When does the ISO audit start this year? | Quality calendar doc |
| 6 | Are customers allowed to request full data export? | Privacy / GDPR doc |
| 7 | What is the escalation path for IT outages? | IT runbook |
| 8 | How long is parental leave? | HR benefits |
| 9 | Which vendors are approved for cloud hosting? | Vendor list |
| 10 | What is the password rotation requirement? | Security policy |
| 11 | Can I use personal email for work announcements? | Acceptable use policy |
| 12 | Where is the fire assembly point? | Site plan / safety |
| 13 | What defines a confidential document? | Data classification guide |
| 14 | How do I report a phishing email? | Security awareness doc |
| 15 | What are standard payment terms for invoices? | AP policy |
| 16 | Is there a bring-your-own-device policy? | IT policy |
| 17 | Who is the DPO contact? | Privacy notice |
| 18 | What training is mandatory annually? | Compliance training list |
| 19 | How are customer support SLAs defined? | Support handbook |
| 20 | What happens to data when a project closes? | Records retention policy |

Store golden answers + doc/page references in `evals/rag/` (future CI job). Reject any model whose **Learn retirement date** is within **12 months** of go-live.
