import AVFoundation
import Vision

/// How much of a video already has words burned into its lower part (subtitles), from a few
/// sampled frames, so captions aren't laid on top of them.
enum TextScan {
    /// The lower 45% of the frame, where subtitles sit (Vision's origin is bottom left).
    static let region = CGRect(x: 0, y: 0, width: 1, height: 0.45)

    static func run(path: String, samples: Int) async throws -> [String: Any] {
        let asset = AVURLAsset(url: try fileURL(path))
        let duration = try await asset.load(.duration).seconds
        guard duration > 0 else { return ["frames": 0, "withText": 0, "share": 0.0] }
        let generator = AVAssetImageGenerator(asset: asset)
        generator.appliesPreferredTrackTransform = true
        generator.maximumSize = CGSize(width: 960, height: 960)
        let tolerance = CMTime(seconds: 0.5, preferredTimescale: 600)
        generator.requestedTimeToleranceBefore = tolerance
        generator.requestedTimeToleranceAfter = tolerance

        let count = max(1, samples)
        var withText = 0
        var lines: [String] = []
        for index in 0..<count {
            try Task.checkCancellation()
            // Spread across the video, skipping the very start and end (titles, end cards).
            let time = duration * (Double(index) + 0.5) / Double(count)
            let (image, _) = try await generator.image(at: CMTime(seconds: time, preferredTimescale: 600))
            let found = try recognise(image)
            if !found.isEmpty {
                withText += 1
                lines.append(contentsOf: found.prefix(1))
            }
        }
        return ["frames": count, "withText": withText, "share": Double(withText) / Double(count), "examples": Array(lines.prefix(3))]
    }

    private static func recognise(_ image: CGImage) throws -> [String] {
        let request = VNRecognizeTextRequest()
        request.recognitionLevel = .accurate
        request.regionOfInterest = region
        try VNImageRequestHandler(cgImage: image).perform([request])
        return (request.results ?? []).compactMap { observation in
            guard let best = observation.topCandidates(1).first, best.confidence > 0.5 else { return nil }
            let text = best.string.trimmingCharacters(in: .whitespaces)
            // A word or more of real text, not a logo letter or a timestamp.
            return text.count >= 4 && text.contains(" ") ? text : nil
        }
    }
}
