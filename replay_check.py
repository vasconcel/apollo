# replay_check.py

import os
import tempfile

os.chdir(r'D:\Projetos\apollo')

from src.core.screening_session import ScreeningSession, ArticleReview
from src.core.reproducibility_engine import (
    create_reproducibility_bundle,
    ReplayEngine
)

replay_checksums = []

for run in range(3):
    session = ScreeningSession(
        session_id='replay-test',
        created_at='2026-05-14T10:00:00',
        protocol_version='1.0'
    )

    session.articles.append(
        ArticleReview(
            'A-1',
            'T',
            'A',
            {'literature_type': 'WL'}
        )
    )

    session.record_decision('include', notes='Test')

    with tempfile.TemporaryDirectory() as tmpdir:
        bundle = create_reproducibility_bundle(session, tmpdir)

        replayed, _ = ReplayEngine.replay_session(
            bundle.bundle_path
        )

        checksum = replayed.compute_checksum()

        replay_checksums.append(checksum)

print("Replay checksums:")
for c in replay_checksums:
    print(c)

print()
print("All identical:", len(set(replay_checksums)) == 1)