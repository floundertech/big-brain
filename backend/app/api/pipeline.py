from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from pydantic import BaseModel

from ..core.database import get_db
from ..core.models import Entity, EntryEntityLink, EntityRelationship, Entry

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


class OpportunitySummary(BaseModel):
    id: int
    name: str
    stage: str | None = None
    value: str | None = None
    close_date: str | None = None
    account_id: int | None = None
    account_name: str | None = None
    sales_rep: str | None = None
    recent_activity_count: int = 0

    class Config:
        from_attributes = True


class AccountSummary(BaseModel):
    id: int
    name: str
    sales_rep: str | None = None
    industry: str | None = None
    engagement_status: str | None = None
    opportunity_count: int = 0
    contact_count: int = 0
    recent_activity_count: int = 0

    class Config:
        from_attributes = True


class RepSummary(BaseModel):
    sales_rep: str
    accounts: list[AccountSummary]
    opportunities: list[OpportunitySummary]


class ActivityItem(BaseModel):
    entry_id: int
    title: str
    source_type: str
    summary: str | None = None
    created_at: datetime
    linked_entities: list[dict] = []

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Pipeline overview — all opportunities
# ---------------------------------------------------------------------------

@router.get("/opportunities", response_model=list[OpportunitySummary])
async def list_opportunities(
    stage: str | None = None,
    sales_rep: str | None = None,
    include_closed: bool = False,
    db: AsyncSession = Depends(get_db),
):
    q = select(Entity).where(Entity.entity_type == "opportunity").order_by(Entity.name)
    result = await db.execute(q)
    opps = result.scalars().all()

    summaries = []
    for opp in opps:
        meta = opp.meta or {}
        opp_stage = meta.get("stage", "")

        # Filter out closed opportunities unless explicitly requested
        if not include_closed and opp_stage.lower().startswith("closed"):
            continue

        opp_rep = meta.get("sales_rep")

        if stage and opp_stage != stage:
            continue
        if sales_rep and opp_rep != sales_rep:
            continue

        # Find linked account
        acct_result = await db.execute(
            select(Entity.id, Entity.name)
            .join(EntityRelationship, EntityRelationship.target_entity_id == Entity.id)
            .where(
                EntityRelationship.source_entity_id == opp.id,
                EntityRelationship.relationship_type == "opportunity_for",
            )
        )
        acct = acct_result.first()

        # If no rep on opportunity, inherit from account
        if not opp_rep and acct:
            acct_entity = await db.get(Entity, acct.id)
            if acct_entity:
                opp_rep = (acct_entity.meta or {}).get("sales_rep")
                if sales_rep and opp_rep != sales_rep:
                    continue

        # Count recent activity (last 7 days)
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        activity_result = await db.execute(
            select(EntryEntityLink.id)
            .join(Entry, Entry.id == EntryEntityLink.entry_id)
            .where(
                EntryEntityLink.entity_id == opp.id,
                Entry.created_at >= week_ago,
            )
        )
        activity_count = len(activity_result.all())

        summaries.append(OpportunitySummary(
            id=opp.id,
            name=opp.name,
            stage=opp_stage,
            value=meta.get("value"),
            close_date=meta.get("close_date"),
            account_id=acct.id if acct else None,
            account_name=acct.name if acct else None,
            sales_rep=opp_rep,
            recent_activity_count=activity_count,
        ))

    return summaries


# ---------------------------------------------------------------------------
# Account summaries
# ---------------------------------------------------------------------------

