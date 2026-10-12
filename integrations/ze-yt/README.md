# ze-yt

`yt-dlp` audio fetcher — turns a video URL into audio that ingestion can transcribe.

## Role in Ze

`ze-ingestion` can ingest video only through this package. It downloads the audio track of a video URL, and `ze-ingestion` then transcribes the audio. Without this package, video URLs fall back to the generic web fetcher.

### Key features

- `YtDlpFetcher` matches YouTube, Instagram (reels and posts), TikTok, Vimeo, and Twitter/X status URLs
- `YtDlpClient` runs `yt-dlp --extract-audio --audio-format mp3 --no-playlist` as a subprocess
- Returns the MP3 bytes as audio content for the ingestion pipeline

### Integration

`ze-ingestion` imports `ze_yt` in a `try/except ImportError` block. When the import works, it puts `YtDlpFetcher` first in its fetcher list. `ze-api` depends on this package. `yt-dlp` must exist as a system binary or through `uv tool`. If it is missing, the fetch raises a `FetchError`.

## Responsibilities

| Module | What it provides |
|---|---|
| `fetcher.py` | `YtDlpFetcher` — URL patterns and the `fetch()` method |
| `client.py` | `YtDlpClient` — the `yt-dlp` subprocess call |

## Dependencies

`ze-ingestion`, `ze-logging`.

## Testing

From the repo root:

```bash
make test-yt
```

See [docs/testing.md](../../docs/testing.md).
