"""
nlp_extractor.py
Ekstraksi struktur semantik kalimat kebutuhan menggunakan NLP berbasis aturan.
Menggantikan spaCy dengan implementasi pure-Python yang mencakup:
  - Tokenisasi & normalisasi
  - Deteksi modalitas (MUST / CAN / SHOULD / MUST_NOT / CANNOT)
  - Deteksi negasi
  - Ekstraksi subjek, aksi (verb phrase), dan objek
  - Deteksi kondisi (JIKA / APABILA / KECUALI / IF / UNLESS / WHEN)
  - Normalisasi teks (stemming Bahasa Indonesia sederhana)
"""

import re
from owl_ontology import (
    RequirementIndividual, Modality, ConditionType
)

# ── Kamus Linguistik ──────────────────────────────────────────────────────────

# Kata modalitas → enum Modality
MODAL_KEYWORDS: dict[str, Modality] = {
    # Bahasa Indonesia
    "harus": Modality.MUST,
    "wajib": Modality.MUST,
    "perlu": Modality.MUST,
    "harus dapat": Modality.MUST,
    "harus bisa": Modality.MUST,
    "dapat": Modality.CAN,
    "bisa": Modality.CAN,
    "mampu": Modality.CAN,
    "diperbolehkan": Modality.CAN,
    "boleh": Modality.CAN,
    "sebaiknya": Modality.SHOULD,
    "seharusnya": Modality.SHOULD,
    "diharapkan": Modality.SHOULD,
    "dilarang": Modality.MUST_NOT,
    "tidak boleh": Modality.MUST_NOT,
    "tidak diperbolehkan": Modality.MUST_NOT,
    "tidak dapat": Modality.CANNOT,
    "tidak bisa": Modality.CANNOT,
    "tidak mampu": Modality.CANNOT,
    # Bahasa Inggris (RFC 2119)
    "must": Modality.MUST,
    "shall": Modality.MUST,
    "required": Modality.MUST,
    "should": Modality.SHOULD,
    "may": Modality.CAN,
    "can": Modality.CAN,
    "must not": Modality.MUST_NOT,
    "shall not": Modality.MUST_NOT,
    "cannot": Modality.CANNOT,
    "can not": Modality.CANNOT,
}

# Kata negasi
NEGATION_WORDS = {
    "tidak", "bukan", "jangan", "tanpa", "tidak boleh",
    "tidak dapat", "tidak bisa", "tidak diperbolehkan",
    "not", "never", "no", "cannot", "don't", "doesn't",
}

# Pola kondisi
CONDITION_TRIGGERS = {
    "jika", "apabila", "bila", "ketika", "saat", "kecuali",
    "jika tidak", "kecuali jika", "selama", "asalkan", "dengan syarat",
    "if", "when", "unless", "except", "provided", "as long as",
    "given that", "in case",
}

# Kata stopword (untuk normalisasi objek/subjek)
STOPWORDS = {
    "yang", "dengan", "dari", "ke", "di", "untuk", "oleh",
    "dan", "atau", "karena", "sehingga", "agar", "maka",
    "the", "a", "an", "of", "in", "for", "to", "by", "is", "are",
}

# Kata subjek sistem (entitas yang sering jadi subjek)
SYSTEM_SUBJECTS = {
    "sistem", "aplikasi", "platform", "website", "web", "app",
    "server", "database", "modul", "fitur", "layanan", "service",
    "program", "software", "perangkat lunak", "system",
}

# Kata entitas khusus domain akademik
ACADEMIC_ENTITIES = {
    "siswa", "mahasiswa", "peserta", "dosen", "guru", "instruktur",
    "admin", "administrator", "pengguna", "user", "student",
    "teacher", "lecturer", "presensi", "absensi", "kehadiran",
    "ujian", "exam", "test", "quiz", "nilai", "grade", "fitur",
    "feature", "akses", "access", "izin", "permission",
}


# ── Tokenizer ─────────────────────────────────────────────────────────────────

