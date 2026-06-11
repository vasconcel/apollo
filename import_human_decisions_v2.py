"""Import human audit ground truth for the calibration run into the database."""

import sqlite3
from pathlib import Path

DB_PATH = Path("data/processed/screening.db")


def main() -> None:
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    # ── Hardcoded decisions ─────────────────────────────────────────────

    wl_yes = [1023, 1049, 1108, 1180, 1308, 1323, 1707, 2186, 939, 993]
    wl_no = [
        1038, 108, 113, 116, 1213, 1256, 128, 1311, 1360, 1406, 1438,
        1484, 1487, 1489, 1519, 1559, 1567, 1571, 1581, 1615, 1657, 1659,
        1721, 1769, 1803, 1848, 1892, 1901, 196, 1997, 2041, 2140, 2207,
        248, 249, 251, 305, 360, 367, 38, 401, 41, 413, 420, 440, 441,
        516, 547, 548, 554, 582, 599, 642, 698, 7, 922, 944, 98,
    ]
    gl_yes = ["GL-273", "GL-435"]
    gl_no = ["GL-234", "GL-250", "GL-377", "GL-38", "GL-406", "GL-412", "GL-421", "GL-439", "GL-49"]

    all_yes = [str(i) for i in wl_yes] + gl_yes
    all_no = [str(i) for i in wl_no] + gl_no

    total_yes = 0
    total_no = 0
    not_found: list[str] = []

    for pid in all_yes:
        cur.execute(
            "UPDATE screening_decisions SET human_decision = 'YES', is_audited = 1 WHERE paper_id = ?",
            (pid,),
        )
        if cur.rowcount == 0:
            not_found.append(pid)
        else:
            total_yes += 1

    for pid in all_no:
        cur.execute(
            "UPDATE screening_decisions SET human_decision = 'NO', is_audited = 1 WHERE paper_id = ?",
            (pid,),
        )
        if cur.rowcount == 0:
            not_found.append(pid)
        else:
            total_no += 1

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

    print(f"YES set: {total_yes}   (expected: 12)")
    print(f"NO set:  {total_no}   (expected: 67)")
    print(f"is_audited=1: {final_aud}  (expected: 79)")

    if not_found:
        print(f"\nWARNING — {len(not_found)} paper_id(s) NOT found in DB:")
        for pid in not_found:
            print(f"  {pid}")

    conn.close()


if __name__ == "__main__":
    main()
