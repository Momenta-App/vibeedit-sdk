#import <AVFoundation/AVFoundation.h>
#import <CoreVideo/CoreVideo.h>
#import <IOSurface/IOSurface.h>
#import <Metal/Metal.h>
#import <VideoToolbox/VideoToolbox.h>
#include <cstdio>
#include <chrono>
#include <thread>
#include <vector>

namespace {
id<MTLDevice> device;
id<MTLCommandQueue> queue;
id<MTLComputePipelineState> conversion;
id<MTLTexture> owned;
CVMetalTextureCacheRef textureCache;
AVAssetWriter* writer;
AVAssetWriterInput* input;
AVAssetWriterInputPixelBufferAdaptor* adaptor;
FILE* rawFile;
int width, height, numerator, denominator, submitted;
bool failed;
double metrics[4] = {};

// Chromium's BGRA sRGB surface -> limited-range Rec.709 NV12. No CPU
// pixel transfer is required for video delivery. Raw readback is QA-only.
NSString* shader = @R"(
#include <metal_stdlib>
using namespace metal;
float3 yuv(float3 rgb) {
  return float3(16.0/255.0 + dot(rgb, float3(.2126,.7152,.0722)) * 219.0/255.0,
                128.0/255.0 + dot(rgb, float3(-.114572,-.385428,.5)) * 224.0/255.0,
                128.0/255.0 + dot(rgb, float3(.5,-.454153,-.045847)) * 224.0/255.0);
}
kernel void convert(texture2d<float, access::read> source [[texture(0)]],
                    texture2d<float, access::write> luma [[texture(1)]],
                    texture2d<float, access::write> chroma [[texture(2)]],
                    uint2 p [[thread_position_in_grid]]) {
  if (p.x >= luma.get_width() || p.y >= luma.get_height()) return;
  luma.write(float4(yuv(source.read(p).rgb).x), p);
  if ((p.x % 2) == 0 && (p.y % 2) == 0) {
    float3 rgb = (source.read(p).rgb + source.read(p + uint2(1,0)).rgb +
                  source.read(p + uint2(0,1)).rgb + source.read(p + uint2(1,1)).rgb) * .25;
    chroma.write(float4(yuv(rgb).yz, 0, 1), p / 2);
  }
}
)";
}

extern "C" int ve_encoder_begin(const char* output, const char* raw, int w, int h, int n, int d, int bitrate) {
  @autoreleasepool {
    failed = false;
    for (auto& metric : metrics) metric = 0;
    width = w; height = h; numerator = n; denominator = d; submitted = 0;
    if (!device) {
      device = MTLCreateSystemDefaultDevice();
      queue = [device newCommandQueue];
      NSError* error = nil;
      auto library = [device newLibraryWithSource:shader options:nil error:&error];
      conversion = [device newComputePipelineStateWithFunction:[library newFunctionWithName:@"convert"] error:&error];
      if (!conversion || CVMetalTextureCacheCreate(nullptr, nullptr, device, nullptr, &textureCache) != kCVReturnSuccess) return 0;
    }
    auto descriptor = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:w height:h mipmapped:NO];
    descriptor.storageMode = *raw ? MTLStorageModeShared : MTLStorageModePrivate;
    descriptor.usage = MTLTextureUsageShaderRead;
    owned = [device newTextureWithDescriptor:descriptor];
    if (!owned) return 0;
    rawFile = *raw ? std::fopen(raw, "wb") : nullptr;
    if (*raw && !rawFile) { owned = nil; return 0; }
    if (!*output) return 1;
    if (w % 2 || h % 2) { if (rawFile) std::fclose(rawFile); rawFile = nullptr; return 0; }
    NSError* error = nil;
    writer = [[AVAssetWriter alloc] initWithURL:[NSURL fileURLWithPath:[NSString stringWithUTF8String:output]] fileType:AVFileTypeQuickTimeMovie error:&error];
    input = [AVAssetWriterInput assetWriterInputWithMediaType:AVMediaTypeVideo outputSettings:@{
      AVVideoCodecKey: AVVideoCodecTypeH264, AVVideoWidthKey:@(w), AVVideoHeightKey:@(h),
      AVVideoEncoderSpecificationKey:@{(id)kVTVideoEncoderSpecification_RequireHardwareAcceleratedVideoEncoder:@YES},
      AVVideoColorPropertiesKey:@{AVVideoColorPrimariesKey:AVVideoColorPrimaries_ITU_R_709_2,
        AVVideoTransferFunctionKey:AVVideoTransferFunction_IEC_sRGB,
        AVVideoYCbCrMatrixKey:AVVideoYCbCrMatrix_ITU_R_709_2},
      AVVideoCompressionPropertiesKey:@{AVVideoAverageBitRateKey:@(bitrate),
        AVVideoAllowFrameReorderingKey:@NO, AVVideoExpectedSourceFrameRateKey:@(double(n)/d)}
    }];
    input.expectsMediaDataInRealTime = NO;
    input.mediaTimeScale = numerator;
    adaptor = [AVAssetWriterInputPixelBufferAdaptor assetWriterInputPixelBufferAdaptorWithAssetWriterInput:input sourcePixelBufferAttributes:@{
      (id)kCVPixelBufferPixelFormatTypeKey:@(kCVPixelFormatType_420YpCbCr8BiPlanarVideoRange),
      (id)kCVPixelBufferWidthKey:@(w), (id)kCVPixelBufferHeightKey:@(h),
      (id)kCVPixelBufferMetalCompatibilityKey:@YES, (id)kCVPixelBufferIOSurfacePropertiesKey:@{}
    }];
    if (!writer || ![writer canAddInput:input]) return 0;
    [writer addInput:input];
    if (![writer startWriting]) return 0;
    [writer startSessionAtSourceTime:kCMTimeZero];
    return 1;
  }
}

