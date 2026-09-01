"""
AI-PTF cross-standard mapping (thesis Appendix B, Table 10), as data so the
report generator can attach OWASP LLM Top 10 / MITRE ATLAS / NIST AI RMF
references to every finding automatically.
"""

FAMILY_INFO = {
    "F1": {"name": "Direct Prompt Injection",
           "owasp": "LLM01 Prompt Injection",
           "atlas": "ML Model Access; Craft Adversarial Data",
           "nist": "MANAGE 2.2, MEASURE 2.5"},
    "F2": {"name": "Indirect Prompt Injection",
           "owasp": "LLM01 Prompt Injection",
           "atlas": "Exfiltration via ML Inference API; Manipulate Training Data",
           "nist": "MANAGE 2.2, GOVERN 6.2"},
    "F3": {"name": "Jailbreak / Policy Bypass",
           "owasp": "LLM05 Improper Output Handling",
           "atlas": "Bypass ML Model Artefact Integrity Checks",
           "nist": "MEASURE 2.5, MANAGE 4.1"},
    "F4": {"name": "Sensitive Data Disclosure",
           "owasp": "LLM02 Sensitive Information Disclosure",
           "atlas": "Exfiltration via ML Inference API",
           "nist": "MAP 5.1, MANAGE 2.4"},
    "F5": {"name": "Improper Output Handling",
           "owasp": "LLM05 Improper Output Handling",
           "atlas": "Exploit Public-Facing Application (downstream)",
           "nist": "MEASURE 2.5, MANAGE 4.2"},
    "F6": {"name": "Model Extraction / Inference Abuse",
           "owasp": "LLM10 Unbounded Consumption",
           "atlas": "ML Model Extraction Attack",
           "nist": "MAP 5.1, MEASURE 2.6"},
    "F7": {"name": "Availability / Cost Abuse",
           "owasp": "LLM10 Unbounded Consumption",
           "atlas": "Denial of ML Service",
           "nist": "MANAGE 4.1, MAP 5.2"},
    "F8": {"name": "Multimodal Injection",
           "owasp": "LLM01 Prompt Injection (multimodal)",
           "atlas": "Craft Adversarial Data (image/audio)",
           "nist": "MANAGE 2.2, MEASURE 2.5"},
    "F9": {"name": "Supply Chain",
           "owasp": "LLM03 Supply Chain; LLM04 Data and Model Poisoning",
           "atlas": "Supply Chain Compromise (ML artefacts)",
           "nist": "GOVERN 1.4, MAP 5.2, MANAGE 3.2"},
}


def info(family):
    return FAMILY_INFO.get(family, {"name": family, "owasp": "", "atlas": "", "nist": ""})
