"""Admin growth, user totals and user history against a real Postgres database.

Skipped unless TEST_DATABASE_URL is set; see test_plans_db.py, whose ``db``
fixture drops and recreates every table.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select

import auth.activity as activity
from admin.repository import AdminRepository
from admin.service import AdminService
from auth.model import LoginEvent, User, UserActivityDay
from auth.oauth_service import OAuthService
from auth.repository import UserRepository
from auth.schema import RegisterRequest
from auth.service import AuthService, LoginClient
from clip.model import ProjectStatus, VideoProject
from clip_generation.model import GeneratedClip
from subscription.model import BillingPeriod, CreditLedger, PaymentStatus, PaymentTransaction
from subscription.repository import PlanRepository
from subscription.service import SubscriptionService
from test_plans_db import TEST_DATABASE_URL, db  # noqa: F401  the shared database fixture
from usage.model import LlmUsage

pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is not set")

SOURCE_URL = "https://www.youtube.com/watch?v=abc"


def _admin(session) -> AdminService:
    return AdminService(AdminRepository(session), PlanRepository(session), SubscriptionService.for_session(session))


async def _seed(maker) -> tuple[str, str]:
    """Alice (3 days old): one project, 3 clips, a refunded charge, Pro and a credit pack,
    two logins, active on two days. Bob (new): one login, active today."""
    now = datetime.utcnow()
    async with maker() as session:
        alice = User(email="alice@example.com", created_at=now - timedelta(days=3))
        bob = User(email="bob@example.com", created_at=now)
        session.add_all([alice, bob])
        await session.commit()
        # Apply this cycle's Free refill now, so reading the plan later adds no ledger rows.
        await SubscriptionService.for_session(session).get_plan_summary(alice.id)

        project = VideoProject(
            user_id=alice.id, title="Talk", source_type="youtube", source_url=SOURCE_URL,
            status=ProjectStatus.COMPLETED, duration_seconds=600,
        )
        session.add(project)
        await session.flush()
        session.add_all(
            [
                GeneratedClip(
                    project_id=project.id, user_id=alice.id, title=f"Clip {i}",
                    start_time=0, end_time=10, duration_seconds=10,
                )
                for i in range(3)
            ]
        )
        session.add_all(
            [
                CreditLedger(
                    user_id=alice.id, amount=20, balance_after=20, reason="Top-up",
                    created_at=now + timedelta(seconds=1),
                ),
                CreditLedger(
                    user_id=alice.id, amount=-20, balance_after=0, reason="Run", reference_id=project.id,
                    reference_type="video_project", created_at=now + timedelta(seconds=2),
                ),
                CreditLedger(
                    user_id=alice.id, amount=5, balance_after=5, reason="Refund", reference_id=project.id,
                    reference_type="video_project_refund", created_at=now + timedelta(seconds=3),
                ),
                LlmUsage(project_id=project.id, user_id=alice.id, step="score", provider="groq", model="m", cost_usd=0.25),
                LlmUsage(project_id=project.id, user_id=alice.id, step="cut", provider="groq", model="m", cost_usd=0.5),
                PaymentTransaction(
                    user_id=alice.id, plan_id="plan-pro", plan_type=BillingPeriod.MONTHLY, amount=699,
                    currency="INR", status=PaymentStatus.SUCCESS, payment_uuid=str(uuid4()), verified_at=now,
                    created_at=now - timedelta(minutes=5),
                ),
                PaymentTransaction(
                    user_id=alice.id, credit_pack="starter", credits=50, amount=99, currency="INR",
                    status=PaymentStatus.SUCCESS, payment_uuid=str(uuid4()), verified_at=now, created_at=now,
                ),
                LoginEvent(
                    user_id=alice.id, method="google", ip="203.0.113.7", user_agent="Firefox",
                    created_at=now - timedelta(days=1),
                ),
                LoginEvent(user_id=alice.id, method="password", created_at=now),
                LoginEvent(user_id=bob.id, method="password", created_at=now),
                UserActivityDay(user_id=alice.id, day=now.date() - timedelta(days=2)),
                UserActivityDay(user_id=alice.id, day=now.date()),
                UserActivityDay(user_id=bob.id, day=now.date()),
            ]
        )
        await session.commit()
        return alice.id, bob.id


@pytest.mark.asyncio
async def test_growth_counts_each_day_and_the_window(db):
    await _seed(db)
    async with db() as session:
        growth = await _admin(session).growth(7)

    today = datetime.utcnow().date()
    assert len(growth.daily) == 7 and growth.daily[-1].day == today
    assert (growth.total_users, growth.new_users) == (2, 2)
    assert (growth.active_in_window, growth.active_today, growth.active_7d, growth.active_30d) == (2, 2, 2, 2)
    assert (growth.projects, growth.clips) == (1, 3)
    assert growth.revenue == 699 + 99 and growth.currency == "INR"
    assert growth.ai_cost_usd == pytest.approx(0.75)

    latest = growth.daily[-1]
    assert (latest.signups, latest.active_users, latest.logins) == (1, 2, 2)
    two_days_ago = growth.daily[-3]
    assert (two_days_ago.active_users, two_days_ago.logins) == (1, 0)


@pytest.mark.asyncio
async def test_user_list_carries_totals_and_sorts(db):
    alice_id, bob_id = await _seed(db)
    async with db() as session:
        by_projects = await _admin(session).list_users(None, 50, 0, "projects")
        newest = await _admin(session).list_users(None, 50, 0, "newest")

    assert [u.id for u in by_projects] == [alice_id, bob_id]
    assert [u.id for u in newest] == [bob_id, alice_id]
    alice = by_projects[0]
    assert (alice.projects, alice.clips, alice.credits_left, alice.total_paid) == (1, 3, 5, 699 + 99)
    assert alice.ai_cost_usd == pytest.approx(0.75)
    assert alice.last_active_on == datetime.utcnow().date()
    bob = by_projects[1]
    assert (bob.projects, bob.clips, bob.total_paid, bob.ai_cost_usd) == (0, 0, 0, 0)


@pytest.mark.asyncio
async def test_user_detail_shows_projects_logins_payments_and_credits(db):
    alice_id, _ = await _seed(db)
    async with db() as session:
        detail = await _admin(session).user_detail(alice_id)

    [project] = detail.projects
    # Charged 20, refunded 5.
    assert (project.source_url, project.clips, project.credits_charged) == (SOURCE_URL, 3, 15)
    assert project.ai_cost_usd == pytest.approx(0.75)
    assert [login.method for login in detail.logins] == ["password", "google"]
    assert (detail.logins[1].ip, detail.logins[1].user_agent) == ("203.0.113.7", "Firefox")
    assert [(p.amount, p.plan_type, p.credits) for p in detail.payments] == [(99, None, 50), (699, "monthly", None)]
    assert [entry.amount for entry in detail.credit_history[:3]] == [5, -20, 20]
    assert detail.active_days == 2
    assert detail.user.credits_left == 5


@pytest.mark.asyncio
async def test_activity_is_recorded_once_per_user_per_day(db, monkeypatch):
    async with db() as session:
        user = User(email="carol@example.com")
        session.add(user)
        await session.commit()
        user_id = user.id
    monkeypatch.setattr(activity, "AsyncSessionLocal", db)
    monkeypatch.setattr(activity, "_recorded_users", set())

    await activity.record_activity(user_id)
    await activity.record_activity(user_id)

    async with db() as session:
        rows = await session.execute(select(func.count()).select_from(UserActivityDay))
        assert rows.scalar_one() == 1


@pytest.mark.asyncio
async def test_login_records_method_ip_and_device(db):
    async with db() as session:
        repo = UserRepository(session)
        await repo.create_user_with_password(RegisterRequest(email="dave@example.com", password="correct-horse"))
        await AuthService(repo, OAuthService()).login(
            "dave@example.com", "correct-horse", LoginClient(ip="198.51.100.4", user_agent="Safari")
        )
        [event] = (await session.execute(select(LoginEvent))).scalars().all()
    assert (event.method, event.ip, event.user_agent) == ("password", "198.51.100.4", "Safari")
