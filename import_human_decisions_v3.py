"""
import_human_decisions_v3.py
────────────────────────────
Importa as decisões humanas de auditoria (ground truth) para o banco
de dados do APOLLO após a rodada de calibração com Meta-Llama-3.3-70B-Instruct
(SambaNova Cloud).

Uso:
    python import_human_decisions_v3.py

O script busca o banco em data/processed/screening.db (padrão APOLLO).
Ajuste DB_PATH se necessário.
"""

import sqlite3
import os
import sys

# ── CONFIGURAÇÃO ──────────────────────────────────────────────────────────
DB_PATH = os.path.join("data", "processed", "screening.db")

# ── GROUND TRUTH ──────────────────────────────────────────────────────────
# Formato: paper_id (str) → human_decision ('YES' | 'NO')
# Baseado na auditoria completa realizada pelo revisor sênior.

DECISIONS: dict[str, str] = {

    # ── WL — INCLUDE (YES) ────────────────────────────────────────────────
    # IC1;IC2;IC4 — AI job matching system, explicit R&S pipeline
    "1023": "YES",
    # IC1;IC2;IC4 — Job2vec, job title benchmarking for talent recruitment
    "1049": "YES",
    # IC1;IC3 — Employer brand + intent to join, R&S attraction phase
    "1108": "YES",
    # IC1;IC3 — AI Ethics stereotypes in synthetic resumes, R&S bias (LLM FN)
    "1180": "YES",
    # IC1;IC2;IC3;IC4;IC5 — Gender discrimination in hiring, R&S empirical (LLM FN)
    "1308": "YES",
    # IC1;IC2 — Topic modeling for skill extraction from job postings (LLM FN)
    "1323": "YES",
    # IC1;IC2;IC4 — CV Recommender candidate classification (LLM FN: EC2)
    "1707": "YES",
    # IC1;IC3;IC5 — What distinguishes great software engineers? (LLM FN)
    "1988": "YES",
    # IC1;IC2;IC3 — Agile PM competencies from recruitment signals
    "2186": "YES",
    # IC1;IC2;IC4 — Selecting teams for IT outsourcing projects
    "939":  "YES",
    # IC1;IC3;IC5 — Cyber-vetting and impression management, R&S empirical
    "993":  "YES",

    # ── WL — EXCLUDE (NO) ─────────────────────────────────────────────────
    # EC5 — ICode competitive coding platform (LLM FP)
    "1038": "NO",
    # EC5 — GitHub toxicity, SE community behavior
    "108":  "NO",
    # EC5 — UnitCon unit test synthesis
    "113":  "NO",
    # EC5 — MetaAgents LLM social simulation
    "116":  "NO",
    # EC2;EC5 — AI career development, no text + not R&S research
    "1160": "NO",
    # EC5 — Digital accessibility adoption barriers
    "1213": "NO",
    # EC5 — Logistic regression on placement data (methods paper)
    "1256": "NO",
    # EC5 — Peer code review in higher education
    "128":  "NO",
    # EC5 — HRIS design (internal HR system, not R&S)
    "1311": "NO",
    # EC5 — Blockchain SEM technology adoption
    "1360": "NO",
    # EC5 — FACE theory, SE experimentation
    "1406": "NO",
    # EC5 — Agile mindset literature review
    "1418": "NO",
    # EC5 — Defect prediction model averaging
    "1438": "NO",
    # EC2;EC5 — Design smells empirical
    "1468": "NO",
    # EC5 — Fairness-aware ML engineering
    "1477": "NO",
    # EC2;EC5 — Nurse-led decision making (medical)
    "1484": "NO",
    # EC5 — Code review usefulness OpenDev
    "1487": "NO",
    # EC5 — Big Data/AI industry workforce report
    "1489": "NO",
    # EC5 — Fuzzy AHP person evaluation (operations research)
    "1491": "NO",
    # EC5 — Software fault prediction (SE quality)
    "150":  "NO",
    # EC2;EC5 — UMLDS round-trip engineering tool
    "1519": "NO",
    # EC2;EC5 — Cancer research Chile (biomedical)
    "1559": "NO",
    # EC5 — Eco-label Blue Angel for software
    "1567": "NO",
    # EC5 — RNA biochemical enrichment (biomedical)
    "1571": "NO",
    # EC2;EC5 — Retronasal aroma microgravity (food science)
    "1581": "NO",
    # EC2;EC5 — Strategic Talent Management (retention, not R&S)
    "1612": "NO",
    # EC2;EC5 — IT PM complexity framework
    "1615": "NO",
    # EC2;EC5 — AI marketplace value creation
    "1622": "NO",
    # EC5 — Software release notes challenges
    "1657": "NO",
    # EC2;EC5 — It Takes a Village
    "1659": "NO",
    # EC5 — Diverse leadership ICT (policy roadmap)
    "1721": "NO",
    # EC2;EC5 — Energy efficient software course (education)
    "1769": "NO",
    # EC5 — Developers talking about code quality
    "1803": "NO",
    # EC2;EC5 — Fuzzy RL task scheduling (IoT/systems)
    "1848": "NO",
    # EC5 — Software modeling interviews (interview as method, not job interview)
    "1869": "NO",
    # EC5 — Deep-tech commercialization (innovation mgmt)
    "1892": "NO",
    # EC2;EC5 — Medication reviews elderly patients (medical)
    "1901": "NO",
    # EC5 — SIP feature model product selection (SE/SPL)
    "196":  "NO",
    # EC5 — Ad-hoc requirements case study (RE/SE)
    "1975": "NO",
    # EC2;EC5 — Dating violence intervention (social work)
    "1997": "NO",
    # EC2;EC5 — Contextual personas UX method
    "2041": "NO",
    # EC5 — DFBA statistical package (statistics)
    "2140": "NO",
    # EC4 — OSR visualization tool (pre-2015) — LLM FP
    "2207": "NO",
    # EC5 — Fairness APIs in ML software
    "248":  "NO",
    # EC5 — Searching entangled program spaces (PL theory)
    "249":  "NO",
    # EC5 — Interactive decision support LLMs (meeting scheduling)
    "251":  "NO",
    # EC5 — Automated Soap Opera testing (SE testing)
    "305":  "NO",
    # EC5 — AIGC survey
    "360":  "NO",
    # EC5 — ChatGPT university assessments (education)
    "367":  "NO",
    # EC5 — SBOM tools evaluation Java
    "38":   "NO",
    # EC5 — NREGA digital work relations (ICTD)
    "401":  "NO",
    # EC5 — LLM in-context learning code generation
    "41":   "NO",
    # EC5 — AIOps LLMs survey
    "413":  "NO",
    # EC5 — CPS goal verification systems
    "420":  "NO",
    # EC5 — Relational program synthesis (PL theory)
    "440":  "NO",
    # EC5 — Cognitive activities of developers (SE cognitive science)
    "441":  "NO",
    # EC5 — Gene expressions Alzheimer (biomedical)
    "516":  "NO",
    # EC5 — Backdoor neural code models (SE security)
    "523":  "NO",
    # EC5 — CNCFuzzer embedded security
    "547":  "NO",
    # EC5 — LLM factuality survey (NLP)
    "548":  "NO",
    # EC5 — Microservice event management challenges
    "554":  "NO",
    # EC5 — Manual vs computational thematic analysis
    "582":  "NO",
    # EC5 — Cross-lingual topic discovery (IR/NLP)
    "599":  "NO",
    # EC5 — Data anonymization practices (privacy)
    "642":  "NO",
    # EC5 — Conceptual design information extraction
    "698":  "NO",
    # EC5 — GSE education with OSS (SE education)
    "7":    "NO",
    # EC4 — Online RCT eHealth (pre-2015)
    "922":  "NO",
    # EC5 — GreedyNAS (ML/systems)
    "944":  "NO",
    # EC5 — IoT programming platforms survey
    "98":   "NO",
    # EC5 — OSS instability variations (SE mining)
    "1710": "NO",

    # ── GL — INCLUDE (YES) ────────────────────────────────────────────────
    # IC1;IC2;IC4 — Security Screening ctm IT, BS7858 pre-hire process (LLM FN: EC3)
    "GL-273": "YES",
    # IC1;IC4 — Towards data-driven SE skills assessment (LLM FN: EC2)
    "GL-329": "YES",
    # IC1 — Vacancies RSE, job postings for SE roles (LLM FN: EC3)
    "GL-435": "YES",

    # ── GL — EXCLUDE (NO) ─────────────────────────────────────────────────
    # EC2;EC3;EC5 — IIIT Surat homepage, no content
    "GL-140": "NO",
    # EC2;EC3;EC5 — MIT News AI coding, no content scraped
    "GL-234": "NO",
    # EC5 — Time tracking for developers (productivity, not R&S)
    "GL-250": "NO",
    # EC1;EC2;EC3;EC5 — HSE University course catalogue (Russian)
    "GL-354": "NO",
    # EC5 — Scientific mindset blog (SE epistemology)
    "GL-363": "NO",
    # EC5 — Data analysis as SE (no content + not R&S)
    "GL-365": "NO",
    # EC2;EC3;EC5 — Student Theses HSE (Russian university)
    "GL-377": "NO",
    # EC2;EC3;EC5 — SE DV IT jobs page, no content
    "GL-38":  "NO",
    # EC5 — Addy Osmani opinion piece (LLM FP)
    "GL-406": "NO",
    # EC5 — IT at Chevron employer branding page (LLM FP)
    "GL-412": "NO",
    # EC3 — What jobs with SE degree (career guide article)
    "GL-439": "NO",
    # EC5 — SE Best Practices 2026 DistantJob blog
    "GL-49":  "NO",
}

