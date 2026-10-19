import Foundation

/// One JSON object per line on stdout. Writes are serialised so lines never interleave.
final class Output: @unchecked Sendable {
    private let queue = DispatchQueue(label: "clipnera.engine.output")

    func send(_ message: [String: Any]) {
        queue.sync {
            guard var data = try? JSONSerialization.data(withJSONObject: message) else { return }
            data.append(0x0A)
            FileHandle.standardOutput.write(data)
        }
    }
}

struct EngineError: Error {
    let code: String
    let message: String

    init(_ code: String, _ message: String) {
        self.code = code
        self.message = message
    }

    static func wrap(_ error: Error) -> EngineError {
        if let error = error as? EngineError { return error }
        if error is CancellationError { return EngineError("CANCELLED", "Cancelled") }
        return EngineError("FAILED", error.localizedDescription)
    }
}

struct Params {
    let raw: [String: Any]

    func string(_ key: String) throws -> String {
        guard let value = raw[key] as? String, !value.isEmpty else { throw EngineError("BAD_PARAMS", "Missing \(key)") }
        return value
    }

    func double(_ key: String, default fallback: Double) -> Double {
        (raw[key] as? NSNumber)?.doubleValue ?? fallback
    }

    func bool(_ key: String) -> Bool {
        (raw[key] as? NSNumber)?.boolValue ?? false
    }

    func int(_ key: String) throws -> Int {
        guard let value = raw[key] as? NSNumber else { throw EngineError("BAD_PARAMS", "Missing \(key)") }
        return value.intValue
    }
}

/// Running requests by id, so `cancel` can stop one.
final class Jobs: @unchecked Sendable {
    private var tasks: [Int: Task<Void, Never>] = [:]
    private let lock = NSLock()

    func add(_ id: Int, _ task: Task<Void, Never>) { lock.withLock { tasks[id] = task } }
    func remove(_ id: Int) { lock.withLock { _ = tasks.removeValue(forKey: id) } }
    func cancel(_ id: Int) -> Bool { lock.withLock { tasks[id]?.cancel(); return tasks[id] != nil } }
}

func fileURL(_ path: String, mustExist: Bool = true) throws -> URL {
    if mustExist && !FileManager.default.fileExists(atPath: path) {
        throw EngineError("NOT_FOUND", "No file at \(path)")
    }
    return URL(fileURLWithPath: path)
}

/// Makes the folder for an output file and clears an old file in the way.
func prepareOutput(_ path: String) throws -> URL {
    let url = URL(fileURLWithPath: path)
    try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
    try? FileManager.default.removeItem(at: url)
    return url
}