extern "C" int ve_encoder_submit(void* value, int frame) {
  @autoreleasepool {
    if (failed || frame != submitted || !owned) return 0;
    IOSurfaceRef surface = static_cast<IOSurfaceRef>(value);
    if (IOSurfaceGetWidth(surface) != size_t(width) || IOSurfaceGetHeight(surface) != size_t(height) || IOSurfaceGetPixelFormat(surface) != kCVPixelFormatType_32BGRA) return 0;
    auto descriptor = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:width height:height mipmapped:NO];
    descriptor.storageMode = MTLStorageModeShared;
    descriptor.usage = MTLTextureUsageShaderRead;
    auto source = [device newTextureWithDescriptor:descriptor iosurface:surface plane:0];
    if (!source) return 0;
    auto commands = [queue commandBuffer];
    auto blit = [commands blitCommandEncoder];
    [blit copyFromTexture:source sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0) sourceSize:MTLSizeMake(width,height,1) toTexture:owned destinationSlice:0 destinationLevel:0 destinationOrigin:MTLOriginMake(0,0,0)];
    [blit endEncoding];
    CVPixelBufferRef buffer = nullptr;
    CVMetalTextureRef luma = nullptr, chroma = nullptr;
    const auto waitStarted = std::chrono::steady_clock::now();
    if (writer) {
      const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(10);
      while (!input.readyForMoreMediaData) {
        if (writer.status == AVAssetWriterStatusFailed || std::chrono::steady_clock::now() >= deadline) return 0;
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
      }
      // Hard allocation threshold prevents encoder pressure from growing an unbounded pool.
      const auto attributes = (__bridge CFDictionaryRef)@{(id)kCVPixelBufferPoolAllocationThresholdKey:@6};
      CVReturn allocated;
      do {
        allocated = CVPixelBufferPoolCreatePixelBufferWithAuxAttributes(nullptr, adaptor.pixelBufferPool, attributes, &buffer);
        if (allocated == kCVReturnWouldExceedAllocationThreshold) std::this_thread::sleep_for(std::chrono::milliseconds(1));
      } while (allocated == kCVReturnWouldExceedAllocationThreshold && std::chrono::steady_clock::now() < deadline);
      if (allocated != kCVReturnSuccess) return 0;
      CVBufferSetAttachment(buffer, kCVImageBufferColorPrimariesKey, kCVImageBufferColorPrimaries_ITU_R_709_2, kCVAttachmentMode_ShouldPropagate);
      CVBufferSetAttachment(buffer, kCVImageBufferTransferFunctionKey, kCVImageBufferTransferFunction_sRGB, kCVAttachmentMode_ShouldPropagate);
      CVBufferSetAttachment(buffer, kCVImageBufferYCbCrMatrixKey, kCVImageBufferYCbCrMatrix_ITU_R_709_2, kCVAttachmentMode_ShouldPropagate);
      const auto first = CVMetalTextureCacheCreateTextureFromImage(nullptr, textureCache, buffer, nullptr, MTLPixelFormatR8Unorm, width, height, 0, &luma);
      const auto second = CVMetalTextureCacheCreateTextureFromImage(nullptr, textureCache, buffer, nullptr, MTLPixelFormatRG8Unorm, width/2, height/2, 1, &chroma);
      if (first || second) {
        if (luma) CFRelease(luma); if (chroma) CFRelease(chroma); CFRelease(buffer); return 0;
      }
      auto compute = [commands computeCommandEncoder];
      [compute setComputePipelineState:conversion];
      [compute setTexture:owned atIndex:0];
      [compute setTexture:CVMetalTextureGetTexture(luma) atIndex:1];
      [compute setTexture:CVMetalTextureGetTexture(chroma) atIndex:2];
      [compute dispatchThreads:MTLSizeMake(width,height,1) threadsPerThreadgroup:MTLSizeMake(16,16,1)];
      [compute endEncoding];
    }
    auto gpuDone = dispatch_semaphore_create(0);
    [commands addCompletedHandler:^(id<MTLCommandBuffer>) { dispatch_semaphore_signal(gpuDone); }];
    [commands commit];
    if (dispatch_semaphore_wait(gpuDone, dispatch_time(DISPATCH_TIME_NOW, 10*NSEC_PER_SEC))) {
      // Never return a borrowed CEF surface while a GPU command might still use it.
      // The orchestrator observes process failure and discards this service.
      std::fprintf(stderr, "VibeEdit GPU completion deadline exceeded\n");
      std::_Exit(70);
    }
    metrics[0] = commands.GPUEndTime > commands.GPUStartTime ? commands.GPUEndTime - commands.GPUStartTime : 0;
    metrics[1] = std::chrono::duration<double>(std::chrono::steady_clock::now()-waitStarted).count();
    // CEF can reuse its surface only after this copy/conversion has completed.
    const bool gpuOK = commands.status == MTLCommandBufferStatusCompleted;
    bool accepted = gpuOK;
    const auto appendStarted = std::chrono::steady_clock::now();
    if (gpuOK && writer) accepted = [adaptor appendPixelBuffer:buffer withPresentationTime:CMTimeMake(int64_t(frame)*denominator, numerator)];
    metrics[2] = std::chrono::duration<double>(std::chrono::steady_clock::now()-appendStarted).count();
    if (luma) CFRelease(luma);
    if (chroma) CFRelease(chroma);
    if (buffer) CFRelease(buffer);
    if (gpuOK && rawFile) {
      std::vector<uint8_t> bytes(size_t(width)*height*4);
      [owned getBytes:bytes.data() bytesPerRow:width*4 fromRegion:MTLRegionMake2D(0,0,width,height) mipmapLevel:0];
      accepted = accepted && std::fwrite(bytes.data(), 1, bytes.size(), rawFile) == bytes.size();
    }
    if (!accepted) { failed = true; return 0; }
    ++submitted;
    return 1;
  }
}

