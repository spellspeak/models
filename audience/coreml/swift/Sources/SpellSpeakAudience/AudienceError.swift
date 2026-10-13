import Foundation

/// Why Audience could not load or answer: missing or mismatched model files, or a request it cannot read.
public struct AudienceError: LocalizedError, Equatable, Sendable {
    public let message: String

    public init(_ message: String) {
        self.message = message
    }

    public var errorDescription: String? { message }
}
