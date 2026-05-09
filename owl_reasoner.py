"""
owl_reasoner.py
OWL2 Reasoner untuk mendeteksi inkonsistensi antar kebutuhan sistem.

Mengimplementasikan aturan inkonsistensi berbasis OWL2 axioms:
  1. OBLIGATE vs PROHIBIT  → Kontradiksi Langsung
  2. OBLIGATE vs PROHIBIT (conditional) → Kontradiksi Bersyarat
  3. PERMIT + CONDITIONAL vs PROHIBIT + UNCONDITIONAL → Inkonsistensi Cakupan
  4. Duplikasi semantik → Redundansi
  5. Melemah tanpa alasan → Inkonsistensi Kekuatan Modal
"""

from dataclasses import dataclass
from owl_ontology import (
    RequirementIndividual, InconsistencyAxiom,
    Modality, ConditionType, RequirementsOntology
)
from nlp_extractor import (
    get_normalized_tokens, jaccard_similarity, normalize,
    ACADEMIC_ENTITIES, SYSTEM_SUBJECTS
)

# ── Kamus Aksi Antonim (aksi yang berlawanan secara semantik) ─────────────────
ANTONYM_ACTIONS: list[tuple[set, set]] = [
    ({"mengunci", "kunci", "lock", "tutup", "menutup", "blokir", "memblokir",
      "nonaktif", "menonaktifkan", "larang", "melarang", "batasi", "membatasi"},
     {"membuka", "buka", "unlock", "open", "aktif", "mengaktifkan",
      "izinkan", "mengizinkan", "boleh", "perbolehkan", "memperbolehkan",
      "akses", "mengakses"}),
    ({"tambah", "menambah", "buat", "membuat", "create", "insert"},
     {"hapus", "menghapus", "delete", "remove"}),
    ({"tampil", "menampilkan", "show", "display"},
     {"sembunyikan", "menyembunyikan", "hide", "conceal"}),
    ({"aktifkan", "mengaktifkan", "enable"},
     {"nonaktifkan", "menonaktifkan", "disable"}),
    ({"simpan", "menyimpan", "save"},
     {"hapus", "menghapus", "delete"}),
    ({"terima", "menerima", "accept", "approve"},
     {"tolak", "menolak", "reject", "deny"}),
]


def has_antonym_action(a: RequirementIndividual,
                        b: RequirementIndividual) -> bool:
    """Cek apakah dua kebutuhan memiliki aksi yang berlawanan (antonim)."""
    action_a = normalize(a.action).lower()
    action_b = normalize(b.action).lower()

    # Cek juga raw tokens untuk aksi multi-kata
    tokens_a = set(a.raw_tokens)
    tokens_b = set(b.raw_tokens)

    for group1, group2 in ANTONYM_ACTIONS:
        norm_g1 = {normalize(w) for w in group1} | group1
        norm_g2 = {normalize(w) for w in group2} | group2

        in_g1_a = (action_a in norm_g1 or bool(tokens_a & norm_g1))
        in_g2_b = (action_b in norm_g2 or bool(tokens_b & norm_g2))
        in_g2_a = (action_a in norm_g2 or bool(tokens_a & norm_g2))
        in_g1_b = (action_b in norm_g1 or bool(tokens_b & norm_g1))

        if (in_g1_a and in_g2_b) or (in_g2_a and in_g1_b):
            return True
    return False


# ── Threshold ─────────────────────────────────────────────────────────────────
SIMILARITY_THRESHOLD = 0.30   # Jaccard min untuk dianggap membicarakan topik sama
HIGH_SIM_THRESHOLD   = 0.60   # Threshold untuk redundansi


# ── Kamus Label ───────────────────────────────────────────────────────────────

CONFLICT_TYPE_LABELS = {
    "DIRECT_CONTRADICTION": "Kontradiksi Langsung",
    "CONDITIONAL_CONTRADICTION": "Kontradiksi Bersyarat",
    "SCOPE_INCONSISTENCY": "Inkonsistensi Cakupan",
    "REDUNDANCY": "Redundansi / Duplikasi Semantik",
    "MODAL_STRENGTH": "Inkonsistensi Kekuatan Modal",
}

SEVERITY_COLORS = {
    "HIGH": "\033[91m",    # Merah
    "MEDIUM": "\033[93m",  # Kuning
    "LOW": "\033[94m",     # Biru
}
RESET = "\033[0m"
BOLD  = "\033[1m"