extern "C" int ve_encoder_finish() {
  @autoreleasepool {
    bool complete = !failed;
    if (rawFile) { complete = std::fclose(rawFile) == 0 && complete; rawFile = nullptr; }
    if (writer) {
      const auto finishStarted = std::chrono::steady_clock::now();
      [writer endSessionAtSourceTime:CMTimeMake(int64_t(submitted)*denominator, numerator)];
      [input markAsFinished];
      auto done = dispatch_semaphore_create(0);
      [writer finishWritingWithCompletionHandler:^{ dispatch_semaphore_signal(done); }];
      const auto status = dispatch_semaphore_wait(done, dispatch_time(DISPATCH_TIME_NOW, 30*NSEC_PER_SEC));
      complete = complete && status == 0 && writer.status == AVAssetWriterStatusCompleted;
      if (status != 0) [writer cancelWriting];
      if (!complete) NSLog(@"VibeEdit encode failure: %@", writer.error);
      metrics[3] = std::chrono::duration<double>(std::chrono::steady_clock::now()-finishStarted).count();
    }
    writer = nil; input = nil; adaptor = nil; owned = nil;
    if (textureCache) CVMetalTextureCacheFlush(textureCache, 0);
    return complete ? 1 : 0;
  }
}

extern "C" double ve_encoder_metric(int index) { return index >= 0 && index < 4 ? metrics[index] : 0; }
