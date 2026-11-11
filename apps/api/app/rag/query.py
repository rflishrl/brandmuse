import re

BRAND_SYNONYM_MAP: dict[str, list[str]] = {
    # Indonesian & colloquial keywords to guideline domain terminology
    "warna": ["color", "palette", "hex"],
    "primer": ["primary"],
    "sekunder": ["secondary"],
    "aksen": ["accent"],
    "huruf": ["typography", "font", "typeface"],
    "tulisan": ["typography", "font"],
    "font": ["typography", "typeface"],
    "suara": ["tone", "voice"],
    "nada": ["tone", "voice"],
    "gaya": ["style", "voice"],
    "aturan": ["guidelines", "rules", "standards"],
    "larangan": ["restrictions", "prohibited", "donts"],
    "pantangan": ["restrictions", "prohibited"],
    "bolehkah": ["permitted", "allowed"],
    "bisakah": ["permitted", "allowed"],
    "gambar": ["imagery", "photography"],
    "foto": ["photography", "imagery"],
    "lambang": ["logo", "mark", "symbol"],
    "logo": ["logo", "mark", "clearspace"],
    "jarak": ["clearspace", "spacing", "margin"],
    "spasi": ["spacing", "clearspace"],
    "kontras": ["contrast", "accessibility"],
    "latar": ["background"],
    "belakang": ["background"],
}

STOP_WORDS: set[str] = {
    "apa",
    "apakah",
    "bagaimana",
    "mengapa",
    "kenapa",
    "siapa",
    "di",
    "ke",
    "dari",
    "pada",
    "dalam",
    "untuk",
    "dengan",
    "dan",
    "atau",
    "yang",
    "ini",
    "itu",
    "ada",
    "adalah",
    "bisa",
    "dapat",
    "tolong",
    "mohon",
    "coba",
    "sebutkan",
    "jelaskan",
    "what",
    "how",
    "why",
    "when",
    "where",
    "who",
    "which",
    "is",
    "are",
    "can",
    "could",
    "would",
    "should",
    "tell",
    "me",
    "about",
    "please",
    "the",
    "a",
    "an",
}


def expand_query_for_retrieval(query_text: str) -> str:
    """Expand user query with domain-specific brand vocabulary for enhanced semantic vector search.

    Keeps the original query intact while appending relevant domain keywords to ensure
    cross-lingual and colloquial questions align closely with English guideline embeddings.
    """
    clean_text = query_text.strip()
    if not clean_text:
        return query_text

    tokens = re.findall(r"\b\w+\b", clean_text.lower())
    expanded_terms: list[str] = []

    for token in tokens:
        if token in BRAND_SYNONYM_MAP:
            for mapped in BRAND_SYNONYM_MAP[token]:
                if mapped not in tokens and mapped not in expanded_terms:
                    expanded_terms.append(mapped)

    if not expanded_terms:
        return clean_text

    return f"{clean_text} ({' '.join(expanded_terms[:4])})"


def build_fts_query_expression(query_text: str) -> str:
    """Build an optimized search expression for Postgres websearch_to_tsquery.

    Extracts high-signal content words and maps colloquial or Indonesian brand
    terms into 'OR' disjunctions so that English guidelines match even when
    the user's phrasing is informal or multilingual.
    """
    clean_text = query_text.strip()
    if not clean_text:
        return query_text

    tokens = re.findall(r"\b\w+\b", clean_text.lower())
    if not tokens:
        return clean_text

    content_terms: list[str] = []
    synonym_terms: list[str] = []

    for token in tokens:
        if token in BRAND_SYNONYM_MAP:
            for s in BRAND_SYNONYM_MAP[token]:
                if s not in synonym_terms:
                    synonym_terms.append(s)
        elif token not in STOP_WORDS and len(token) > 2:
            if token not in content_terms:
                content_terms.append(token)

    merged = content_terms + synonym_terms
    if not merged:
        return clean_text

    # Use OR disjunction across the top high-signal terms (up to 5)
    return " or ".join(merged[:5])