# ── Shared Topic Detection ────────────────────────────────────────────────────

def share_topic(req_a: RequirementIndividual,
                req_b: RequirementIndividual,
                threshold: float = SIMILARITY_THRESHOLD) -> tuple[bool, float]:
    """
    Cek apakah dua kebutuhan membicarakan topik yang sama.
    Menggunakan:
    1. Jaccard similarity token
    2. Kesamaan objek utama (setelah normalisasi)
    3. Kesamaan aksi (setelah normalisasi)
    """
    tokens_a = get_normalized_tokens(req_a)
    tokens_b = get_normalized_tokens(req_b)
    sim = jaccard_similarity(tokens_a, tokens_b)

    # Bonus jika objek utama sama
    obj_match = (normalize(req_a.obj) == normalize(req_b.obj))
    if obj_match:
        sim += 0.20

    # Bonus jika aksi sama (setelah normalisasi)
    action_match = (normalize(req_a.action) == normalize(req_b.action))
    if action_match:
        sim += 0.10

    sim = min(sim, 1.0)
    return (sim >= threshold), sim


# ── Aturan Inkonsistensi (OWL2 Axioms) ────────────────────────────────────────

def rule_direct_contradiction(a: RequirementIndividual,
                               b: RequirementIndividual,
                               sim: float) -> InconsistencyAxiom | None:
    """
    Aturan 1: OBLIGATE(R_a, X) ∧ PROHIBIT(R_b, X) → inkonsistensi
    Kedua kebutuhan tanpa kondisi dan saling berlawanan modalitas.
    Severity: HIGH
    """
    em_a = a.effective_modality
    em_b = b.effective_modality
    cond_a = a.condition_type
    cond_b = b.condition_type

    if (em_a == "OBLIGATE" and em_b == "PROHIBIT") or \
       (em_a == "PROHIBIT" and em_b == "OBLIGATE"):
        # Keduanya unconditional → HIGH
        if cond_a == ConditionType.UNCONDITIONAL and cond_b == ConditionType.UNCONDITIONAL:
            explanation = (
                f"Kebutuhan #{a.index} {'mewajibkan' if em_a == 'OBLIGATE' else 'melarang'} "
                f"sedangkan kebutuhan #{b.index} {'mewajibkan' if em_b == 'OBLIGATE' else 'melarang'} "
                f"hal yang sama tanpa kondisi apapun."
            )
            return InconsistencyAxiom(a, b, "DIRECT_CONTRADICTION", explanation, "HIGH", sim)

    return None


def rule_antonym_action_inconsistency(a: RequirementIndividual,
                                       b: RequirementIndividual,
                                       sim: float) -> InconsistencyAxiom | None:
    """
    Aturan 1b: Dua kebutuhan pada objek yang sama namun aksi berlawanan (antonim).
    Contoh: harus mengunci fitur ujian (jika presensi < 80%)
            bisa membuka fitur ujian (jika presensi < 80% + dapat izin dosen)
    Severity: HIGH jika kondisi overlap, MEDIUM jika tidak.
    """
    if not has_antonym_action(a, b):
        return None

    em_a = a.effective_modality
    em_b = b.effective_modality

    # Keduanya harus membicarakan hal yang relevan (bukan keduanya PROHIBIT)
    if em_a == "PROHIBIT" and em_b == "PROHIBIT":
        return None

    cond_a = a.condition_type
    cond_b = b.condition_type

    # Cek overlap kondisi (topik kondisi sama, mis. keduanya soal presensi)
    cond_tokens_a = set(a.condition_text.lower().split()) if a.condition_text else set()
    cond_tokens_b = set(b.condition_text.lower().split()) if b.condition_text else set()
    cond_sim = jaccard_similarity(cond_tokens_a, cond_tokens_b) if (cond_tokens_a and cond_tokens_b) else 0

    if cond_a == ConditionType.CONDITIONAL and cond_b == ConditionType.CONDITIONAL and cond_sim > 0.2:
        severity = "HIGH"
        explanation = (
            f"Kebutuhan #{a.index} mewajibkan aksi '{a.action}' pada '{a.obj}' "
            f"dengan kondisi: \"{a.condition_text}\". "
            f"Namun kebutuhan #{b.index} mengizinkan aksi berlawanan '{b.action}' "
            f"pada objek yang sama dengan kondisi yang tumpang tindih: \"{b.condition_text}\". "
            f"Inkonsistensi ini tidak menjelaskan mana yang berlaku saat kondisi bertumpang tindih."
        )
    elif cond_a != ConditionType.UNCONDITIONAL or cond_b != ConditionType.UNCONDITIONAL:
        severity = "HIGH"
        r_uncond = a if cond_a == ConditionType.UNCONDITIONAL else b
        r_cond   = b if cond_a == ConditionType.UNCONDITIONAL else a
        explanation = (
            f"Kebutuhan #{r_uncond.index} menetapkan aturan '{r_uncond.action}' pada '{r_uncond.obj}', "
            f"namun kebutuhan #{r_cond.index} memperbolehkan aksi yang bertentangan ('{r_cond.action}') "
            f"jika syarat tertentu terpenuhi. "
            f"Hal ini menimbulkan ambiguitas: apakah aksi '{r_cond.action}' diizinkan atau tidak?"
        )
    else:
        severity = "MEDIUM"
        explanation = (
            f"Kebutuhan #{a.index} dan #{b.index} memiliki aksi yang berlawanan "
            f"('{a.action}' vs '{b.action}') pada objek yang sama ('{a.obj}'). "
            f"Ini berpotensi menimbulkan konflik implementasi."
        )

    return InconsistencyAxiom(a, b, "CONDITIONAL_CONTRADICTION", explanation, severity, sim)


