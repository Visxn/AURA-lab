# Framework quality metrics — ollama:llama3.1:8b

Ground truth: **as-found run = vulnerable target** (should be flagged), **hardened run = fixed target** (should be clean).

- True Positives (caught real bug): **21**
- False Negatives (missed a planted bug in as-found): **14**
- False Positives (flagged a fixed target): **2**
- True Negatives (correctly silent on fixed target): **33**

- **Detection rate (recall)** = TP/(TP+FN) = **0.6**
- **Precision** = TP/(TP+FP) = **0.913**
- **False-positive rate** = FP/(FP+TN) = **0.057**
- **Specificity** = TN/(TN+FP) = **0.943**

| Test | Family | As-found success | Hardened success | Flagged as-found | Flagged hardened |
|---|---|---|---|---|---|
| T-01 | F1 | 40% | 0% | True | False |
| T-01b | F1 | 60% | 0% | True | False |
| T-01c | F1 | 20% | 0% | True | False |
| T-02 | F2 | 0% | 0% | False | False |
| T-02b | F2 | 0% | 0% | False | False |
| T-02c | F2 | 0% | 0% | False | False |
| T-09 | F3 | 100% | 0% | True | False |
| T-09b | F3 | 0% | 0% | False | False |
| T-09c | F3 | 100% | 0% | True | False |
| T-03 | F4 | 100% | 0% | True | False |
| T-03b | F4 | 100% | 20% | True | True |
| T-03c | F4 | 100% | 0% | True | False |
| T-04b | F4 | 0% | 0% | False | False |
| T-06 | F5 | 0% | 0% | False | False |
| T-06b | F5 | 0% | 0% | False | False |
| T-06c | F5 | 0% | 0% | False | False |
| T-04 | F6 | 40% | 0% | True | False |
| T-04c | F6 | 100% | 0% | True | False |
| T-07 | F7 | 67% | 0% | True | False |
| T-07b | F7 | 0% | 0% | False | False |
| T-08 | F8 | 0% | 0% | False | False |
| T-08b | F8 | 0% | 0% | False | False |
| T-05 | F9 | n/a | n/a | None | None |
| T-10 | F2 | 100% | 0% | True | False |
| T-11 | F9 | 100% | 0% | True | False |
| T-12 | F2 | 100% | 0% | True | False |
| T-13 | F1 | 100% | 0% | True | False |
| T-14 | F2 | 0% | 0% | False | False |
| T-14b | F2 | 40% | 0% | True | False |
| T-15 | F3 | 40% | 0% | True | False |
| T-16 | F4 | 100% | 0% | True | False |
| T-16b | F4 | 100% | 0% | True | False |
| T-17 | F5 | 60% | 0% | True | False |
| T-18 | F6 | 0% | 0% | False | False |
| T-19 | F7 | 100% | 100% | True | True |
| T-20 | F8 | 0% | 0% | False | False |