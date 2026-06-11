"""Import human audit decisions from CSVs into the screening_decisions table."""

import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = Path("data/processed/screening.db")
WL_CSV = Path("APOLLO_Screening_Results.xlsx - White Literature.csv")
GL_CSV = Path("APOLLO_Screening_Results.xlsx - Grey Literature.csv")


def main() -> None:
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    total_yes = 0
    total_no = 0
    total_audited = 0
    not_found: list[str] = []
    warn_zero: list[str] = []

    # ── PASS 1: WL CSV ──────────────────────────────────────────────────
    df_wl = pd.read_csv(str(WL_CSV))
    for _, row in df_wl.iterrows():
        decision = str(row.get("Revisor 1", "")).strip()
        if decision not in ("YES", "NO"):
            continue
        paper_id = str(row["Unnamed: 1"]).strip()
        cur.execute(
            "UPDATE screening_decisions SET human_decision = ?, is_audited = 1 WHERE paper_id = ?",
            (decision, paper_id),
        )
        if cur.rowcount == 0:
            not_found.append(paper_id)
        else:
            total_audited += 1
            if decision == "YES":
                total_yes += 1
            else:
                total_no += 1

    # ── PASS 2: Hardcoded GL decisions ──────────────────────────────────
    gl_decisions: dict[str, str] = {
        "GL-273": "YES",
        "GL-329": "YES",
        "GL-435": "YES",
        "GL-140": "NO",
        "GL-234": "NO",
        "GL-363": "NO",
        "GL-397": "NO",
        "GL-406": "NO",
        "GL-412": "NO",
        "GL-421": "NO",
        "GL-436": "NO",
        "GL-49": "NO",
    }
    for paper_id, decision in gl_decisions.items():
        cur.execute(
            "UPDATE screening_decisions SET human_decision = ?, is_audited = 1 WHERE paper_id = ?",
            (decision, paper_id),
        )
        if cur.rowcount == 0:
            not_found.append(paper_id)
        else:
            total_audited += 1
            if decision == "YES":
                total_yes += 1
            else:
                total_no += 1

    # ── PASS 3: NEEDS_REVIEW WL papers by title match ───────────────────
    include_matches: list[str] = [
        "%Cyber-vetting%impression management%",
        "%Job2vec%",
        "%Synthetic Resumes%ChatGPT%",
        "%great software engineers%",
    ]
    exclude_matches: list[str] = [
        "%Logistic Regression%Placement%",
        "%Fuzzy AHP%",
        "%Strategic Talent Management%Agile%",
        "%IT Project Management Complexity%",
        "%Multi-party Development%Artificial Intelligence%",
        "%It Takes a Village%",
        "%instability variations%open-source%",
        "%software modeling%interviews with experts%",
        "%deep-tech%commercialization%",
        "%Ad-Hoc Requirements%",
    ]

    for pattern in include_matches:
        cur.execute(
            "UPDATE screening_decisions SET human_decision = 'YES', is_audited = 1 "
            "WHERE status = 'NEEDS_REVIEW' AND title LIKE ?",
            (pattern,),
        )
        if cur.rowcount == 0:
            warn_zero.append(pattern)
        else:
            total_audited += cur.rowcount
            total_yes += cur.rowcount

    for pattern in exclude_matches:
        cur.execute(
            "UPDATE screening_decisions SET human_decision = 'NO', is_audited = 1 "
            "WHERE status = 'NEEDS_REVIEW' AND title LIKE ?",
            (pattern,),
        )
        if cur.rowcount == 0:
            warn_zero.append(pattern)
        else:
            total_audited += cur.rowcount
            total_no += cur.rowcount

    conn.commit()

    # ── Summary ─────────────────────────────────────────────────────────
    final_yes = conn.execute(
        "SELECT COUNT(*) FROM screening_decisions WHERE human_decision='YES'"
    ).fetchone()[0]
    final_no = conn.execute(
        "SELECT COUNT(*) FROM screening_decisions WHERE human_decision='NO'"
    ).fetchone()[0]
    final_aud = conn.execute(
        "SELECT COUNT(*) FROM screening_decisions WHERE is_audited=1"
    ).fetchone()[0]

    print(f"Total YES set: {total_yes}")
    print(f"Total NO set: {total_no}")
    print(f"Total is_audited=1: {total_audited}")
    print()
    print(f"Final DB state — YES={final_yes} NO={final_no} is_audited={final_aud}")

    if not_found:
        print(f"\nWARNING — {len(not_found)} paper_id(s) NOT found in DB:")
        for pid in not_found:
            print(f"  {pid}")

    if warn_zero:
        print(f"\nWARNING — {len(warn_zero)} NEEDS_REVIEW title pattern(s) matched 0 rows:")
        for p in warn_zero:
            print(f"  {p}")

    conn.close()


if __name__ == "__main__":
    main()
