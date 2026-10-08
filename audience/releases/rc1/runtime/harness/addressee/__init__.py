"""The addressee model (released as SpellSpeak Audience): who a player's line was said to.

- `render`: how the single-pass model reads a request (addressee-input-0.1), shared by training and the runtime.
- `features`: the cached-cards model's inputs (addressee-tt-0.5), shared by training and the runtime.
- `classifier`: the model at run time, on ONNX Runtime.
- `evidence`: the rules of evidence as code, shared by the data generator and the rules baseline.
- `rules`: the rules baseline, the floor and the harness's instant fallback.
- `bands`: positions and facings to the spatial facts the model reads.
"""
