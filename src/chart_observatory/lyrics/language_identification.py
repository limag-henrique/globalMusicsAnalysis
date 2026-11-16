"""Deterministic, standalone language identification for lyric texts.

Identifies language from Unicode script distribution and lexical function-word
profiles, recording method and confidence without relying on thematic AI
classification.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from typing import Any

LANGUAGE_ID_VERSION = "language-id-v1-script-lexical"

_LATIN_STOPWORDS: dict[str, set[str]] = {
    "en": {
        "the", "and", "you", "that", "was", "for", "are", "with", "his", "they",
        "this", "have", "from", "not", "but", "what", "all", "were", "when", "your",
        "can", "said", "there", "will", "just", "know", "like", "yeah", "don't", "i'm",
        "you're", "it's", "my", "me", "we", "she", "he", "her", "him", "our", "out",
    },
    "es": {
        "que", "de", "no", "la", "el", "en", "y", "es", "por", "un", "una", "con",
        "para", "como", "pero", "más", "mas", "si", "ya", "te", "me", "mi", "tu",
        "yo", "eso", "esta", "estoy", "cuando", "donde", "todo", "nada", "solo", "amor",
    },
    "pt": {
        "que", "não", "nao", "de", "eu", "você", "voce", "pra", "com", "um", "uma",
        "meu", "minha", "seu", "sua", "por", "mais", "mas", "como", "isso", "aqui",
        "agora", "tudo", "nada", "vai", "vou", "tô", "to", "estou", "quando", "sem",
    },
    "fr": {
        "je", "tu", "il", "elle", "nous", "vous", "ils", "elles", "le", "la", "les",
        "un", "une", "des", "et", "est", "pas", "que", "qui", "dans", "pour", "avec",
        "sur", "mon", "ma", "mes", "ton", "ta", "tes", "tout", "rien", "mais", "c'est",
    },
    "de": {
        "ich", "du", "er", "sie", "es", "wir", "ihr", "und", "der", "die", "das",
        "ein", "eine", "nicht", "ist", "mit", "auf", "für", "von", "zu", "den", "dem",
        "wenn", "aber", "auch", "noch", "nur", "wie", "was", "mein", "dein", "dich", "mich",
    },
    "it": {
        "che", "non", "di", "la", "il", "un", "una", "per", "con", "sono", "sei",
        "mia", "mio", "tuo", "tua", "come", "quando", "tutto", "niente", "più", "ma",
        "anche", "ora", "qui", "questo", "quella", "ti", "mi", "ci", "amore", "vita",
    },
    "tr": {
        "bir", "ve", "bu", "da", "de", "ben", "sen", "o", "ne", "için", "gibi",
        "var", "yok", "ama", "çok", "her", "beni", "seni", "bana", "sana", "değil",
    },
    "id": {
        "yang", "dan", "di", "ini", "itu", "aku", "kamu", "kau", "ku", "mu", "tidak",
        "tak", "ada", "untuk", "dengan", "dari", "ke", "akan", "bisa", "cinta", "hati",
    },
    "nl": {
        "ik", "jij", "je", "hij", "zij", "wij", "en", "de", "het", "een", "van",
        "niet", "dat", "dit", "wat", "met", "voor", "maar", "als", "naar", "mijn",
    },
    "pl": {
        "nie", "się", "sie", "w", "na", "i", "z", "do", "to", "jest", "jak", "co",
        "ale", "za", "od", "po", "tak", "już", "juz", "ty", "ja", "mnie", "ciebie",
    },
    "sv": {
        "jag", "du", "han", "hon", "vi", "och", "det", "att", "som", "en", "ett",
        "är", "inte", "för", "med", "på", "till", "av", "om", "men", "min", "din",
    },
    "fi": {
        "ja", "ei", "on", "se", "että", "oli", "kun", "niin", "mutta", "minä",
        "sinä", "mä", "sä", "ole", "vain", "kaikki", "nyt", "jos", "kanssa",
    },
    "ro": {
        "și", "si", "în", "in", "cu", "de", "la", "nu", "ce", "pe", "care", "să",
        "sa", "un", "o", "eu", "tu", "el", "ea", "pentru", "dar", "când", "tot",
    },
    "vi": {
        "và", "là", "của", "anh", "em", "không", "có", "trong", "cho", "những",
        "người", "tôi", "mình", "khi", "đã", "đến", "với", "như", "này", "yêu",
    },
    "tl": {
        "ang", "ng", "sa", "na", "at", "ay", "ko", "mo", "ako", "ikaw", "ka",
        "hindi", "di", "mga", "kung", "para", "lang", "naman", "mahal", "puso",
    },
}

_DIACRITIC_HINTS: dict[str, set[str]] = {
    "pt": set("ãõçáéíóúâêôà"),
    "es": set("ñ¿¡áéíóúü"),
    "fr": set("àâçéèêëîïôùûüÿœæ"),
    "de": set("äöüß"),
    "it": set("àèéìíîòóùú"),
    "tr": set("çğıİöşü"),
    "pl": set("ąćęłńóśźż"),
    "sv": set("åäö"),
    "fi": set("äö"),
    "ro": set("ăâîșşțţ"),
    "vi": set("ăâđêôơưàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ"),
}

_NON_LATIN_SCRIPT_MAP: dict[str, str] = {
    "HANGUL": "ko",
    "HIRAGANA": "ja",
    "KATAKANA": "ja",
    "CYRILLIC": "ru",
    "ARABIC": "ar",
    "DEVANAGARI": "hi",
    "THAI": "th",
    "GREEK": "el",
    "HEBREW": "he",
    "BENGALI": "bn",
    "TAMIL": "ta",
    "TELUGU": "te",
    "GEORGIAN": "ka",
    "ARMENIAN": "hy",
}

_TOKEN_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿĀ-žḀ-ỿ']+")


def _char_script(ch: str) -> str | None:
    if not ch.isalpha():
        return None
    name = unicodedata.name(ch, "")
    if "HANGUL" in name:
        return "HANGUL"
    if "HIRAGANA" in name:
        return "HIRAGANA"
    if "KATAKANA" in name:
        return "KATAKANA"
    if "CJK UNIFIED" in name or "CJK COMPATIBILITY" in name:
        return "CJK"
    if "LATIN" in name:
        return "LATIN"
    for key in _NON_LATIN_SCRIPT_MAP:
        if key in name:
            return key
    return "OTHER"


def identify_language(
    text: str | None,
    *,
    source_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Identify lyric language deterministically with method and confidence."""
    if not text or not text.strip():
        return {
            "language_code": "und",
            "confidence": 0.0,
            "method": LANGUAGE_ID_VERSION,
            "script": "none",
            "reason": "empty_text",
        }

    # Strip section headers like [Verse 1], [Chorus], etc.
    cleaned = re.sub(r"\[[^\]]{1,60}\]", " ", text)
    scripts: Counter[str] = Counter()
    for ch in cleaned:
        sc = _char_script(ch)
        if sc:
            scripts[sc] += 1

    total_alpha = sum(scripts.values())
    if total_alpha < 12:
        return {
            "language_code": "und",
            "confidence": 0.0,
            "method": LANGUAGE_ID_VERSION,
            "script": "insufficient",
            "reason": "too_few_alphabetic_chars",
        }

    # Japanese uses Kana + CJK; Korean uses Hangul; Chinese uses CJK without Kana.
    kana_count = scripts["HIRAGANA"] + scripts["KATAKANA"]
    if kana_count >= 5 or (kana_count > 0 and scripts["CJK"] > 0 and kana_count / total_alpha >= 0.05):
        conf = round(min(0.99, (kana_count + scripts["CJK"]) / total_alpha), 4)
        return {
            "language_code": "ja",
            "confidence": conf,
            "method": LANGUAGE_ID_VERSION,
            "script": "JAPANESE",
            "reason": "kana_script_detected",
        }
    if scripts["CJK"] / total_alpha >= 0.4:
        return {
            "language_code": "zh",
            "confidence": round(min(0.98, scripts["CJK"] / total_alpha), 4),
            "method": LANGUAGE_ID_VERSION,
            "script": "CJK",
            "reason": "cjk_without_kana",
        }

    top_script, top_count = scripts.most_common(1)[0]
    if top_script in _NON_LATIN_SCRIPT_MAP and top_count / total_alpha >= 0.4:
        return {
            "language_code": _NON_LATIN_SCRIPT_MAP[top_script],
            "confidence": round(min(0.99, top_count / total_alpha), 4),
            "method": LANGUAGE_ID_VERSION,
            "script": top_script,
            "reason": "non_latin_script_majority",
        }

    tokens = [tok.lower() for tok in _TOKEN_RE.findall(cleaned)]
    if len(tokens) < 6:
        return {
            "language_code": "und",
            "confidence": 0.0,
            "method": LANGUAGE_ID_VERSION,
            "script": top_script,
            "reason": "too_few_tokens",
        }

    token_counts = Counter(tokens)
    diacritic_chars = {ch.lower() for ch in cleaned if ord(ch) > 127 and ch.isalpha()}
    scores: dict[str, float] = {}
    for lang, sw in _LATIN_STOPWORDS.items():
        hits = sum(token_counts[w] for w in sw if w in token_counts)
        ratio = hits / len(tokens)
        d_bonus = 0.0
        hints = _DIACRITIC_HINTS.get(lang)
        if hints and diacritic_chars:
            overlap = len(diacritic_chars & hints)
            d_bonus = min(0.08, overlap * 0.02)
        scores[lang] = ratio + d_bonus

    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    best_lang, best_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0
    if best_score < 0.08:
        return {
            "language_code": "und",
            "confidence": round(best_score, 4),
            "method": LANGUAGE_ID_VERSION,
            "script": "LATIN",
            "reason": "low_stopword_coverage",
        }
    margin = max(0.0, best_score - second_score)
    confidence = round(min(0.99, 0.5 + min(0.49, margin * 2.5 + best_score * 0.4)), 4)
    return {
        "language_code": best_lang,
        "confidence": confidence,
        "method": LANGUAGE_ID_VERSION,
        "script": "LATIN",
        "reason": "lexical_stopword_and_diacritic_profile",
    }
