"""
main.py
CLI Utama - Sistem Pengecekan Inkonsistensi Kebutuhan Sistem
Menggunakan OWL2 Ontology + NLP Rule-based

Cara penggunaan:
  python main.py
"""

import sys
import os
from datetime import datetime

from owl_ontology import RequirementsOntology
from nlp_extractor import extract_requirement
from owl_reasoner import OWL2Reasoner, CONFLICT_TYPE_LABELS, SEVERITY_COLORS, RESET, BOLD


# ── Konstanta Tampilan ────────────────────────────────────────────────────────

CYAN    = "\033[96m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
RED     = "\033[91m"
BLUE    = "\033[94m"
MAGENTA = "\033[95m"
DIM     = "\033[2m"
UNDER   = "\033[4m"

SEP     = "─" * 65
SEP2    = "═" * 65


def cls():
    os.system("cls" if os.name == "nt" else "clear")


def print_banner():
    print(f"""
{CYAN}{BOLD}
╔══════════════════════════════════════════════════════════════╗
║     🔍 SISTEM PENGECEKAN INKONSISTENSI KEBUTUHAN SISTEM      ║
║     Berbasis OWL2 Ontology + NLP Rule-based Extraction       ║
╚══════════════════════════════════════════════════════════════╝
{RESET}
{DIM}• Input kalimat kebutuhan satu per satu
• Ketik '{BOLD}selesai{DIM}' untuk menjalankan analisis
• Ketik '{BOLD}lihat{DIM}'   untuk melihat daftar kebutuhan
• Ketik '{BOLD}hapus <nomor>{DIM}' untuk menghapus kebutuhan
• Ketik '{BOLD}reset{DIM}'   untuk mulai dari awal
• Ketik '{BOLD}keluar{DIM}'  untuk exit{RESET}
""")


def print_requirement_list(requirements: list):
    if not requirements:
        print(f"\n  {DIM}(Belum ada kebutuhan yang diinput){RESET}\n")
        return

    print(f"\n{BOLD}  📋 Daftar Kebutuhan Sistem:{RESET}")
    print(f"  {SEP}")
    for req in requirements:
        em_color = {
            "OBLIGATE": GREEN,
            "PROHIBIT": RED,
            "PERMIT": YELLOW,
            "UNKNOWN": DIM,
        }.get(req.effective_modality, RESET)

        cond_indicator = ""
        from owl_ontology import ConditionType
        if req.condition_type == ConditionType.CONDITIONAL:
            cond_indicator = f" {BLUE}[BERSYARAT]{RESET}"
        elif req.condition_type == ConditionType.EXCEPTION:
            cond_indicator = f" {MAGENTA}[PENGECUALIAN]{RESET}"

        mod_badge = f"{em_color}[{req.effective_modality}]{RESET}"
        print(f"  {BOLD}#{req.index:2d}{RESET} {mod_badge}{cond_indicator}")
        print(f"      {req.text}")
        print(f"      {DIM}Subjek: {req.subject} | Aksi: {req.action} | Objek: {req.obj}{RESET}")

    print(f"  {SEP}\n")


def print_analysis_header(n: int):
    print(f"\n{CYAN}{SEP2}{RESET}")
    print(f"{CYAN}{BOLD}  🧠 ANALISIS OWL2 REASONER DIMULAI{RESET}")
    print(f"{CYAN}  Memeriksa {n} kebutuhan ({n*(n-1)//2} pasang kombinasi)...{RESET}")
    print(f"{CYAN}{SEP2}{RESET}\n")


