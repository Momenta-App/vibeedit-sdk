// The original shared-surface experiments remain under experiments/.
// Production export uses the recovered callback-scoped IOSurface/Metal copy
// with application-owned resources and a bounded hardware encoder.
#[cfg(target_os = "macos")]
mod encoder;