def rule_conditional_contradiction(a: RequirementIndividual,
                                    b: RequirementIndividual,
                                    sim: float) -> InconsistencyAxiom | None:
    """
    Aturan 2: PROHIBIT(R_a, X) [unconditional] ∧ PERMIT/OBLIGATE(R_b, X) [conditional]
    Satu kebutuhan melarang tanpa syarat, yang lain mengizinkan dengan syarat.
    Contoh: "Sistem harus mengunci fitur ujian jika presensi < 80%"
            "Sistem bisa membuka fitur ujian jika siswa mendapat izin dosen"
    Severity: HIGH
    """
    em_a = a.effective_modality
    em_b = b.effective_modality
    cond_a = a.condition_type
    cond_b = b.condition_type

    pairs = [
        (a, b, em_a, em_b, cond_a, cond_b),
        (b, a, em_b, em_a, cond_b, cond_a),
    ]
    for r1, r2, em1, em2, c1, c2 in pairs:
        if em1 == "PROHIBIT" and em2 in ("PERMIT", "OBLIGATE"):
            if c1 == ConditionType.UNCONDITIONAL and c2 == ConditionType.CONDITIONAL:
                explanation = (
                    f"Kebutuhan #{r1.index} melarang aksi secara mutlak (tanpa syarat), "
                    f"namun kebutuhan #{r2.index} mengizinkan aksi yang sama dengan syarat tertentu. "
                    f"Syarat pada #{r2.index}: \"{r2.condition_text}\". "
                    f"Ini menimbulkan inkonsistensi: apakah aksi diizinkan atau tidak?"
                )
                return InconsistencyAxiom(r1, r2, "CONDITIONAL_CONTRADICTION",
                                          explanation, "HIGH", sim)

    return None


def rule_scope_inconsistency(a: RequirementIndividual,
                              b: RequirementIndividual,
                              sim: float) -> InconsistencyAxiom | None:
    """
    Aturan 3: Kedua kebutuhan bersyarat tapi kondisinya tumpang tindih/bertentangan.
    Contoh: "Jika A, wajibkan X" vs "Jika A, larang X"
    Severity: HIGH jika kondisi sama, MEDIUM jika kondisi mirip
    """
    em_a = a.effective_modality
    em_b = b.effective_modality
    cond_a = a.condition_type
    cond_b = b.condition_type

    if cond_a != ConditionType.UNCONDITIONAL and cond_b != ConditionType.UNCONDITIONAL:
        if (em_a == "OBLIGATE" and em_b == "PROHIBIT") or \
           (em_a == "PROHIBIT" and em_b == "OBLIGATE"):
            # Hitung kesamaan teks kondisi
            cond_tokens_a = set(a.condition_text.lower().split())
            cond_tokens_b = set(b.condition_text.lower().split())
            cond_sim = jaccard_similarity(cond_tokens_a, cond_tokens_b)

            if cond_sim > 0.3:
                severity = "HIGH" if cond_sim > 0.6 else "MEDIUM"
                explanation = (
                    f"Kebutuhan #{a.index} dan #{b.index} keduanya bersyarat "
                    f"dengan kondisi yang mirip/tumpang tindih "
                    f"(kesamaan kondisi: {cond_sim:.0%}), "
                    f"namun memberikan aturan yang berlawanan ({em_a} vs {em_b})."
                )
                return InconsistencyAxiom(a, b, "SCOPE_INCONSISTENCY",
                                          explanation, severity, sim)
    return None