def print_inconsistency(axiom, idx: int):
    severity_color = SEVERITY_COLORS.get(axiom.severity, RESET)
    conflict_label = CONFLICT_TYPE_LABELS.get(axiom.conflict_type, axiom.conflict_type)

    severity_badge = f"{severity_color}{BOLD}[{axiom.severity}]{RESET}"
    type_badge = f"{MAGENTA}{conflict_label}{RESET}"

    print(f"  {BOLD}⚠️  Inkonsistensi #{idx}{RESET} {severity_badge}")
    print(f"  {SEP}")
    print(f"  {UNDER}Tipe{RESET}        : {type_badge}")
    print(f"  {UNDER}Pasangan{RESET}    : Kebutuhan #{axiom.req_a.index} ↔ Kebutuhan #{axiom.req_b.index}")
    print(f"  {UNDER}Kesamaan{RESET}    : {axiom.similarity_score:.0%}")
    print()
    print(f"  {DIM}Kebutuhan #{axiom.req_a.index}:{RESET}")
    print(f"  {YELLOW}  \"{axiom.req_a.text}\"{RESET}")
    print()
    print(f"  {DIM}Kebutuhan #{axiom.req_b.index}:{RESET}")
    print(f"  {YELLOW}  \"{axiom.req_b.text}\"{RESET}")
    print()
    print(f"  {BOLD}📌 Penjelasan:{RESET}")
    # Word-wrap penjelasan
    words = axiom.explanation.split()
    line = "     "
    for word in words:
        if len(line) + len(word) > 68:
            print(line)
            line = "     " + word + " "
        else:
            line += word + " "
    if line.strip():
        print(line)
    print()


def print_summary(summary: dict, n_req: int):
    total = summary["total"]
    by_sev = summary["by_severity"]
    by_type = summary["by_type"]

    print(f"\n{CYAN}{SEP2}{RESET}")
    print(f"{CYAN}{BOLD}  📊 RINGKASAN HASIL ANALISIS{RESET}")
    print(f"{CYAN}{SEP2}{RESET}\n")
    print(f"  Total kebutuhan dianalisis : {BOLD}{n_req}{RESET}")
    print(f"  Total inkonsistensi ditemukan: {BOLD}{RED if total > 0 else GREEN}{total}{RESET}\n")

    if total > 0:
        print(f"  {BOLD}Berdasarkan Tingkat Keparahan:{RESET}")
        for sev, count in by_sev.items():
            if count > 0:
                color = SEVERITY_COLORS.get(sev, RESET)
                bar = "█" * count
                print(f"    {color}{sev:8s}{RESET} : {color}{bar}{RESET} {count}")

        print(f"\n  {BOLD}Berdasarkan Tipe Inkonsistensi:{RESET}")
        for tipe, count in by_type.items():
            print(f"    • {tipe}: {BOLD}{count}{RESET}")
    else:
        print(f"  {GREEN}✅ Tidak ditemukan inkonsistensi antar kebutuhan!{RESET}")

    print()


def print_owl_export_info(path: str):
    print(f"\n  {GREEN}📁 Ontologi OWL2 berhasil diekspor ke:{RESET}")
    print(f"  {BOLD}  {path}{RESET}")
    print(f"  {DIM}  (Dapat dibuka dengan Protégé atau OWL reasoner lain){RESET}\n")


def get_export_path() -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"requirements_ontology_{timestamp}.owl"


# ── NLP Debug Mode ────────────────────────────────────────────────────────────

def print_nlp_debug(req):
    """Tampilkan hasil ekstraksi NLP detail."""
    print(f"\n  {DIM}┌─ Ekstraksi NLP ─────────────────────────────────────────┐{RESET}")
    print(f"  {DIM}│ Subjek     : {req.subject:<40}│{RESET}")
    print(f"  {DIM}│ Aksi       : {req.action:<40}│{RESET}")
    print(f"  {DIM}│ Objek      : {req.obj:<40}│{RESET}")
    print(f"  {DIM}│ Modalitas  : {req.modality.value:<40}│{RESET}")
    print(f"  {DIM}│ Negasi     : {str(req.is_negated):<40}│{RESET}")
    print(f"  {DIM}│ Efektif    : {req.effective_modality:<40}│{RESET}")
    print(f"  {DIM}│ Kondisi    : {req.condition_type.value:<40}│{RESET}")
    if req.condition_text:
        cond_short = req.condition_text[:40]
        print(f"  {DIM}│ Teks Syarat: {cond_short:<40}│{RESET}")
    print(f"  {DIM}└─────────────────────────────────────────────────────────┘{RESET}")


# ── Main Loop ─────────────────────────────────────────────────────────────────

