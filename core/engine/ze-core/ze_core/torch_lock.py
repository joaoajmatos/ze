"""Process-wide lock serializing access to shared PyTorch models.

The E5 embedder (embeddings.py) runs on the event-loop thread; the NLI
cross-encoder (nli.py) runs in the default executor's thread pool. Both can
hit the MPS backend at the same moment, which corrupts model state ("Cannot
copy out of meta tensor") since MPS isn't safe for concurrent cross-thread
access. Every call into either model must hold this lock.
"""

from __future__ import annotations

import threading

MODEL_LOCK = threading.Lock()
