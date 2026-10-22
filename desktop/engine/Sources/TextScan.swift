import AVFoundation
import Vision

/// How much of a video already has words burned into it (subtitles, at the top or the bottom), from a
/// few sampled frames, so captions aren't laid on top of them; and on which side they sit.
enum TextScan {
    /// Text whose middle is above this (Vision's origin is bottom left) sits in the top part of the frame.
    static let topBand = 0.55

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
        var withText = 0, top = 0, bottom = 0
        var lines: [String] = []
        for index in 0..<count {
            try Task.checkCancellation()
            // Spread across the video, skipping the very start and end (titles, end cards).
            let time = duration * (Double(index) + 0.5) / Double(count)
            let (image, _) = try await generator.image(at: CMTime(seconds: time, preferredTimescale: 600))
            let found = try recognise(image)
            if !found.isEmpty {
                withText += 1
                lines.append(contentsOf: found.prefix(1).map(\.text))
                if found.contains(where: { $0.y > topBand }) { top += 1 }
                if found.contains(where: { $0.y <= topBand }) { bottom += 1 }
            }
        }
        let side = top > 0 && bottom > 0 ? "both" : top > 0 ? "top" : bottom > 0 ? "bottom" : "none"
        return ["frames": count, "withText": withText, "share": Double(withText) / Double(count), "examples": Array(lines.prefix(3)),
                "side": side]
    }

    /// The lines of real text in the frame, each with the height of its middle (0 bottom, 1 top).
    private static func recognise(_ image: CGImage) throws -> [(text: String, y: Double)] {
        let request = VNRecognizeTextRequest()
        request.recognitionLevel = .accurate
        try VNImageRequestHandler(cgImage: image).perform([request])
        return (request.results ?? []).compactMap { observation in
            guard let best = observation.topCandidates(1).first, best.confidence > 0.5 else { return nil }
            let text = best.string.trimmingCharacters(in: .whitespaces)
            // A word or more of real text, not a logo letter or a timestamp.
            return text.count >= 4 && text.contains(" ") ? (text, Double(observation.boundingBox.midY)) : nil
        }
    }
}
