"""Transactional campaign-wide USD ceiling, including fees and human review."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

CAMPAIGN_ID = "lyrics-revision-20261023"
TOTAL_LIMIT = Decimal("180")
ALLOCATIONS = {
    "pilot": Decimal("10"),
    "main": Decimal("110"),
    "review": Decimal("25"),
    "services": Decimal("10"),
    "contingency": Decimal("25"),
}
DEFAULT_BUDGET_PATH = Path(__file__).resolve().parents[3] / (
    "data/derived/annual_revision/runtime/campaign-budget.sqlite"
)


class BudgetBlocked(ValueError):
    pass


def money(value):
    amount = Decimal(str(value))
    if not amount.is_finite() or amount < 0:
        raise BudgetBlocked("costs must be finite nonnegative USD values")
    return amount


class CampaignBudget:
    def __init__(self, path=DEFAULT_BUDGET_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS campaign_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS campaign_entries(
                    id TEXT PRIMARY KEY, category TEXT NOT NULL, reserved TEXT NOT NULL,
                    realized TEXT, state TEXT NOT NULL CHECK(state IN ('pending','settled')),
                    evidence_json TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS campaign_events(
                    id INTEGER PRIMARY KEY, recorded_at TEXT NOT NULL,event_json TEXT NOT NULL);
            """)
            policy = json.dumps(
                {
                    "campaign": CAMPAIGN_ID,
                    "total": str(TOTAL_LIMIT),
                    "allocations": {k: str(v) for k, v in ALLOCATIONS.items()},
                },
                sort_keys=True,
            )
            conn.execute("INSERT OR IGNORE INTO campaign_meta VALUES ('policy',?)", (policy,))
            if (
                conn.execute("SELECT value FROM campaign_meta WHERE key='policy'").fetchone()[0]
                != policy
            ):
                raise BudgetBlocked("budget policy changed; explicit reconciliation is required")

    @contextmanager
    def connection(self):
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _event(self, conn, event):
        conn.execute(
            "INSERT INTO campaign_events(recorded_at,event_json) VALUES (?,?)",
            (datetime.now(UTC).isoformat(), json.dumps(event, sort_keys=True)),
        )

    def attest(self, *, external_complete=None, provider_complete=None, evidence):
        if not evidence:
            raise BudgetBlocked("reconciliation evidence is required")
        with self.connection() as conn:
            for key, value in (
                ("external_complete", external_complete),
                ("provider_complete", provider_complete),
            ):
                if value is not None:
                    if type(value) is not bool:
                        raise BudgetBlocked("reconciliation status must be explicit")
                    conn.execute(
                        "INSERT OR REPLACE INTO campaign_meta VALUES (?,?)",
                        (key, json.dumps(value)),
                    )
            self._event(
                conn,
                {
                    "reconciliation": evidence,
                    "external_complete": external_complete,
                    "provider_complete": provider_complete,
                },
            )

    def _snapshot(self, conn):
        totals = {category: Decimal(0) for category in ALLOCATIONS}
        realized, unsettled = Decimal(0), 0
        for row in conn.execute("SELECT * FROM campaign_entries"):
            actual = money(row["realized"] or 0)
            commitment = (
                actual if row["state"] == "settled" else max(actual, money(row["reserved"]))
            )
            totals[row["category"]] += commitment
            realized += actual
            unsettled += row["state"] != "settled"
        flags = dict(conn.execute("SELECT key,value FROM campaign_meta"))
        reconciled = all(flags.get(k) == "true" for k in ("external_complete", "provider_complete"))
        committed = sum(totals.values(), Decimal(0))
        within = committed <= TOTAL_LIMIT and all(totals[k] <= ALLOCATIONS[k] for k in totals)
        return {
            "campaign_id": CAMPAIGN_ID,
            "limit_usd": str(TOTAL_LIMIT),
            "reconciled": reconciled,
            "within_limits": within,
            "committed_usd": str(committed),
            "realized_usd": str(realized),
            "unsettled_entries": unsettled,
            "spendable_usd": str(TOTAL_LIMIT - committed) if reconciled and within else "0",
            "allocations": {k: str(v) for k, v in ALLOCATIONS.items()},
            "category_commitments": {k: str(v) for k, v in totals.items()},
        }

    def snapshot(self):
        with self.connection() as conn:
            return self._snapshot(conn)

    def _check(self, conn, category, additional, operator_cap):
        if category not in ALLOCATIONS:
            raise BudgetBlocked("unknown budget category")
        snapshot = self._snapshot(conn)
        if not snapshot["reconciled"]:
            raise BudgetBlocked("campaign costs require reconciliation before spending")
        if (
            not snapshot["within_limits"]
            or money(snapshot["committed_usd"]) + additional > min(TOTAL_LIMIT, money(operator_cap))
            or money(snapshot["category_commitments"][category]) + additional
            > ALLOCATIONS[category]
        ):
            raise BudgetBlocked("campaign exceeds US$180 or its category allocation")
        return money(snapshot["committed_usd"]) + additional

    def preview(self, category, amount, operator_cap=TOTAL_LIMIT):
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            return self._check(conn, category, money(amount), operator_cap)

    def reserve(self, key, category, amount, evidence, operator_cap=TOTAL_LIMIT):
        amount = money(amount)
        if amount <= 0 or not key or not evidence:
            raise BudgetBlocked("reservation key, evidence and positive maximum cost are required")
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute("SELECT * FROM campaign_entries WHERE id=?", (key,)).fetchone()
            if existing:
                if existing["category"] != category or money(existing["reserved"]) != amount:
                    raise BudgetBlocked("reservation identity or maximum changed")
                self._check(conn, category, Decimal(0), operator_cap)
                return False
            self._check(conn, category, amount, operator_cap)
            conn.execute(
                "INSERT INTO campaign_entries VALUES (?,?,?,NULL,'pending',?)",
                (key, category, str(amount), json.dumps(evidence, sort_keys=True)),
            )
            self._event(
                conn,
                {
                    "reserved": key,
                    "category": category,
                    "maximum_usd": str(amount),
                    "evidence": evidence,
                },
            )
            return True

    def settle(self, key, actual, evidence):
        actual = money(actual)
        if not evidence:
            raise BudgetBlocked("settlement evidence is required")
        with self.connection() as conn:
            changed = conn.execute(
                "UPDATE campaign_entries SET realized=?,state='settled',evidence_json=? WHERE id=?",
                (str(actual), json.dumps(evidence, sort_keys=True), key),
            )
            if changed.rowcount != 1:
                raise BudgetBlocked("unknown reservation")
            # Even an unexpected overrun is recorded, never hidden to make a cap pass.
            self._event(conn, {"settled": key, "actual_usd": str(actual), "evidence": evidence})

    def record_existing(self, key, category, committed, realized, *, settled, evidence):
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._record_existing(
                conn, key, category, committed, realized, settled=settled, evidence=evidence
            )

    def _record_existing(self, conn, key, category, committed, realized, *, settled, evidence):
        committed = money(committed)
        realized = money(realized) if realized is not None else None
        if category not in ALLOCATIONS or not evidence:
            raise BudgetBlocked("existing expense needs a category and evidence")
        if settled and realized is None:
            raise BudgetBlocked("an unknown cost cannot be settled")
        old = conn.execute("SELECT * FROM campaign_entries WHERE id=?", (key,)).fetchone()
        if old and old["realized"] is not None:
            # Stale database snapshots cannot erase costs already observed. A lower
            # invoice needs explicit settle() evidence, not an automatic refresh.
            realized = max(money(old["realized"]), realized or Decimal(0))
        committed = max(committed, realized or Decimal(0))
        values = (
            key,
            category,
            str(committed),
            str(realized) if realized is not None else None,
            "settled" if settled else "pending",
            json.dumps(evidence, sort_keys=True),
        )
        if old and tuple(old) == values:
            return
        conn.execute("INSERT OR REPLACE INTO campaign_entries VALUES (?,?,?,?,?,?)", values)
        self._event(
            conn,
            {
                "reconciled_entry": key,
                "committed_usd": str(committed),
                "realized_usd": str(realized),
                "evidence": evidence,
            },
        )

    def sync_provider(self, entries, evidence):
        """Replace aggregate holds with per-job costs in one indivisible transaction."""
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            for entry in entries:
                self._record_existing(conn, **entry)
            conn.execute("INSERT OR REPLACE INTO campaign_meta VALUES ('provider_complete','true')")
            self._event(conn, {"provider_snapshot": evidence})
