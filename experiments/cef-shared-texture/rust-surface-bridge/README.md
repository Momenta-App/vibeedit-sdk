# Rust CEF surface bridge

This small `cdylib` tests two CEF surface-consumption strategies.

The production-candidate path performs real GPU work:

1. CEF passes its callback-scoped IOSurface to Rust.
2. Rust calls a small platform adapter compiled into the library.
3. The adapter imports the IOSurface as a Metal texture.
4. A three-frame in-flight GPU queue blits it into private GPU memory without
   CPU pixel readback.

The diagnostic CPU path makes the old bottleneck measurable:

1. CEF locks the temporary IOSurface.
2. Rust copies each BGRA row into pooled Rust-owned memory before the callback
   returns.
3. A bounded channel applies backpressure.
4. A dedicated Rust writer thread drains frames concurrently.

The bridge intentionally has no package dependencies. Its build script compiles
the Objective-C++ Metal platform adapter using the macOS toolchain. It is loaded by the
instrumented CEF probe with `dlopen`, so the downloaded CEF sample does not need
to link against Rust at build time.

The Metal path proves direct native GPU import and blit. It does not yet connect
the private texture to the production layer compositor or hardware encoder.
Equivalent D3D and Vulkan/dma-buf adapters are still required for Windows and
Linux. Stable high-level wgpu is not used for IOSurface import because that
external-memory operation is platform-specific.
