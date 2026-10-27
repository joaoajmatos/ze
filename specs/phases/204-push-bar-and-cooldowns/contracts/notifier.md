# Contract: the notifier and its cooldown (`ze-proactive`)

Owner: lane `lead`. Every other lane builds against this contract.

## Public surface (`ze_proactive`)

```python
# ze_proactive/types.py
PushOutcome = Literal["delivered", "held", "suppressed_budget", "deduped", "failed"]

@dataclass(frozen=True)
class OncePer:
    key: str
    within: timedelta | None = None   # None: once ever

def is_sent(outcome: PushOutcome | None) -> bool: ...   # delivered or held

# ze_proactive/candidates.py
@dataclass(frozen=True)
class BarThresholds: ...     # fields in data-model.md
@dataclass(frozen=True)
class PushCandidate: ...     # fields in data-model.md

# ze_proactive/notifier.py
class ProactiveNotifier:
    def __init__(
        self,
        interface: AppInterface,
        notification_store: NotificationStore | None,
        *,
        push_log: PushLogStore | None = None,
        settings_store: InterruptionSettingsStore | None = None,
        max_discretionary_per_day: int = 5,
        clock: Callable[[], datetime] = ...,
    ) -> None: ...

    async def notify(
        self,
        kind: PushKind,
        title: str,
        body: str,
        *,
        target_type: str | None = None,
        target_id: str | None = None,
        target_parent_id: str | None = None,
        once_per: OncePer | None = None,
        actions: Sequence[Action] = (),
        format: str = "text",
    ) -> PushOutcome: ...

    async def on_cooldown(self, once_per: OncePer) -> bool: ...          # read-only; False on store error
    async def recent_discretionary_bodies(self, hours: float) -> list[str]: ...  # [] on store error
    async def budget_status(self) -> BudgetStatus: ...                  # unchanged
    async def remaining_budget(self) -> int: ...                        # unchanged
    async def quiet_now(self) -> bool: ...                              # unchanged
    async def deliver_held(self) -> int: ...                            # unchanged; never claims

# ze_proactive/bootstrap.py
def build_notifier(
    pool: asyncpg.Pool,
    interface: AppInterface,
    notification_store: NotificationStore,
    settings_store: InterruptionSettingsStore,
    settings: Any,
) -> ProactiveNotifier: ...   # builds the PushLogStore; max from shared_push_budget(settings)

# ze_proactive/data_domain.py
def proactive_data_domains(pool: asyncpg.Pool) -> list[DataDomain]: ...
    # "proactive.interruption_settings" (unchanged) + "proactive.log" (moved from ze-core)
```

`ze_sdk.proactive` re-exports `OncePer` and `is_sent`, and drops `PushLogStore` and `PushLogEntry`.

## `notify` rules

| Push class | `once_per` | Behaviour |
|---|---|---|
| `requested` | must be `None` (`PushPolicyError`) | no claim, no budget, never held (FR-009) |
| `accountability` | optional | with it: claim (no budget); `cooling` → `deduped` |
| `discretionary` | required (`PushPolicyError`) | claim + budget in one transaction (FR-006) |

Outcomes and the claim:

| Claim | Governor | Outcome | Claim after |
|---|---|---|---|
| `cooling` | — | `deduped` (no notification row) | unchanged |
| `over_budget` | suppress | `suppressed_budget` | none taken |
| `won` | hold | `held` | kept (also if the later release fails) |
| `won` | deliver, push ok | `delivered` | kept |
| `won` | persist or push error | `failed` | deleted by id |
| store error | as if `won`, unclaimed | per governor | none (logged `push_claim_failed`) |

## Private store (`ze_proactive/push_log_store.py`)

```python
class PushLogStore:
    async def claim(self, *, event_type: str, once_per: OncePer, discretionary: bool,
                    max_discretionary: int, payload: str | None,
                    budget_window_hours: float = 24.0) -> ClaimResult: ...
    async def release(self, claim_id: int) -> None: ...
    async def is_cooling(self, once_per: OncePer) -> bool: ...
    async def window_sent_at(self, hours: float) -> list[datetime]: ...   # discretionary claims, ascending
    async def recent_discretionary_payloads(self, hours: float) -> list[str]: ...  # newest first
```

`claim` follows research R2 (key lock, then budget lock, check, count, insert, one transaction). `ze_proactive.attention_budget.budget_status(push_log, max_per_day)` keeps its signature and calls `window_sent_at(window_hours)`.

Deleted: `was_sent_within_hours`, `log`, `try_claim`, `release_claim`, `list_recent_payloads`, `list_workflow_failures_within_hours`, `PushLogEntry`, `attention_budget.{ATTENTION_PUSH_EVENT_KEY, within_budget, try_claim_shared, release_shared}`, `NotificationStore.exists_recent`, `notify(budget_key=, dedup_hours=)`.

## Call sites that change `budget_key=` to `once_per=`

The window is `None` (once ever) unless stated; each keeps its key string.

| File (main) | Key | `within` | Lane |
|---|---|---|---|
| `ze_worldstate/surfacing.py:156` | `loop:<id>` | `timedelta(days=repush_after_days)` | bar |
| `ze_correlation/push.py:194` | `hypothesis:<id>` | — | bar |
| `ze_automation/goals/proposal.py:166` | `goal_overlap:<id>` | — | jobs |
| `ze_automation/goals/executor.py:802` | `goal_reuse:<milestone id>` | — | jobs |
| `ze_automation/jobs/goal_suggestion.py:126` | `goal_suggestion:<id>` | — | jobs |
| `ze_automation/jobs/stuck_goals.py:47` | `stuck_goals:<date>` | — | jobs |
| `ze_finance/jobs/recurring.py:111,133,151` | `finance_stale:…`, `finance_new:…`, `finance_price:…` | — | jr1 |
| `ze_messenger/inbound/processor.py:153` | `inbound:<channel>:<message>` | — | jr1 |
| `ze_personal/jobs/contacts.py:55` | `contact:<id>` | — | jr1 |
| `ze_personal/jobs/insights.py:171` | `insight:<id>` | — | jr1 |

## Cooldown jobs (FR-007)

| Job | Key | `within` | Pre-check (R9) |
|---|---|---|---|
| `AccountabilityJob` | `weekly_accountability` | 6 days | yes |
| `GoalNarrativeJob` | `goal_narrative` | 144 hours | yes |
| `MorningBriefing` (`ze_personal/jobs/briefing.py`) | `morning_brief` | 20 hours | yes |
| workflow-failure alert | `workflow_failure_alert:<workflow id>` | `proactive.alerts.workflow_failure_cooldown_hours` (default 1) | no (cheap) |
