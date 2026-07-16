use std::env;
use std::ffi::c_void;
use std::fs::File;
use std::io::Write;
use std::slice;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::mpsc::{SyncSender, sync_channel};
use std::sync::{Arc, Mutex, OnceLock};
use std::thread;
use std::time::Instant;

struct Frame {
    bytes: Vec<u8>,
}

struct Bridge {
    sender: SyncSender<Frame>,
    pool: Arc<Mutex<Vec<Vec<u8>>>>,
    copied_frames: AtomicU64,
    copy_nanos: AtomicU64,
    queue_wait_nanos: AtomicU64,
    allocated_buffers: AtomicU64,
}

static BRIDGE: OnceLock<Option<Bridge>> = OnceLock::new();
static GPU_SUBMITTED_FRAMES: AtomicU64 = AtomicU64::new(0);
static GPU_SUBMIT_NANOS: AtomicU64 = AtomicU64::new(0);

#[cfg(target_os = "macos")]
unsafe extern "C" {
    fn vibeedit_metal_copy_surface(surface: *mut c_void, width: usize, height: usize) -> i32;
    fn vibeedit_metal_completed_frames() -> u64;
}

#[unsafe(no_mangle)]
pub unsafe extern "C" fn vibeedit_rust_submit_surface(
    surface: *mut c_void,
    width: usize,
    height: usize,
) -> i32 {
    if surface.is_null() || width == 0 || height == 0 {
        return 0;
    }
    #[cfg(target_os = "macos")]
    {
        let started = Instant::now();
        // SAFETY: The adapter imports the callback-scoped IOSurface into a
        // retained Metal texture before returning to CEF.
        let accepted = unsafe { vibeedit_metal_copy_surface(surface, width, height) };
        GPU_SUBMIT_NANOS.fetch_add(started.elapsed().as_nanos() as u64, Ordering::Relaxed);
        if accepted == 0 {
            return 0;
        }
        let submitted = GPU_SUBMITTED_FRAMES.fetch_add(1, Ordering::Relaxed) + 1;
        if env::var("VIBEEDIT_CEF_GPU_FRAMES")
            .ok()
            .and_then(|value| value.parse::<u64>().ok())
            == Some(submitted)
        {
            // SAFETY: This reads an atomic counter owned by the linked adapter.
            let completed = unsafe { vibeedit_metal_completed_frames() };
            eprintln!(
                "VIBEEDIT_RUST_GPU_STATS submitted={} completed={} submit_nanos={}",
                submitted,
                completed,
                GPU_SUBMIT_NANOS.load(Ordering::Relaxed),
            );
        }
        return 1;
    }
    #[cfg(not(target_os = "macos"))]
    0
}

fn bridge() -> Option<&'static Bridge> {
    BRIDGE
        .get_or_init(|| {
            let output = env::var_os("VIBEEDIT_CEF_RAW_OUTPUT")?;
            let depth = env::var("VIBEEDIT_RUST_CHANNEL_DEPTH")
                .ok()
                .and_then(|value| value.parse::<usize>().ok())
                .unwrap_or(4)
                .clamp(1, 64);
            let file = File::create(output).ok()?;
            let (sender, receiver) = sync_channel::<Frame>(depth);
            let pool = Arc::new(Mutex::new(Vec::<Vec<u8>>::with_capacity(depth + 1)));
            let writer_pool = Arc::clone(&pool);
            thread::Builder::new()
                .name("vibeedit-cef-writer".into())
                .spawn(move || {
                    let mut file = file;
                    while let Ok(mut frame) = receiver.recv() {
                        if file.write_all(&frame.bytes).is_err() {
                            break;
                        }
                        frame.bytes.clear();
                        if let Ok(mut buffers) = writer_pool.lock() {
                            buffers.push(frame.bytes);
                        }
                    }
                })
                .ok()?;
            Some(Bridge {
                sender,
                pool,
                copied_frames: AtomicU64::new(0),
                copy_nanos: AtomicU64::new(0),
                queue_wait_nanos: AtomicU64::new(0),
                allocated_buffers: AtomicU64::new(0),
            })
        })
        .as_ref()
}

#[unsafe(no_mangle)]
pub unsafe extern "C" fn vibeedit_rust_submit_frame(
    source: *const u8,
    stride: usize,
    width: usize,
    height: usize,
) -> i32 {
    if source.is_null() || width == 0 || height == 0 || stride < width.saturating_mul(4) {
        return 0;
    }
    let Some(bridge) = bridge() else {
        return 0;
    };
    let started = Instant::now();
    let row_bytes = width * 4;
    let length = row_bytes.saturating_mul(height);
    let pooled = bridge
        .pool
        .lock()
        .ok()
        .and_then(|mut buffers| buffers.pop());
    if pooled.is_none() {
        bridge.allocated_buffers.fetch_add(1, Ordering::Relaxed);
    }
    let mut bytes = pooled.unwrap_or_default();
    bytes.resize(length, 0);
    for row in 0..height {
        // SAFETY: CEF keeps the callback-scoped IOSurface locked while this
        // function copies every validated row into Rust-owned memory.
        let input = unsafe { slice::from_raw_parts(source.add(row * stride), row_bytes) };
        bytes[row * row_bytes..(row + 1) * row_bytes].copy_from_slice(input);
    }
    bridge
        .copy_nanos
        .fetch_add(started.elapsed().as_nanos() as u64, Ordering::Relaxed);
    let copied_frames = bridge.copied_frames.fetch_add(1, Ordering::Relaxed) + 1;
    let queue_started = Instant::now();
    if bridge.sender.send(Frame { bytes }).is_err() {
        return 0;
    }
    bridge
        .queue_wait_nanos
        .fetch_add(queue_started.elapsed().as_nanos() as u64, Ordering::Relaxed);
    if env::var("VIBEEDIT_CEF_RAW_FRAMES")
        .ok()
        .and_then(|value| value.parse::<u64>().ok())
        == Some(copied_frames)
    {
        eprintln!(
            "VIBEEDIT_RUST_SURFACE_STATS frames={} copy_nanos={} queue_wait_nanos={} allocated_buffers={}",
            copied_frames,
            bridge.copy_nanos.load(Ordering::Relaxed),
            bridge.queue_wait_nanos.load(Ordering::Relaxed),
            bridge.allocated_buffers.load(Ordering::Relaxed),
        );
    }
    1
}

#[unsafe(no_mangle)]
pub extern "C" fn vibeedit_rust_copied_frames() -> u64 {
    bridge()
        .map(|value| value.copied_frames.load(Ordering::Relaxed))
        .unwrap_or(0)
}

#[unsafe(no_mangle)]
pub extern "C" fn vibeedit_rust_copy_nanos() -> u64 {
    bridge()
        .map(|value| value.copy_nanos.load(Ordering::Relaxed))
        .unwrap_or(0)
}
