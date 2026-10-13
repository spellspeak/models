import CoreML
import Foundation
import SpellSpeakAudience
import Testing

// The tokenizer and the models against the reference: the fixtures hold the `tokenizers` library's encodings and
// ONNX Runtime's answers for rc2.1's 16-bit graphs (`make_fixture.py`). Both checks read the converter's output,
// from AUDIENCE_MODELS (default: ../build/rc2.1), and are skipped without it.
private let models = URL(fileURLWithPath: ProcessInfo.processInfo.environment["AUDIENCE_MODELS"]
    ?? URL(fileURLWithPath: #filePath).deletingLastPathComponent()
        .appendingPathComponent("../../../build/rc2.1").standardized.path)
private let haveModels = FileManager.default.fileExists(atPath: models.appendingPathComponent("coreml.json").path)

private func fixture<T: Decodable>(_ name: String, as type: T.Type) throws -> T {
    let url = try #require(Bundle.module.url(forResource: name, withExtension: "json", subdirectory: "Fixtures"))
    return try JSONDecoder().decode(T.self, from: Data(contentsOf: url))
}

private struct Encodings: Decodable {
    struct Case: Decodable {
        let text: String
        let max_length: Int
        let ids: [Int32]
        let offsets: [[Int]]
    }

    let cases: [Case]
}

private struct Answers: Decodable {
    struct Request: Decodable {
        let cards: [String]
        let line: String
        let current: Int
        let people: [[Float]]
        let features: [Float]
        let person: [Double]
        let unclear: Double
        let group: Double
    }

    let requests: [Request]
}

private func reading(person: [Double], unclear: Double, group: Double) -> String {
    if unclear >= 0.5 { return "unclear" }
    if group >= 0.5 { return "group" }
    return String(person.indices.max { person[$0] < person[$1] }!)
}

@Test(.enabled(if: haveModels, "needs the converter's output in AUDIENCE_MODELS"))
func tokenizerMatchesTheTokenizersLibrary() throws {
    let tokenizer = try AudienceTokenizer(contentsOf: models.appendingPathComponent("tokenizer.json"))
    for item in try fixture("tokenization", as: Encodings.self).cases {
        let got = tokenizer.encode(item.text, maxLength: item.max_length)
        #expect(got.ids == item.ids, "ids for \(item.text.debugDescription.prefix(60))")
        #expect(got.offsets.map { [$0.start, $0.end] } == item.offsets,
                "offsets for \(item.text.debugDescription.prefix(60))")
    }
}

@Test(.enabled(if: haveModels, "needs the converter's output in AUDIENCE_MODELS"))
func answersMatchOnnxRuntime() async throws {
    let model = try await AudienceModel.load(directory: models)
    var worst = 0.0
    for request in try fixture("answers", as: Answers.self).requests {
        let answer = try model.answer(cards: request.cards, line: request.line, current: request.current,
                                      people: request.people, features: request.features)
        let differences = zip(answer.person, request.person).map { abs($0 - $1) }
            + [abs(answer.unclear - request.unclear), abs(answer.group - request.group)]
        worst = max(worst, differences.max()!)
        #expect(reading(person: answer.person, unclear: answer.unclear, group: answer.group)
                    == reading(person: request.person, unclear: request.unclear, group: request.group),
                "reading for \(request.line.debugDescription)")
    }
    #expect(worst < 1e-4, "largest probability difference \(worst)")
}

@Test(.enabled(if: haveModels, "needs the converter's output in AUDIENCE_MODELS"))
func refusesTooManyPeople() async throws {
    let model = try await AudienceModel.load(directory: models)
    let nine = Array(repeating: "Someone.", count: 9)
    #expect(throws: AudienceError.self) {
        try model.answer(cards: nine, line: "Hello.", current: 6, people: nine.map { _ in [] }, features: [])
    }
}
