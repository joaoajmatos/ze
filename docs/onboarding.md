# Onboarding

Ze onboarding is a plugin-extensible setup flow. It lets plugins ask for meaningful
first-run information, renders those questions with server-driven UI, reviews durable
memory/settings before saving them.

## Package Boundary

Reusable onboarding logic lives in `core/ops/ze-onboarding`:

- `ze_onboarding.types` defines provider, step, field, seed, session, store, persistence,
  and view dataclasses/protocols.
- `ze_onboarding.coordinator.OnboardingCoordinator` orders providers, dispatches
  submissions, inserts the review step, and applies approved seeds through protocols.
- `ze_onboarding.providers.CoreOnboardingProvider` provides minimal built-in setup.

Deployment adapters live in `apps/ze-api`:

- `ze_api.api.ws.onboarding.send_onboarding_view()` serializes onboarding views
  into WebSocket `message` frames.
- `ze_api.api.ws.component_submit.handle_component_submit()` routes onboarding
  submissions back into the coordinator.
- `ze_api.api.ws.commands.handle_command()` starts onboarding on demand.
- `ze_api.wiring.agents.build_onboarding_coordinator` builds the `OnboardingCoordinator`
  from the core provider, each plugin's provider, and `ze_onboarding`'s own
  Postgres-backed store and persistence adapter. There is no reset service.

Plugin authors should import from `ze_sdk.onboarding`, not from `ze_api`.

## Plugin Opt-In

Plugins opt in by returning an onboarding provider from `ZePlugin.onboarding()`.

```python
from ze_sdk import ZePlugin
from ze_sdk.onboarding import (
    OnboardingField,
    OnboardingResult,
    OnboardingSeed,
    OnboardingStep,
    OnboardingSubmission,
)


class NewsOnboardingProvider:
    plugin_name = "ze_news"
    priority = 20

    async def steps(self) -> list[OnboardingStep]:
        return [
            OnboardingStep(
                id="ze_news.preferences",
                plugin=self.plugin_name,
                title="Choose news preferences",
                kind="form",
                fields=[
                    OnboardingField(
                        id="topics",
                        label="Topics you care about",
                        field_type="chips",
                        placeholder="AI, Portugal, markets",
                    ),
                    OnboardingField(
                        id="excluded_topics",
                        label="Topics to avoid",
                        field_type="chips",
                        required=False,
                    ),
                ],
            )
        ]

    async def handle_submission(
        self,
        submission: OnboardingSubmission,
    ) -> OnboardingResult:
        return OnboardingResult(seeds=[
            OnboardingSeed(
                kind="profile_facet",
                key="news_interests",
                value=submission.values.get("topics", []),
                plugin=self.plugin_name,
                source_step_id=submission.step_id,
            ),
            OnboardingSeed(
                kind="profile_facet",
                key="news_exclusions",
                value=submission.values.get("excluded_topics", []),
                plugin=self.plugin_name,
                source_step_id=submission.step_id,
            ),
        ])


class NewsPlugin(ZePlugin):
    def onboarding(self) -> NewsOnboardingProvider:
        return NewsOnboardingProvider()
```

Providers should be deterministic. Processing the same submission twice must
produce equivalent seeds and follow-up steps.

## Seed Model

Providers do not write directly to global memory or plugin tables. They return typed
`OnboardingSeed` values. The coordinator stores those seeds and shows review-required
items before applying them.

Ze supports three seed kinds:

- `profile_facet`: persisted to `memory_profile_facets`.
- `memory_fact`: submitted through the contribution seam (`submit_perception_facts`) as a reviewed fact with `prompt_supplied` provenance.
- `plugin_setting`: persisted through a registered plugin setting setter.

Step kinds are `intro`, `form`, `choice`, `consent`, `connect_account`, and `review`.

## WebSocket Flow

![Sequence diagram showing the App starting onboarding with a command message, the Backend replying with an assistant message plus onboarding session metadata carrying a form component, and the App submitting the filled-in form back to the Backend as a structured component_submit payload.](diagrams/docs/onboarding-flow.svg)

<sub>[Interactive version](diagrams/docs/onboarding-flow.html)</sub>

The app starts onboarding by sending:

```json
{ "type": "command", "name": "onboarding" }
```

The backend replies with a normal assistant message plus onboarding metadata:

```json
{
  "type": "message",
  "message": {
    "role": "assistant",
    "text": "Tell Ze the basics",
    "components": [{ "type": "form", "id": "core.profile", "title": "Tell Ze the basics" }]
  },
  "onboarding": {
    "session_id": "2cf6...",
    "completed": false
  }
}
```

Interactive onboarding components submit structured payloads:

```json
{
  "type": "component_submit",
  "session_id": "2cf6...",
  "step_id": "core.profile",
  "component_id": "core.profile",
  "values": {
    "preferred_name": "Joao",
    "timezone": "Europe/Lisbon"
  }
}
```

Without a `session_id`, or with a session the coordinator does not know, the server
treats a `component_submit` as a chat message of the form
`[component_submit:<step_id>] <JSON values>`.

## Resetting a dev database

Ze has no reset service. To start over in development, run `make db-reset`, or `make db-reset-seed` to also apply the dev seed data. Delete all data in Governance › Data is the one destructive action in the app.

Do not log raw onboarding submissions; they may contain sensitive user data.