def tokenize(text: str) -> list[str]:
    """Tokenisasi sederhana: lowercase → split by whitespace & punctuation."""
    text = text.lower().strip()
    # Pertahankan tanda hubung antar kata (mis: "tidak-boleh" → "tidak boleh")
    text = text.replace("-", " ")
    # Hapus tanda baca di awal/akhir kata kecuali di tengah
    tokens = re.findall(r"[a-zA-Z0-9]+(?:['''][a-zA-Z]+)?", text)
    return tokens


def normalize(word: str) -> str:
    """
    Stemming ringan Bahasa Indonesia.
    Hapus prefix: me-, ber-, ke-, ter-, pe-, di-
    Hapus suffix: -kan, -an, -i, -nya
    """
    prefixes = ["meng", "meny", "mem", "men", "me",
                "peng", "peny", "pem", "pen", "pe",
                "ber", "ter", "ke", "di", "se"]
    suffixes = ["kan", "an", "nya", "i"]

    w = word.lower()
    for p in prefixes:
        if w.startswith(p) and len(w) > len(p) + 2:
            w = w[len(p):]
            break
    for s in suffixes:
        if w.endswith(s) and len(w) > len(s) + 2:
            w = w[:-len(s)]
            break
    return w


# ── Deteksi Modalitas ─────────────────────────────────────────────────────────

def detect_modality(text: str) -> tuple[Modality, bool]:
    """
    Deteksi modalitas dan negasi dari teks kalimat.
    Returns: (Modality, is_negated)
    """
    lower = text.lower()

    # Cek frasa multi-kata dulu (lebih panjang lebih spesifik)
    sorted_modals = sorted(MODAL_KEYWORDS.keys(), key=len, reverse=True)
    for phrase in sorted_modals:
        if phrase in lower:
            mod = MODAL_KEYWORDS[phrase]
            is_negated = (mod in (Modality.MUST_NOT, Modality.CANNOT))
            return mod, is_negated

    # Cek negasi terpisah
    neg_found = any(neg in lower for neg in NEGATION_WORDS)
    return Modality.MUST, neg_found  # default jika tidak ada modal eksplisit


# ── Deteksi Kondisi ───────────────────────────────────────────────────────────

def detect_condition(text: str) -> tuple[ConditionType, str]:
    """
    Deteksi apakah kalimat memiliki kondisi/syarat.
    Returns: (ConditionType, condition_text)
    """
    lower = text.lower()

    # Kondisi pengecualian
    exception_words = {"kecuali", "kecuali jika", "unless", "except"}
    for word in exception_words:
        if word in lower:
            idx = lower.find(word)
            cond_text = text[idx:].strip()
            return ConditionType.EXCEPTION, cond_text

    # Kondisi biasa (jika/apabila/if/when)
    condition_words = ["jika", "apabila", "bila", "ketika", "saat",
                       "asalkan", "dengan syarat", "selama",
                       "if", "when", "provided", "as long as",
                       "given that", "in case"]
    for word in sorted(condition_words, key=len, reverse=True):
        if word in lower:
            idx = lower.find(word)
            cond_text = text[idx:].strip()
            return ConditionType.CONDITIONAL, cond_text

    return ConditionType.UNCONDITIONAL, ""


# ── Ekstraksi Subjek ──────────────────────────────────────────────────────────

def extract_subject(tokens: list[str], text: str) -> str:
    """
    Ekstrak subjek dari kalimat kebutuhan.
    Heuristic: cari kata sistem/aktor di awal kalimat.
    """
    lower_text = text.lower()

    # Cek apakah ada kata subjek sistem di awal kalimat (15 kata pertama)
    first_part = " ".join(tokens[:15])
    for subj in sorted(SYSTEM_SUBJECTS, key=len, reverse=True):
        if subj in first_part:
            return subj

    # Cari entitas akademik sebagai subjek
    for entity in sorted(ACADEMIC_ENTITIES, key=len, reverse=True):
        if entity in first_part:
            return entity

    # Fallback: token pertama
    return tokens[0] if tokens else "sistem"


