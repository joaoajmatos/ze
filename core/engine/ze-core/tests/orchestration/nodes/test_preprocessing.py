from unittest.mock import AsyncMock

from ze_core.orchestration.nodes.preprocessing import preprocess


def _config(settings: dict, client=None) -> dict:
    return {
        "configurable": {
            "openrouter_client": client or AsyncMock(),
            "settings": settings,
        }
    }


class TestCapabilityKeysBypassResolver:
    """models.default must never influence vision captioning — the call site
    reads models.vision_caption directly."""

    async def test_vision_caption_uses_models_vision_caption_regardless_of_default(
        self,
    ):
        client = AsyncMock()
        client.complete = AsyncMock(return_value="a caption")
        settings = {
            "models": {
                "default": "fleet-default-model",
                "overrides": {},
                "vision_caption": "pinned-vision-model",
            }
        }
        state = {"image_data": b"raw-bytes", "image_mime": "image/jpeg", "prompt": None}

        await preprocess(state, _config(settings, client=client))

        assert client.complete.call_args.kwargs["model"] == "pinned-vision-model"
