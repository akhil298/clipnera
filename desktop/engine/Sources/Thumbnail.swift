import AVFoundation
import ImageIO
import UniformTypeIdentifiers

/// A JPEG still from a video, no larger than `maxSize` on its long side.
enum Thumbnail {
    static func run(path: String, atSeconds: Double, maxSize: Double, output: String) async throws -> [String: Any] {
        let asset = AVURLAsset(url: try fileURL(path))
        let generator = AVAssetImageGenerator(asset: asset)
        generator.appliesPreferredTrackTransform = true
        generator.maximumSize = CGSize(width: maxSize, height: maxSize)
        // A nearby keyframe is fine for a thumbnail and much faster than an exact frame.
        let tolerance = CMTime(seconds: 1, preferredTimescale: 600)
        generator.requestedTimeToleranceBefore = tolerance
        generator.requestedTimeToleranceAfter = tolerance

        let (image, _) = try await generator.image(at: CMTime(seconds: atSeconds, preferredTimescale: 600))
        let url = try prepareOutput(output)
        guard let destination = CGImageDestinationCreateWithURL(url as CFURL, UTType.jpeg.identifier as CFString, 1, nil) else {
            throw EngineError("FAILED", "Could not write \(output)")
        }
        CGImageDestinationAddImage(destination, image, [kCGImageDestinationLossyCompressionQuality: 0.8] as CFDictionary)
        guard CGImageDestinationFinalize(destination) else { throw EngineError("FAILED", "Could not write \(output)") }
        return ["path": output, "width": image.width, "height": image.height]
    }
}
