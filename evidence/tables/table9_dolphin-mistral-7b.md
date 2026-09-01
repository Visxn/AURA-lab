### Table 9 — Coverage analysis (dolphin-mistral:7b)

| Family | AI-PTF name | Tests | Auto-tested | Coverage | Notes |
|---|---|---|---|---|---|
| F1 | Direct Prompt Injection | 4 | 4 | Full | 3/4 auto-tests fired |
| F2 | Indirect Prompt Injection | 7 | 7 | Full | 1/7 auto-tests fired |
| F3 | Jailbreak / Policy Bypass | 4 | 4 | Full | 3/4 auto-tests fired |
| F4 | Sensitive Data Disclosure | 6 | 6 | Full | 6/6 auto-tests fired |
| F5 | Improper Output Handling | 4 | 4 | Full | 4/4 auto-tests fired |
| F6 | Model Extraction / Inference Abuse | 3 | 3 | Full | 2/3 auto-tests fired |
| F7 | Availability / Cost Abuse | 3 | 3 | Full | 1/3 auto-tests fired |
| F8 | Multimodal Injection | 3 | 3 | Full | 1/3 auto-tests fired |
| F9 | Supply Chain | 2 | 1 | Full + manual | 1/1 auto-tests fired; 1 manual |