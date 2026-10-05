"""Who a flag is being evaluated for."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.model import User

if TYPE_CHECKING:
    from feature_flags.evaluation import Snapshot


@dataclass(frozen=True)
class FlagContext:
    user_id: str | None = None
    workspace_id: str | None = None
    plan: str | None = None       # effective plan slug, loaded only when a rule targets plans
    role: str | None = None       # "user" | "admin", loaded only when a segment matches roles
    email: str | None = None      # segment matching by domain only; never logged
    anon_id: str | None = None    # signed-out visitors (cn_anon cookie)

    @classmethod
    async def for_user(cls, session: AsyncSession, user_id: str, workspace_id: str | None = None) -> FlagContext:
        """Context for background work, which has a user id but no request."""
        from feature_flags.engine import flags

        return await load_context(session, cls(user_id=user_id, workspace_id=workspace_id),
                                  await flags.snapshot_for(session))


# Background work with no user, and the legacy facade: no unit, so only 0%/100% rollouts apply.
GLOBAL_CONTEXT = FlagContext()


async def load_context(
    session: AsyncSession, ctx: FlagContext, snapshot: Snapshot | None = None, include_config: bool = True
) -> FlagContext:
    """``ctx`` with the role, email and plan filled in, each only when ``snapshot``
    has a rule that needs it (always when ``snapshot`` is None). Flag checks pass
    ``include_config=False``, so most requests add no query."""
    if ctx.user_id is None:
        return ctx
    needs_user = snapshot is None or snapshot.needs_user
    needs_plan = snapshot is None or (snapshot.needs_plan if include_config else snapshot.flags_need_plan)
    if needs_user and ctx.role is None:
        row = (await session.execute(select(User.role, User.email).where(User.id == ctx.user_id))).one_or_none()
        if row is not None:
            ctx = replace(ctx, role=getattr(row.role, "value", row.role), email=row.email)
    if needs_plan and ctx.plan is None:
        # Imported here: subscription.service and subtitle_styling import each other at load time.
        from subscription.service import SubscriptionService

        ctx = replace(ctx, plan=await SubscriptionService.for_session(session).get_effective_plan(ctx.user_id))
    return ctx
