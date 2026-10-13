import CoreML
import Foundation
import os

/// Runs Audience off the caller's thread, one request at a time on its own queue, with the models loaded on first
/// use (or ahead of time with `prepare`). A load that fails is tried again on the next call.
public final class AudienceRunner: Sendable {
    private let directory: URL
    private let computeUnits: MLComputeUnits
    private let queue = DispatchQueue(label: "spellspeak.audience", qos: .userInitiated)
    private let loading = OSAllocatedUnfairLock<Task<AudienceModel, Error>?>(initialState: nil)

    /// `directory` holds compiled models or the converter's `.mlpackage`s, as `AudienceModel.load` reads them;
    /// in an app, for example, `Bundle.main.url(forResource: "audience", withExtension: nil)`.
    public init(directory: URL, computeUnits: MLComputeUnits = .cpuOnly) {
        self.directory = directory
        self.computeUnits = computeUnits
    }

    public func prepare() async throws {
        _ = try await model()
    }

    public func answer(cards: [String], line: String, current: Int, people: [[Float]],
                       features: [Float]) async throws -> AudienceModel.Answer {
        let model = try await model()
        return try await withCheckedThrowingContinuation { continuation in
            queue.async {
                continuation.resume(with: Result {
                    try model.answer(cards: cards, line: line, current: current, people: people, features: features)
                })
            }
        }
    }

    private func model() async throws -> AudienceModel {
        let task = loading.withLock { task in
            if let task { return task }
            let started = Task { [directory, computeUnits] in
                try await AudienceModel.load(directory: directory, computeUnits: computeUnits)
            }
            task = started
            return started
        }
        do {
            return try await task.value
        } catch {
            loading.withLock { if $0 == task { $0 = nil } }
            throw error
        }
    }
}
