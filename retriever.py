"""
Lightweight local retriever for AURA-Lab.

Uses TF-IDF + cosine similarity (scikit-learn) over the synthetic corpus.
No API key and no large model download required. This is intentionally
simple: the object of the AI-PTF validation is the AUTHORIZATION and
INJECTION behavior around retrieval, not retrieval quality itself.
"""
import json
import os
import re
import pypdf
import piexif
import piexif.helper
import config

_SVG_TEXT_RE = re.compile(r"<(?:text|tspan|desc|title)\b[^>]*>(.*?)</(?:text|tspan|desc|title)>",
                           re.IGNORECASE | re.DOTALL)


def _extract_text(full_path):
    if full_path.endswith(".pdf"):
        reader = pypdf.PdfReader(full_path)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if full_path.endswith((".jpg", ".jpeg")):
        try:
            exif_dict = piexif.load(full_path)
            raw = exif_dict.get("Exif", {}).get(piexif.ExifIFD.UserComment)
            if raw:
                return piexif.helper.UserComment.load(raw)
        except Exception:
            pass
        return ""
    if full_path.endswith(".svg"):
        # T-20 (F8): simulate a "describe/summarize this image" ingestion
        # path that extracts the SVG's text layer rather than rendering it.
        # This is what actually makes SVG a multimodal injection vector in
        # production: a <text> element styled invisible to a human viewer
        # (fill matching the background, near-zero font-size) is still
        # ordinary text content to any text-layer extractor. We deliberately
        # do NOT read the raw XML (attribute values like fill/font-size are
        # irrelevant styling noise a real ingestion pipeline wouldn't surface
        # either) -- only the text-bearing elements, mirroring the PDF/EXIF
        # extractors above, which likewise return clean text, not markup.
        with open(full_path, "r", encoding="utf-8") as f:
            raw = f.read()
        return "\n".join(m.strip() for m in _SVG_TEXT_RE.findall(raw) if m.strip())
    with open(full_path, "r", encoding="utf-8") as f:
        return f.read()


class Corpus:
    def __init__(self):
        with open(config.MANIFEST_PATH) as f:
            self.manifest = json.load(f)
        self.docs = {}
        for entry in self.manifest:
            full_path = os.path.join(config.DOCUMENTS_DIR, entry["path"])
            if not os.path.exists(full_path):
                continue  # generated artifacts not built yet
            self.docs[entry["id"]] = {
                **entry,
                "text": _extract_text(full_path),
            }
        self._build_index()

    def _build_index(self):
        from sklearn.feature_extraction.text import TfidfVectorizer
        self.ids = list(self.docs.keys())
        corpus_texts = [self.docs[i]["text"] for i in self.ids]
        self.vectorizer = TfidfVectorizer(stop_words="english")
        self.matrix = self.vectorizer.fit_transform(corpus_texts) if corpus_texts else None

    def get(self, doc_id):
        return self.docs.get(doc_id)

    def search(self, query, role, k=None, strict_auth=None):
        """Returns list of (doc_id, score, entry) sorted by relevance.

        If strict_auth is True, documents whose role_required exceeds the
        querying user's role are excluded BEFORE ranking (secure/remediated
        behavior). If False (default / vulnerable), ALL documents are
        ranked regardless of role -- authorization is left entirely to the
        model following a system-prompt instruction, which is the bug
        behind findings F-01/F-02.
        """
        from sklearn.metrics.pairwise import cosine_similarity
        if strict_auth is None:
            strict_auth = config.STRICT_AUTH
        k = k or config.TOP_K
        if self.matrix is None:
            return []
        q_vec = self.vectorizer.transform([query])
        sims = cosine_similarity(q_vec, self.matrix)[0]
        ranked = sorted(zip(self.ids, sims), key=lambda x: x[1], reverse=True)
        results = []
        for doc_id, score in ranked:
            if score <= 1e-9:
                continue  # no real lexical overlap -- don't inject unrelated docs
            entry = self.docs[doc_id]
            if strict_auth:
                if config.ROLE_RANK[entry["role_required"]] > config.ROLE_RANK[role]:
                    continue
            results.append((doc_id, float(score), entry))
            if len(results) >= k:
                break
        return results
