### Cross-model comparison (attack success rate by family)

| Family | llama3.1:8b (strong) | mistral:7b (medium) | dolphin-mistral:7b (none(uncensored)) |
|---|---|---|---|
| F1 | 55% | 60% | 55% |
| F2 | 34% | 3% | 3% |
| F3 | 60% | 75% | 75% |
| F4 | 83% | 100% | 87% |
| F5 | 15% | 60% | 70% |
| F6 | 47% | 53% | 53% |
| F7 | 56% | 0% | 33% |
| F8 | 0% | 0% | 7% |
| F9 | 100% | 20% | 80% |

### Framework quality per model (as-found vs hardened)

| Model | Guardrail | Detection rate | Precision | False-positive rate |
|---|---|---|---|---|
| llama3.1:8b | strong | 0.6 | 0.913 | 0.057 |
| mistral:7b | medium | 0.543 | 0.905 | 0.057 |
| dolphin-mistral:7b | none(uncensored) | 0.629 | 0.88 | 0.086 |