# SpellSpeak Audience on Core ML

Audience's two ONNX graphs as Core ML models, for apps on iPhone, iPad and Mac, with a Swift package that runs them. They give the same answers as ONNX Runtime: the same reading on 1,500 of 1,500 checked requests, every probability within 0.00002.

| | What it is |
|---|---|
| [`swift/`](swift/) | `SpellSpeakAudience`, a Swift package: the tokenizer, the two models and a runner |
| `convert.py` | Makes the Core ML models from a release |
| `check.py` | Compares them with ONNX Runtime |
| `classifier.py` | Runs them from Python on a Mac, with the reference runtime's inputs |
| `make_fixture.py` | Records the reference's encodings and answers that the Swift package's tests check against |

## Get the models

The converted rc2.1 models are on Hugging Face, in the `coreml/` folder of [spellspeak/audience](https://huggingface.co/spellspeak/audience/tree/main/coreml):

```bash
hf download spellspeak/audience --include "coreml/*" --local-dir audience-models
```

Or make them yourself:

```bash
cd audience/coreml
uv run convert.py              # rc2.1's 16-bit graphs from Hugging Face -> build/rc2.1/
uv run check.py                # 1,500 requests through both runtimes
```

Either way the folder holds the two `.mlpackage`s, the release's `tokenizer.json` and `config.json`, and `coreml.json`, which records the shapes, the head's functions, the source files' sha256 and the converter's versions.

## The Swift package

Add `swift/` to a project as a local package (Xcode: File > Add Package Dependencies > Add Local), or depend on it by path:

```swift
.package(path: "../spellspeak-models/audience/coreml/swift")
```

```swift
import SpellSpeakAudience

let audience = AudienceRunner(directory: modelsFolder)  // the downloaded folder, or compiled models in the app bundle
try await audience.prepare()                            // optional: load ahead of the first line
let answer = try await audience.answer(cards: cards, line: line, current: current,
                                       people: personFeatures, features: lineFeatures)
// answer.person[i], answer.unclear, answer.group: probabilities, temperatures applied
```

- **`AudienceRunner`** loads the models on first use and runs one request at a time on its own queue.
- **`AudienceModel`** is the same without the queue: call it from one thread. `AudienceModel.load(directory:)` compiles a folder of `.mlpackage`s once and keeps the result under Caches. An app that adds the `.mlpackage`s to its target gets them compiled by Xcode; put them in a folder with the three JSON files and pass that folder.
- **`AudienceTokenizer`** matches the `tokenizers` library on `tokenizer.json`, offsets included.
- Each card's encoding is cached by its text, so a scene's cards cost one encoder pass each, once.

The package takes the request already rendered: card texts, the line, and the features. Render them with the release's reference runtime (`card_only`, `line_input`, `person_features` and `line_features` in `runtime/harness/addressee/features.py`), on device through embedded Python or wherever the request is built. The rendering is not yet in Swift.

`swift test` checks the tokenizer against 201 of the library's encodings and the models against 160 of ONNX Runtime's answers. It reads the models from `AUDIENCE_MODELS`, by default `build/rc2.1/`, and skips those checks without them:

```bash
cd audience/coreml/swift
AUDIENCE_MODELS=/path/to/audience-models/coreml swift test
```

## The models

| File | Size | What it does |
|---|---|---|
| `AudienceEncoder.mlpackage` | 61 MB | Encodes one text: a person's card, or the line with the line before it |
| `AudienceHead.mlpackage` | 2.4 MB | Scores everyone present: one function per number of people, `people_1` to `people_8` |

Both are ML Programs for iOS 18 and macOS 15 on. They compute in 32 bits on the CPU or GPU, and store the 16-bit release's weights in 16 bits, exactly. `convert.py --precision fp32` converts the full-precision graphs instead, at twice the size. `build/<release>/` also holds the release's `tokenizer.json` and `config.json`. Its `coreml.json` records the shapes, the head's functions, the source files' sha256 and the converter's versions.

## Running them without the package

The Swift package does what follows; this is for another language or runtime. The inputs are the reference runtime's (`runtime/` in a release folder: `features.py` and `render.py`). An app makes the same request, card text, line text and features as `CachedCardsClassifier` does, and runs the models in its place:

1. **Tokenize** with `tokenizer.json`: the cards at most 96 tokens (`card_len`), the line at most 64 (`line_len`). An app reimplementing the tokenizer must match the `tokenizers` library, offsets included.
2. **Encode** each card once and keep it, and the line on every utterance. Pad `ids` to 96 with `[PAD]` (50283) and set `mask` 1 for real tokens. Keep `h` and `hp` for the real tokens; the line's `pooled` is the head's `q`.
3. **Score** with the head function for the number of people present, `people_<n>`:
   - Pad the line's `h` and `hp` to 64 rows with zeros. `cur` is 1 for each of the current line's tokens, as in the reference runtime, and 0 elsewhere.
   - Pad the cards' `g` and `gp` to 96 rows. `card_mask` is 1 for real tokens.
   - `pfeat` and `lfeat` are the reference runtime's `person_features` and `line_features`.
4. **Read** `person`, `unclear` and `group` as logits. Divide each by its temperature in `config.json`, then apply a sigmoid.

Padding as described leaves every answer unchanged. The head's `unclear` and `group` read everyone present, so the number of people is fixed per function: never pad with empty people.

## Measured

`check.py` on an M1 Max under macOS 27.0.1, rc2.1's 16-bit graphs, coremltools 9.0. The requests come from fixed seeds and cover:
- the example's tavern, the Pipecat example's garage, a pair, and crowds of four to eight;
- the player or a character speaking;
- with and without spatial facts;
- up to four lines of history.

| | Core ML, CPU | Core ML, CPU, GPU and Neural Engine | ONNX Runtime, 4 threads |
|---|---|---|---|
| The same reading as ONNX Runtime | 1,500 of 1,500 | 1,500 of 1,500 | |
| Largest probability difference | 0.000010 | 0.000011 | |
| Median per line, cards cached | 6.3 ms | 8.1 ms | 4.9 ms |

The readings agree on every slice: the player speaking, a character speaking, with spatial facts and without.

## Notes

- **16-bit compute is not offered.** Computed in 16 bits, the encoder's fully masked attention rows turn to NaN on the CPU, and its outputs move by up to 0.14 on the GPU and Neural Engine. Storing the weights in 16 bits and computing in 32 keeps the release's answers at half the size.
- **Fixed shapes.** The head reads the line's tokens through `cur` and the cards' through `card_mask`. Padding either changes nothing, so the encoder is fixed at 96 tokens and the head at 64 line tokens and 96 card tokens.
- **The conversion path.** onnx2torch carries the graphs into PyTorch, and coremltools converts the traced modules. `convert.py` replaces five onnx2torch converters:
  - `GreaterOrEqual` and `LessOrEqual`, which it lacks;
  - `Flatten`, whose axis it gets wrong;
  - `Less`, as `lt`, an alias coremltools lacks;
  - `Expand`, which it writes as a product with ones. Core ML's CPU sums such a product wrongly.
- **Python on a Mac.** coremltools' Python bridge crashes with two functions of one package loaded at once, so `classifier.py` keeps one head function at a time. Core ML itself runs all eight together: a Swift check loading every function at once matched ONNX Runtime within 0.00003 in the logits.

Licence: Apache-2.0, as the model; base model `jhu-clsp/ettin-encoder-32m`, MIT.