@router.get("/accounts", response_model=list[AccountSummary])
async def list_accounts(
    sales_rep: str | None = None,
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
):
    q = select(Entity).where(Entity.entity_type == "account").order_by(Entity.name)
    result = await db.execute(q)
    accounts = result.scalars().all()

    summaries = []
    for acct in accounts:
        meta = acct.meta or {}
        acct_rep = meta.get("sales_rep")

        # Filter inactive accounts unless explicitly requested
        if active_only and meta.get("active") is False:
            continue

        if sales_rep and acct_rep != sales_rep:
            continue

        # Count opportunities linked to this account
        opp_result = await db.execute(
            select(EntityRelationship.id).where(
                EntityRelationship.target_entity_id == acct.id,
                EntityRelationship.relationship_type == "opportunity_for",
            )
        )
        opp_count = len(opp_result.all())

        # Count contacts at this account
        contact_result = await db.execute(
            select(EntityRelationship.id).where(
                EntityRelationship.target_entity_id == acct.id,
                EntityRelationship.relationship_type == "works_at",
            )
        )
        contact_count = len(contact_result.all())

        # Count recent activity (last 7 days)
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        activity_result = await db.execute(
            select(EntryEntityLink.id)
            .join(Entry, Entry.id == EntryEntityLink.entry_id)
            .where(
                EntryEntityLink.entity_id == acct.id,
                Entry.created_at >= week_ago,
            )
        )
        activity_count = len(activity_result.all())

        summaries.append(AccountSummary(
            id=acct.id,
            name=acct.name,
            sales_rep=acct_rep,
            industry=meta.get("industry"),
            engagement_status=meta.get("engagement_status"),
            opportunity_count=opp_count,
            contact_count=contact_count,
            recent_activity_count=activity_count,
        ))

    return summaries


# ---------------------------------------------------------------------------
# By-rep view
# ---------------------------------------------------------------------------

@router.get("/reps", response_model=list[str])
async def list_reps(db: AsyncSession = Depends(get_db)):
    """Get distinct sales rep names across accounts and opportunities."""
    result = await db.execute(
        text("""
            SELECT DISTINCT meta->>'sales_rep' AS rep
            FROM entities
            WHERE entity_type IN ('account', 'opportunity')
              AND meta->>'sales_rep' IS NOT NULL
              AND meta->>'sales_rep' != ''
            ORDER BY rep
        """)
    )
    return [row.rep for row in result.all()]


@router.get("/by-rep/{sales_rep}", response_model=RepSummary)
async def get_rep_summary(sales_rep: str, db: AsyncSession = Depends(get_db)):
    accounts = await list_accounts(sales_rep=sales_rep, db=db)
    opportunities = await list_opportunities(sales_rep=sales_rep, db=db)
    return RepSummary(sales_rep=sales_rep, accounts=accounts, opportunities=opportunities)


# ---------------------------------------------------------------------------
# Weekly activity — recent entries linked to accounts/opportunities
# ---------------------------------------------------------------------------

@router.get("/weekly-activity", response_model=list[ActivityItem])
async def weekly_activity(
    days: int = Query(default=7, le=30),
    sales_rep: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    since = datetime.now(timezone.utc) - timedelta(days=days)

    # Get all entries from the last N days that are linked to accounts or opportunities
    q = (
        select(Entry, EntryEntityLink.entity_id)
        .join(EntryEntityLink, EntryEntityLink.entry_id == Entry.id)
        .join(Entity, Entity.id == EntryEntityLink.entity_id)
        .where(
            Entry.created_at >= since,
            Entity.entity_type.in_(["account", "opportunity"]),
        )
        .order_by(Entry.created_at.desc())
    )
    result = await db.execute(q)

    # Deduplicate entries and collect linked entities
    seen = {}
    for row in result.all():
        entry, entity_id = row
        if entry.id not in seen:
            seen[entry.id] = {
                "entry": entry,
                "entity_ids": set(),
            }
        seen[entry.id]["entity_ids"].add(entity_id)

    items = []
    for entry_data in seen.values():
        entry = entry_data["entry"]
        linked = []
        for eid in entry_data["entity_ids"]:
            e = await db.get(Entity, eid)
            if e:
                rep = (e.meta or {}).get("sales_rep")
                if sales_rep and e.entity_type == "account" and rep != sales_rep:
                    continue
                linked.append({"id": e.id, "name": e.name, "entity_type": e.entity_type})

        if linked or not sales_rep:
            items.append(ActivityItem(
                entry_id=entry.id,
                title=entry.title,
                source_type=entry.source_type,
                summary=entry.summary,
                created_at=entry.created_at,
                linked_entities=linked,
            ))

    return items
