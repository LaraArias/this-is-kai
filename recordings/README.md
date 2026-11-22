# Raw screen recordings

Each file is one whole agent run recorded from the OpenClaw interface, from before the prompt is sent to the final answer. They were converted from the recorder's WebM to MP4 and placed on a 1920×1080 canvas. Nothing was cut, sped up, frozen or added.

These runs use the hackathon's official speed patch, whose readout appears at the bottom of the window (`N tok/s mean · N p90 (server)`). They are evidence for the numbers in this repository, not the public demo.

| File | Prompt | Temperature | Length | Rejected requests (429) | Model calls | Mean tokens/s | Per call |
|---|---|---:|---:|---:|---:|---:|---|
| `catalog-temp0-003.mp4` | catalog, 3 calls | 0 | 26.5 s | 3 | 3 | 1,125.6 | 703 / 1,262 / 1,412 |
| `catalog-temp0-001.mp4` | catalog, 3 calls | 0 | 120.6 s | 7 | 3 | 1,002.4 | 638 / 909 / 1,461 |
| `catalog-kimi-recorded-001.mp4` | catalog, 3 calls | 1 | 18.4 s | 1 | 3 | 865.1 | 738 / 1,123 / 734 |
| `catalog-kimi-recorded-004.mp4` | catalog, 3 calls | 1 | 38.5 s | 4 | 3 | 863.2 | 479 / 1,363 / 748 |
| `live-control-002.mp4` | browsing | 1 | 22.4 s | 0 | 4 | 761.7 | 677 / 956 / 889 / 525 |

The catalog prompt is [`prompts/catalog-3calls.txt`](../prompts/catalog-3calls.txt). The long recording is long because the run waited in the provider's queue; the wait is left in.

The same prompt did not score the same twice: at temperature 0 it gave 1,002, 795 and 1,126; at temperature 1 it gave 865, 763 and 863. Every run, including the ones not recorded here and the ones that failed, is in [`data/runs.csv`](../data/runs.csv).