# ── Ekstraksi Aksi (Verb Phrase) ─────────────────────────────────────────────

COMMON_VERBS = {
    "mengunci", "membuka", "menutup", "mengizinkan", "memblokir",
    "menampilkan", "menyembunyikan", "mengirim", "menerima",
    "memproses", "menyimpan", "menghapus", "memperbarui", "membuat",
    "mengakses", "mengaktifkan", "menonaktifkan", "memberikan",
    "memvalidasi", "memeriksa", "menghitung", "mendeteksi",
    "kunci", "buka", "tutup", "izin", "blokir", "tampil",
    "lock", "unlock", "open", "close", "allow", "block", "permit",
    "display", "hide", "send", "receive", "process", "save",
    "delete", "update", "create", "access", "activate", "deactivate",
}

def extract_action(tokens: list[str], text: str) -> str:
    """Ekstrak frasa aksi (verb phrase) dari kalimat."""
    lower_text = text.lower()

    for verb in sorted(COMMON_VERBS, key=len, reverse=True):
        if verb in lower_text:
            return verb

    # Fallback: cari token setelah kata modal
    modal_pos = -1
    modal_words_flat = ["harus", "dapat", "bisa", "wajib", "boleh",
                        "must", "can", "should", "may"]
    for i, tok in enumerate(tokens):
        if tok in modal_words_flat:
            modal_pos = i
            break

    if modal_pos >= 0 and modal_pos + 1 < len(tokens):
        return tokens[modal_pos + 1]

    return tokens[1] if len(tokens) > 1 else "aksi"


# ── Ekstraksi Objek ───────────────────────────────────────────────────────────

def extract_object(tokens: list[str], text: str) -> str:
    """
    Ekstrak objek utama (fitur/resource yang dikenai aksi).
    Prioritas: entitas domain akademik.
    """
    lower_text = text.lower()

    # Prioritas entitas akademik/domain
    for entity in sorted(ACADEMIC_ENTITIES, key=len, reverse=True):
        if entity in lower_text:
            return entity

    # Ambil noun phrase setelah verb (heuristik sederhana)
    # Cari token setelah verb yang bukan stopword
    verb_found = False
    for tok in tokens:
        if verb_found and tok not in STOPWORDS and len(tok) > 2:
            return tok
        if tok in {normalize(v) for v in COMMON_VERBS}:
            verb_found = True

    return tokens[-1] if tokens else "objek"


# ── Main Extractor ────────────────────────────────────────────────────────────

def extract_requirement(text: str, index: int) -> RequirementIndividual:
    """
    Pipeline utama ekstraksi NLP → RequirementIndividual (OWL Individual).
    
    Tahapan:
    1. Tokenisasi & normalisasi
    2. Deteksi modalitas + negasi
    3. Deteksi kondisi
    4. Ekstraksi subjek, aksi, objek
    5. Construct OWL Individual
    """
    tokens = tokenize(text)
    modality, is_negated = detect_modality(text)
    condition_type, condition_text = detect_condition(text)
    subject = extract_subject(tokens, text)
    action = extract_action(tokens, text)
    obj = extract_object(tokens, text)

    return RequirementIndividual(
        index=index,
        text=text,
        subject=subject,
        action=action,
        obj=obj,
        modality=modality,
        is_negated=is_negated,
        condition_type=condition_type,
        condition_text=condition_text,
        raw_tokens=tokens,
    )


# ── Utilitas Normalisasi Teks untuk Perbandingan ─────────────────────────────

def get_normalized_tokens(req: RequirementIndividual) -> set[str]:
    """Kembalikan set token ternormalisasi dari sebuah kebutuhan (untuk similarity)."""
    result = set()
    for tok in req.raw_tokens:
        if tok not in STOPWORDS and len(tok) > 2:
            result.add(normalize(tok))
    return result


def jaccard_similarity(set_a: set, set_b: set) -> float:
    """Hitung Jaccard similarity antara dua set token."""
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)
