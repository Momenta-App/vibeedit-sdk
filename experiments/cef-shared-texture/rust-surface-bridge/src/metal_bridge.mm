#import <Foundation/Foundation.h>
#import <IOSurface/IOSurface.h>
#import <Metal/Metal.h>

#include <atomic>

namespace {
id<MTLDevice> device;
id<MTLCommandQueue> queue;
dispatch_semaphore_t inflight;
std::atomic<uint64_t> completed{0};
}

extern "C" int vibeedit_metal_copy_surface(void* value, size_t width, size_t height) {
  @autoreleasepool {
    IOSurfaceRef surface = static_cast<IOSurfaceRef>(value);
    if (!surface || !width || !height) return 0;
    static dispatch_once_t once;
    dispatch_once(&once, ^{
      device = MTLCreateSystemDefaultDevice();
      queue = [device newCommandQueue];
      inflight = dispatch_semaphore_create(3);
    });
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
    privateDescriptor.storageMode = MTLStorageModePrivate;
    privateDescriptor.usage = MTLTextureUsageShaderRead | MTLTextureUsageRenderTarget;
    id<MTLTexture> destination = [device newTextureWithDescriptor:privateDescriptor];
    id<MTLCommandBuffer> commands = [queue commandBuffer];
    id<MTLBlitCommandEncoder> blit = [commands blitCommandEncoder];
    [blit copyFromTexture:source sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0, 0, 0) sourceSize:MTLSizeMake(width, height, 1) toTexture:destination destinationSlice:0 destinationLevel:0 destinationOrigin:MTLOriginMake(0, 0, 0)];
    [blit endEncoding];
    [commands addCompletedHandler:^(id<MTLCommandBuffer>) {
      (void)source;
      (void)destination;
      completed.fetch_add(1, std::memory_order_relaxed);
      dispatch_semaphore_signal(inflight);
    }];
    [commands commit];
    return 1;
  }
}

extern "C" uint64_t vibeedit_metal_completed_frames() {
  return completed.load(std::memory_order_relaxed);
}