# ── IMPORT ────────────────────────────────────────────────────────────────
def main() -> None:
    if not os.path.exists(DB_PATH):
        print(f"[ERROR] Database not found at: {DB_PATH}", file=sys.stderr)
        print("  Adjust DB_PATH at the top of this script.", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")

    yes_count = no_count = not_found = 0

    for paper_id, decision in DECISIONS.items():
        result = conn.execute(
            "UPDATE screening_decisions "
            "SET human_decision = ?, is_audited = 1 "
            "WHERE paper_id = ?",
            (decision, paper_id),
        )
        if result.rowcount == 0:
            print(f"  [WARN] paper_id={paper_id!r} not found in DB — skipped")
            not_found += 1
        else:
            if decision == "YES":
                yes_count += 1
            else:
                no_count += 1

    conn.commit()
    conn.close()

    total = yes_count + no_count
    print(f"\n{'='*50}")
    print(f"Import complete")
    print(f"{'='*50}")
    print(f"  human_decision=YES set : {yes_count:>4}  (expected: 14)")
    print(f"  human_decision=NO  set : {no_count:>4}  (expected: 82)")
    print(f"  Total updated          : {total:>4}  (expected: 96)")
    print(f"  Not found in DB (warn) : {not_found:>4}  (expected: 0)")

    # Verification query
    conn = sqlite3.connect(DB_PATH)
    yes_db = conn.execute(
        "SELECT COUNT(*) FROM screening_decisions WHERE human_decision='YES'"
    ).fetchone()[0]
    no_db = conn.execute(
        "SELECT COUNT(*) FROM screening_decisions WHERE human_decision='NO'"
    ).fetchone()[0]
    aud_db = conn.execute(
        "SELECT COUNT(*) FROM screening_decisions WHERE is_audited=1"
    ).fetchone()[0]
    conn.close()

    print(f"\nVerification (current DB state):")
    print(f"  human_decision=YES : {yes_db}")
    print(f"  human_decision=NO  : {no_db}")
    print(f"  is_audited=1       : {aud_db}")

    if yes_db >= 14 and no_db >= 82 and aud_db >= 96:
        print("\n[OK] All thresholds met.")
    else:
        print("\n[WARN] Some counts below expected thresholds — check warnings above.")


if __name__ == "__main__":
    main()