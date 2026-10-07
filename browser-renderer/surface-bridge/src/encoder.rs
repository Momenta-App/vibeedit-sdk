use std::ffi::{c_char, c_void};
use std::sync::Mutex;

// Single serialized encoder per warm browser service. No borrowed CEF handle
// crosses this call; the adapter waits for its GPU copy before returning.
static NEXT_FRAME: Mutex<Option<i32>> = Mutex::new(None);
unsafe extern "C" {
    fn ve_encoder_begin(
        output: *const c_char,
        raw: *const c_char,
        width: i32,
        height: i32,
        numerator: i32,
        denominator: i32,
        bitrate: i32,
    ) -> i32;
    fn ve_encoder_submit(surface: *mut c_void, frame: i32) -> i32;
    fn ve_encoder_finish() -> i32;
    fn ve_encoder_metric(index: i32) -> f64;
}

#[unsafe(no_mangle)]
pub extern "C" fn vibeedit_renderer_metric(index: i32) -> f64 {
    let Ok(_guard) = NEXT_FRAME.lock() else {
        return 0.0;
    };
    // SAFETY: Serialized access to the native timing array; the adapter bounds indices.
    unsafe { ve_encoder_metric(index) }
}

#[unsafe(no_mangle)]
pub unsafe extern "C" fn vibeedit_renderer_begin(
    output: *const c_char,
    raw: *const c_char,
    width: i32,
    height: i32,
    numerator: i32,
    denominator: i32,
    bitrate: i32,
) -> i32 {
    if output.is_null()
        || raw.is_null()
        || width < 1
        || height < 1
        || numerator < 1
        || denominator < 1
    {
        return 0;
    }
    let Ok(mut next) = NEXT_FRAME.lock() else {
        return 0;
    };
    if next.is_some() {
        return 0;
    }
    // SAFETY: Strings remain valid during the call and are copied by Objective-C.
    if unsafe { ve_encoder_begin(output, raw, width, height, numerator, denominator, bitrate) } == 0
    {
        return 0;
    }
    *next = Some(0);
    1
}

#[unsafe(no_mangle)]
pub unsafe extern "C" fn vibeedit_renderer_submit(surface: *mut c_void, frame: i32) -> i32 {
    let Ok(mut next) = NEXT_FRAME.lock() else {
        return 0;
    };
    if surface.is_null() || *next != Some(frame) {
        return 0;
    }
    // SAFETY: CEF supplies a live IOSurface until this synchronous copy returns.
    if unsafe { ve_encoder_submit(surface, frame) } == 0 {
        return 0;
    }
    *next = frame.checked_add(1);
    1
}

#[unsafe(no_mangle)]
pub extern "C" fn vibeedit_renderer_finish() -> i32 {
    let Ok(mut next) = NEXT_FRAME.lock() else {
        return 0;
    };
    if next.is_none() {
        return 0;
    }
    // SAFETY: The mutex serializes all native encoder operations.
    let completed = unsafe { ve_encoder_finish() };
    *next = None;
    completed
}