def main():
    cls()
    print_banner()

    ontology = RequirementsOntology()
    requirements_text: list[str] = []
    debug_mode = False
    counter = 1

    while True:
        try:
            prompt = f"{CYAN}{BOLD}[Kebutuhan #{counter}]{RESET} > "
            user_input = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n\n{DIM}Program dihentikan.{RESET}\n")
            break

        if not user_input:
            continue

        cmd = user_input.lower()

        # ── Perintah ──────────────────────────────────────────────────────────
        if cmd in ("keluar", "exit", "quit"):
            print(f"\n{DIM}Terima kasih. Program selesai.{RESET}\n")
            break

        elif cmd in ("reset",):
            ontology = RequirementsOntology()
            requirements_text = []
            counter = 1
            cls()
            print_banner()
            print(f"  {GREEN}✔ Data direset. Silakan input ulang kebutuhan.{RESET}\n")
            continue

        elif cmd in ("lihat", "list"):
            print_requirement_list(ontology.individuals)
            continue

        elif cmd.startswith("hapus "):
            parts = cmd.split()
            if len(parts) == 2 and parts[1].isdigit():
                idx = int(parts[1])
                before = len(ontology.individuals)
                ontology.individuals = [r for r in ontology.individuals if r.index != idx]
                after = len(ontology.individuals)
                if before != after:
                    print(f"  {GREEN}✔ Kebutuhan #{idx} dihapus.{RESET}\n")
                else:
                    print(f"  {YELLOW}⚠ Kebutuhan #{idx} tidak ditemukan.{RESET}\n")
            else:
                print(f"  {YELLOW}Penggunaan: hapus <nomor>{RESET}\n")
            continue

        elif cmd in ("debug on",):
            debug_mode = True
            print(f"  {DIM}Mode debug aktif.{RESET}\n")
            continue

        elif cmd in ("debug off",):
            debug_mode = False
            print(f"  {DIM}Mode debug nonaktif.{RESET}\n")
            continue

        elif cmd in ("selesai", "analisis", "done", "check"):
            if len(ontology.individuals) < 2:
                print(f"\n  {YELLOW}⚠ Minimal 2 kebutuhan diperlukan untuk analisis.{RESET}\n")
                continue

            # ── Jalankan Reasoning ─────────────────────────────────────────
            print_analysis_header(len(ontology.individuals))
            reasoner = OWL2Reasoner(ontology)
            results = reasoner.run()

            if results:
                for i, axiom in enumerate(results, 1):
                    print_inconsistency(axiom, i)
                    print(f"  {SEP}\n")
            else:
                print(f"  {GREEN}✅ Tidak ada inkonsistensi yang ditemukan.{RESET}\n")

            print_summary(reasoner.summary(), len(ontology.individuals))

            # Export OWL
            export_path = get_export_path()
            ontology.export_owl_xml(export_path)
            print_owl_export_info(export_path)

            # Tanya apakah ingin lanjut
            print(f"  {DIM}Ketik kebutuhan baru untuk melanjutkan, atau 'reset' / 'keluar'.{RESET}\n")
            continue

        elif cmd in ("bantuan", "help", "?"):
            print(f"""
  {BOLD}Perintah yang tersedia:{RESET}
  {GREEN}selesai{RESET}       → Jalankan analisis inkonsistensi
  {GREEN}lihat{RESET}         → Tampilkan daftar kebutuhan
  {GREEN}hapus <N>{RESET}     → Hapus kebutuhan nomor N
  {GREEN}reset{RESET}         → Hapus semua dan mulai dari awal
  {GREEN}debug on/off{RESET}  → Tampilkan detail ekstraksi NLP
  {GREEN}keluar{RESET}        → Keluar dari program
""")
            continue

        else:
            # ── Proses Kalimat Kebutuhan Baru ─────────────────────────────
            req = extract_requirement(user_input, counter)
            ontology.add_individual(req)

            em_color = {
                "OBLIGATE": GREEN, "PROHIBIT": RED,
                "PERMIT": YELLOW, "UNKNOWN": DIM,
            }.get(req.effective_modality, RESET)

            from owl_ontology import ConditionType
            cond_info = ""
            if req.condition_type != ConditionType.UNCONDITIONAL:
                cond_info = f" | {BLUE}Kondisi: {req.condition_type.value}{RESET}"

            print(f"  {GREEN}✔{RESET} Ditambahkan sebagai "
                  f"{em_color}{BOLD}{req.effective_modality}{RESET}{cond_info}")

            if debug_mode:
                print_nlp_debug(req)
            else:
                print(f"  {DIM}(Ketik 'debug on' untuk melihat detail ekstraksi){RESET}")

            print()
            counter += 1


if __name__ == "__main__":
    main()
