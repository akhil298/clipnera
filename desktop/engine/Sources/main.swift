import Foundation

// clipnera-engine: the app's video worker. Reads one JSON request per line on stdin,
//   {"id": 1, "method": "probe", "params": {"path": "/…/clip.mov"}}
// and answers on stdout with {"id": 1, "result": {…}} or {"id": 1, "error": {"code", "message"}}.
// Long jobs also send {"id": 1, "event": "progress", "params": {"fraction": 0.4}}.

let version = "0.1.0"
let output = Output()
let jobs = Jobs()

func handle(_ id: Int, _ method: String, _ params: Params) async throws -> [String: Any] {
    switch method {
    case "ping":
        return ["version": version]
    case "probe":
        return try await Probe.run(path: params.string("path"))
    case "thumbnail":
        return try await Thumbnail.run(
            path: params.string("path"),
            atSeconds: params.double("atSeconds", default: 0),
            maxSize: params.double("maxSize", default: 320),
            output: params.string("output")
        )
    case "proxy":
        return try await Proxy.run(path: params.string("path"), output: params.string("output"), audioOnly: params.bool("audioOnly")) { fraction in
            output.send(["id": id, "event": "progress", "params": ["fraction": fraction]])
        }
    case "textscan":
        return try await TextScan.run(path: params.string("path"), samples: (try? params.int("samples")) ?? 12)
    case "cancel":
        return ["cancelled": jobs.cancel(try params.int("job"))]
    default:
        throw EngineError("UNKNOWN_METHOD", "Unknown method \(method)")
    }
}

while let line = readLine() {
    if line.trimmingCharacters(in: .whitespaces).isEmpty { continue }
    guard
        let data = line.data(using: .utf8),
        let message = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
        let id = (message["id"] as? NSNumber)?.intValue,
        let method = message["method"] as? String
    else {
        output.send(["error": ["code": "BAD_REQUEST", "message": "Each line must be a JSON request with an id and a method"]])
        continue
    }
    let params = Params(raw: message["params"] as? [String: Any] ?? [:])
    let task = Task {
        do {
            output.send(["id": id, "result": try await handle(id, method, params)])
        } catch {
            let failure = EngineError.wrap(error)
            output.send(["id": id, "error": ["code": failure.code, "message": failure.message]])
        }
        jobs.remove(id)
    }
    jobs.add(id, task)
}
