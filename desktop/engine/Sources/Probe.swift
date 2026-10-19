import AVFoundation

/// Duration, picture size, frame rate and audio format of a media file.
enum Probe {
    static func run(path: String) async throws -> [String: Any] {
        let url = try fileURL(path)
        let asset = AVURLAsset(url: url)
        let (duration, tracks) = try await loadOrExplain { try await asset.load(.duration, .tracks) }
        let video = tracks.first { $0.mediaType == .video }
        let audio = tracks.first { $0.mediaType == .audio }
        guard video != nil || audio != nil else {
            throw EngineError("UNSUPPORTED", "This file has no video or audio that macOS can read.")
        }

        let size = (try? FileManager.default.attributesOfItem(atPath: path)[.size] as? NSNumber)?.intValue ?? 0
        var result: [String: Any] = [
            "durationSeconds": duration.seconds,
            "fileSize": size,
            "hasVideo": video != nil,
            "hasAudio": audio != nil,
        ]

        if let video {
            let (natural, transform, fps, formats) = try await video.load(.naturalSize, .preferredTransform, .nominalFrameRate, .formatDescriptions)
            let shown = natural.applying(transform)
            result["width"] = Int(abs(shown.width).rounded())
            result["height"] = Int(abs(shown.height).rounded())
            result["fps"] = Double(fps)
            result["videoCodec"] = formats.first.map(codecName) ?? ""
        }
        if let audio {
            let formats = try await audio.load(.formatDescriptions)
            if let format = formats.first, let basic = CMAudioFormatDescriptionGetStreamBasicDescription(format)?.pointee {
                result["sampleRate"] = basic.mSampleRate
                result["audioChannels"] = Int(basic.mChannelsPerFrame)
                result["audioCodec"] = codecName(format)
            }
        }
        return result
    }

    /// AVFoundation reports unreadable formats (e.g. WebM) as a generic error; say what it means.
    private static func loadOrExplain<T>(_ load: () async throws -> T) async throws -> T {
        do {
            return try await load()
        } catch {
            throw EngineError("UNSUPPORTED", "macOS can't open this file format.")
        }
    }

    private static func codecName(_ format: CMFormatDescription) -> String {
        let code = CMFormatDescriptionGetMediaSubType(format)
        let bytes = [24, 16, 8, 0].map { UInt8((code >> $0) & 0xFF) }
        return String(decoding: bytes, as: UTF8.self).trimmingCharacters(in: .whitespaces)
    }
}
