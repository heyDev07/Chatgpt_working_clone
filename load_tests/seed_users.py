"""Pre-creates a pool of test accounts for locustfile.py to log in as.

Deliberately not done through POST /api/v1/auth/register: that endpoint is rate-limited to 5
requests per 5 minutes per IP (Phase 15) - a real, intentional protection against registration
abuse that a load test setup script shouldn't route around by disabling, but also shouldn't be
measuring the effect of either. Going through AuthService directly is test setup, not simulated
traffic - the actual load test only ever hits POST /auth/login (keyed per-email, Phase 15's
login_rate_limiter, so N different pre-seeded users never share one rate-limit bucket) and the
app's normal endpoints, exactly like real concurrent users would.

Run once before a load test: python load_tests/seed_users.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.db.database import async_session_factory  # noqa: E402
from app.services.auth_service import AuthService  # noqa: E402

USER_COUNT = 20
PASSWORD = "LoadTest123!"


async def main() -> None:
    async with async_session_factory() as db:
        service = AuthService(db)
        created = 0
        for i in range(USER_COUNT):
            email = f"loadtest-{i}@example.com"
            try:
                await service.register(email, PASSWORD, f"Load Test {i}")
                created += 1
            except Exception:
                pass  # already exists from a previous run - fine, this script is idempotent
        print(f"Seeded {created} new load-test users (of {USER_COUNT} total)")


if __name__ == "__main__":
    asyncio.run(main())
