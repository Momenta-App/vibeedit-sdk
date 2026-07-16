#import <Foundation/Foundation.h>
#import <IOSurface/IOSurface.h>
#import <Metal/Metal.h>

#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <cstring>

namespace {
id<MTLDevice> device;
id<MTLCommandQueue> queue;
id<MTLComputePipelineState> compositor;
dispatch_semaphore_t inflight;
std::atomic<uint64_t> completed{0};
std::atomic<uint64_t> submitted{0};

void PrepareMetal() {
  static dispatch_once_t once;
  dispatch_once(&once, ^{
    device = MTLCreateSystemDefaultDevice();
    queue = [device newCommandQueue];
    inflight = dispatch_semaphore_create(3);
    NSError* error = nil;
    NSString* source = @R"(
#include <metal_stdlib>
using namespace metal;

float4 over(float4 bottom, float4 top) {
  float alpha = top.a + bottom.a * (1.0 - top.a);
  return alpha > 0.0 ? float4((top.rgb * top.a + bottom.rgb * bottom.a * (1.0 - top.a)) / alpha, alpha) : float4(0.0);
}

kernel void composite(texture2d<float, access::sample> web [[texture(0)]],
                      texture2d<float, access::write> output [[texture(1)]],
                      constant uint& frame [[buffer(0)]],
                      uint2 position [[thread_position_in_grid]]) {
  if (position.x >= output.get_width() || position.y >= output.get_height()) return;
  constexpr sampler linear(coord::normalized, address::clamp_to_zero, filter::linear);
  float2 size = float2(output.get_width(), output.get_height());
  float2 uv = (float2(position) + 0.5) / size;
  float phase = float(frame) * 0.035;
  float3 nativeBase = mix(float3(0.018, 0.03, 0.07), float3(0.05, 0.20, 0.24), uv.x + 0.12 * sin(uv.y * 10.0 + phase));
  float4 result = float4(nativeBase, 1.0);

  float angle = -0.035;
  float2 centered = uv - 0.5;
  float2 transformed = float2(cos(angle) * centered.x - sin(angle) * centered.y,
                              sin(angle) * centered.x + cos(angle) * centered.y) / 0.94 + 0.5;
  float4 webLayer = web.sample(linear, transformed);
  webLayer.a *= 0.96 * step(0.0, transformed.x) * step(transformed.x, 1.0) * step(0.0, transformed.y) * step(transformed.y, 1.0);
  result = over(result, webLayer);

  float2 circle = uv - float2(0.72 + 0.025 * sin(phase), 0.34);
  float circleMask = smoothstep(0.24, 0.225, length(circle));
  float3 nativeOverlay = float3(0.18 + 0.45 * uv.y, 0.05 + 0.4 * uv.x, 0.34 + 0.25 * sin((uv.x + uv.y) * 18.0));
  float3 screen = 1.0 - (1.0 - result.rgb) * (1.0 - nativeOverlay);
  result.rgb = mix(result.rgb, screen, circleMask * 0.42);
  output.write(result, position);
}
)";
    id<MTLLibrary> library = [device newLibraryWithSource:source options:nil error:&error];
    id<MTLFunction> function = [library newFunctionWithName:@"composite"];
    compositor = function ? [device newComputePipelineStateWithFunction:function error:&error] : nil;
    if (!compositor) NSLog(@"VibeEdit Metal compositor failed: %@", error);
  });
}
}

extern "C" int vibeedit_metal_prepare() {
  PrepareMetal();
  return device && queue && compositor ? 1 : 0;
}

extern "C" int vibeedit_metal_copy_surface(void* value, size_t width, size_t height) {
  @autoreleasepool {
    IOSurfaceRef surface = static_cast<IOSurfaceRef>(value);
    if (!surface || !width || !height) return 0;
    PrepareMetal();
    if (!device || !queue) return 0;
    dispatch_semaphore_wait(inflight, DISPATCH_TIME_FOREVER);
    MTLTextureDescriptor* sharedDescriptor = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:width height:height mipmapped:NO];
    sharedDescriptor.storageMode = MTLStorageModeShared;
    sharedDescriptor.usage = MTLTextureUsageShaderRead;
    id<MTLTexture> source = [device newTextureWithDescriptor:sharedDescriptor iosurface:surface plane:0];
    if (!source) {
      dispatch_semaphore_signal(inflight);
      return 0;
    }
    MTLTextureDescriptor* privateDescriptor = [sharedDescriptor copy];
    const char* qaOutput = std::getenv("VIBEEDIT_METAL_QA_OUTPUT");
    const char* targetValue = std::getenv("VIBEEDIT_CEF_GPU_FRAMES");
    const uint64_t target = targetValue ? std::strtoull(targetValue, nullptr, 10) : 0;
    const uint64_t frame = submitted.fetch_add(1, std::memory_order_relaxed);
    const bool captureQa = qaOutput && target && frame + 1 == target;
    privateDescriptor.storageMode = captureQa ? MTLStorageModeShared : MTLStorageModePrivate;
    privateDescriptor.usage = MTLTextureUsageShaderRead | MTLTextureUsageShaderWrite | MTLTextureUsageRenderTarget;
    id<MTLTexture> destination = [device newTextureWithDescriptor:privateDescriptor];
    id<MTLCommandBuffer> commands = [queue commandBuffer];
    const bool composite = compositor && std::getenv("VIBEEDIT_RUST_GPU_MODE") && std::strcmp(std::getenv("VIBEEDIT_RUST_GPU_MODE"), "composite") == 0;
    if (composite) {
      id<MTLComputeCommandEncoder> compute = [commands computeCommandEncoder];
      uint32_t frameValue = static_cast<uint32_t>(frame);
      [compute setComputePipelineState:compositor];
      [compute setTexture:source atIndex:0];
      [compute setTexture:destination atIndex:1];
      [compute setBytes:&frameValue length:sizeof(frameValue) atIndex:0];
      MTLSize group = MTLSizeMake(16, 16, 1);
      [compute dispatchThreads:MTLSizeMake(width, height, 1) threadsPerThreadgroup:group];
      [compute endEncoding];
    } else {
      id<MTLBlitCommandEncoder> blit = [commands blitCommandEncoder];
      [blit copyFromTexture:source sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0, 0, 0) sourceSize:MTLSizeMake(width, height, 1) toTexture:destination destinationSlice:0 destinationLevel:0 destinationOrigin:MTLOriginMake(0, 0, 0)];
      [blit endEncoding];
    }
    [commands addCompletedHandler:^(id<MTLCommandBuffer>) {
      (void)source;
      (void)destination;
      completed.fetch_add(1, std::memory_order_relaxed);
      dispatch_semaphore_signal(inflight);
    }];
    [commands commit];
    // CEF releases the IOSurface to its reuse pool as soon as
    // OnAcceleratedPaint returns. The GPU must finish reading the shared
    // surface before Rust returns control to CEF.
    [commands waitUntilCompleted];
    if (captureQa) {
      const size_t rowBytes = width * 4;
      auto* bytes = static_cast<uint8_t*>(std::malloc(rowBytes * height));
      if (bytes) {
        [destination getBytes:bytes bytesPerRow:rowBytes fromRegion:MTLRegionMake2D(0, 0, width, height) mipmapLevel:0];
        if (FILE* file = std::fopen(qaOutput, "wb")) {
          std::fwrite(bytes, rowBytes, height, file);
          std::fclose(file);
        }
        std::free(bytes);
      }
    }
    return 1;
  }
}

extern "C" uint64_t vibeedit_metal_completed_frames() {
  return completed.load(std::memory_order_relaxed);
}
