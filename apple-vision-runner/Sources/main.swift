import Foundation
import ImageIO
import Vision

let arguments = CommandLine.arguments
guard arguments.count >= 2 else {
    fputs("usage: vibeedit-apple-vision <capabilities|face|body|pose> [image]\n", stderr)
    exit(2)
}

if arguments[1] == "capabilities" {
    emit(["schemaVersion": "1.0.0", "capabilities": ["face", "body", "pose"]])
}

guard arguments.count == 3,
      ["face", "body", "pose"].contains(arguments[1]),
      let source = CGImageSourceCreateWithURL(URL(fileURLWithPath: arguments[2]) as CFURL, nil),
      let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else {
    fputs("operation requires a decodable image\n", stderr)
    exit(3)
}

let handler = VNImageRequestHandler(cgImage: image, orientation: .up, options: [:])

if arguments[1] == "face" {
    let request = VNDetectFaceRectanglesRequest()
    perform(handler, request)
    emit(["schemaVersion": "1.0.0", "detections": (request.results ?? []).map { detection("face", $0.boundingBox, $0.confidence) }])
}

if arguments[1] == "body" {
    let request = VNDetectHumanRectanglesRequest()
    request.upperBodyOnly = false
    perform(handler, request)
    emit(["schemaVersion": "1.0.0", "detections": (request.results ?? []).map { detection("person", $0.boundingBox, $0.confidence) }])
}

let request = VNDetectHumanBodyPoseRequest()
perform(handler, request)
let poses = (request.results ?? []).compactMap { observation -> [String: Any]? in
    guard let recognized = try? observation.recognizedPoints(.all) else { return nil }
    let keypoints = recognized.compactMap { name, point -> [String: Any]? in
        guard point.confidence >= 0.1 else { return nil }
        return ["joint": name.rawValue, "x": clamp(Double(point.location.x)), "y": clamp(1 - Double(point.location.y)), "confidence": Double(point.confidence)]
    }
    return keypoints.isEmpty ? nil : ["confidence": Double(observation.confidence), "keypoints": keypoints]
}
emit(["schemaVersion": "1.0.0", "poses": poses])

func perform<T: VNRequest>(_ handler: VNImageRequestHandler, _ request: T) {
    do {
        try handler.perform([request])
    } catch {
        fputs("Apple Vision request failed: \(error)\n", stderr)
        exit(4)
    }
}

func detection(_ label: String, _ rect: CGRect, _ confidence: VNConfidence) -> [String: Any] {
    [
        "label": label,
        "confidence": Double(confidence),
        "x": clamp(Double(rect.origin.x)),
        "y": clamp(1 - Double(rect.origin.y + rect.height)),
        "width": clamp(Double(rect.width)),
        "height": clamp(Double(rect.height)),
    ]
}

func clamp(_ value: Double) -> Double {
    max(0, min(1, value))
}

func emit(_ payload: [String: Any]) -> Never {
    guard let data = try? JSONSerialization.data(withJSONObject: payload),
          let line = String(data: data, encoding: .utf8) else {
        fputs("failed to serialize response\n", stderr)
        exit(5)
    }
    print(line)
    exit(0)
}