def rule_redundancy(a: RequirementIndividual,
                    b: RequirementIndividual,
                    sim: float) -> InconsistencyAxiom | None:
    """
    Aturan 4: Dua kebutuhan dengan modalitas sama dan topik sangat mirip → redundansi.
    Severity: LOW
    """
    if sim < HIGH_SIM_THRESHOLD:
        return None

    em_a = a.effective_modality
    em_b = b.effective_modality

    if em_a == em_b:
        explanation = (
            f"Kebutuhan #{a.index} dan #{b.index} tampak menyatakan hal yang sama "
            f"(kesamaan semantik: {sim:.0%}) dengan modalitas yang identik ({em_a}). "
            f"Pertimbangkan untuk menggabungkan atau menghapus salah satunya."
        )
        return InconsistencyAxiom(a, b, "REDUNDANCY", explanation, "LOW", sim)
    return None


def rule_modal_strength(a: RequirementIndividual,
                         b: RequirementIndividual,
                         sim: float) -> InconsistencyAxiom | None:
    """
    Aturan 5: MUST(R_a, X) vs CAN/SHOULD(R_b, X) → pelemahan tidak konsisten.
    Severity: MEDIUM
    """
    em_a = a.effective_modality
    em_b = b.effective_modality

    downgrade_pairs = {
        ("OBLIGATE", "PERMIT"),
    }
    pair = (em_a, em_b)
    pair_rev = (em_b, em_a)

    if pair in downgrade_pairs or pair_rev in downgrade_pairs:
        strong = a if em_a == "OBLIGATE" else b
        weak   = b if em_a == "OBLIGATE" else a
        explanation = (
            f"Kebutuhan #{strong.index} mewajibkan (MUST/harus) suatu aksi, "
            f"namun kebutuhan #{weak.index} hanya mengizinkan (CAN/SHOULD/bisa) "
            f"aksi yang sama. Ini melemahkan kekuatan modal tanpa alasan yang jelas."
        )
        return InconsistencyAxiom(strong, weak, "MODAL_STRENGTH",
                                   explanation, "MEDIUM", sim)
    return None


# ── Reasoner Utama ─────────────────────────────────────────────────────────────

class OWL2Reasoner:
    """
    OWL2 Reasoner: menerapkan aturan inkonsistensi pada semua pasang kebutuhan.
    Menggunakan pendekatan Tableau-based reasoning yang disederhanakan.
    """

    RULES = [
        rule_direct_contradiction,
        rule_antonym_action_inconsistency,
        rule_conditional_contradiction,
        rule_scope_inconsistency,
        rule_redundancy,
        rule_modal_strength,
    ]

    def __init__(self, ontology: RequirementsOntology):
        self.ontology = ontology
        self.results: list[InconsistencyAxiom] = []

    def run(self) -> list[InconsistencyAxiom]:
        """
        Jalankan semua aturan pada setiap pasang kebutuhan.
        Kompleksitas: O(n²) terhadap jumlah kebutuhan.
        """
        individuals = self.ontology.individuals
        n = len(individuals)
        self.results = []

        for i in range(n):
            for j in range(i + 1, n):
                a = individuals[i]
                b = individuals[j]

                # Cek apakah topik cukup mirip untuk dibandingkan
                same_topic, sim = share_topic(a, b)
                if not same_topic:
                    continue

                # Terapkan aturan satu per satu, ambil inkonsistensi pertama yang ditemukan
                found = False
                for rule_fn in self.RULES:
                    axiom = rule_fn(a, b, sim)
                    if axiom:
                        self.results.append(axiom)
                        self.ontology.add_inconsistency(axiom)
                        found = True
                        break  # Satu inkonsistensi per pasang

        return self.results

    def summary(self) -> dict:
        """Ringkasan hasil reasoning."""
        total = len(self.results)
        by_severity = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
        by_type = {}
        for r in self.results:
            by_severity[r.severity] = by_severity.get(r.severity, 0) + 1
            label = CONFLICT_TYPE_LABELS.get(r.conflict_type, r.conflict_type)
            by_type[label] = by_type.get(label, 0) + 1
        return {
            "total": total,
            "by_severity": by_severity,
            "by_type": by_type,
        }
