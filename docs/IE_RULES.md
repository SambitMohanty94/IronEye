# Engineering Rules & Coding Standards — IronEye

## 1. Python & OpenCV Rules
- **Non-blocking Streams:** Never invoke blocking network calls directly in the OpenCV frame generator loop. Offload database and SMS calls to asynchronous workers or background threads.
- **No Unhandled Frame Drops:** Ingestion loops must handle `ret == False` gracefully by sleeping 10ms, attempting reconnect, or seeking to 0 on loopable media.
- **Clean Memory Management:** Explicitly release VideoCapture objects and PyTorch CUDA caches during source switching.

## 2. Frontend & Styling Rules
- **Palette Strictness:** Only use the 6 designated palette tokens (`#191D23`, `#57707A`, `#7E919F`, `#979DAB`, `#C5BAC4`, `#DEDCDC`)[cite: 1, 2] alongside the status hazard accents (`#FF1744`, `#FFD600`, `#00E676`, `#00E5FF`).
- **Responsive-First:** Viewports must scale using CSS flexbox, CSS grid, and `aspect-ratio` without causing horizontal scrollbars on mobile or tablet devices.
- **SVG Coordinate Synchronization:** Scaled SVG viewports must map click coordinates back to the native $640 \times 480$ frame scale before emitting payload to `POST /api/set_zone`.