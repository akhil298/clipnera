import AVFoundation

/// A copy for smooth editing, upload and the final render: 1080p H.264 for video, AAC (.m4a) for audio.
/// The original file is never changed.
enum Proxy {
    static func run(path: String, output: String, audioOnly: Bool, onProgress: @escaping @Sendable (Double) -> Void) async throws -> [String: Any] {
        let asset = AVURLAsset(url: try fileURL(path))
        let preset = audioOnly ? AVAssetExportPresetAppleM4A : AVAssetExportPreset1920x1080
        guard let session = AVAssetExportSession(asset: asset, presetName: preset) else {
            throw EngineError("UNSUPPORTED", "This file can't be converted for editing.")
        }
        let url = try prepareOutput(output)

        let progress = Task {
            for await state in session.states(updateInterval: 0.25) {
                if case .exporting(let p) = state { onProgress(p.fractionCompleted) }
            }
        }
        defer { progress.cancel() }

        do {
            try await session.export(to: url, as: audioOnly ? .m4a : .mp4)
        } catch {
            try? FileManager.default.removeItem(at: url)
            throw error
        }
        onProgress(1)
        return ["path": output]
    }
}
