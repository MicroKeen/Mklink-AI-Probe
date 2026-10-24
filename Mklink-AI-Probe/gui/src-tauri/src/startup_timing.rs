//! Opt-in, one-shot startup measurements. No arbitrary frontend strings or paths.
use std::collections::BTreeMap;
use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Instant;

pub struct StartupTiming {
    started: Instant,
    output: Option<PathBuf>,
    recorded: AtomicBool,
}

impl StartupTiming {
    pub fn new(path: PathBuf) -> Self {
        Self {
            started: Instant::now(),
            output: (std::env::var("MKLINK_STARTUP_TIMING").as_deref() == Ok("1")).then_some(path),
            recorded: AtomicBool::new(false),
        }
    }

    pub fn record(&self, values: BTreeMap<String, f64>) {
        let Some(path) = &self.output else { return };
        if self.recorded.swap(true, Ordering::Relaxed) { return; }
        let frontend = filtered(values);
        let report = serde_json::json!({
            "native_elapsed_ms": self.started.elapsed().as_secs_f64() * 1000.0,
            "frontend_navigation_ms": frontend,
        });
        if let Ok(bytes) = serde_json::to_vec_pretty(&report) {
            let _ = std::fs::write(path, bytes);
        }
    }
}

fn filtered(values: BTreeMap<String, f64>) -> BTreeMap<String, f64> {
    values.into_iter().filter(|(key, value)| {
        matches!(key.as_str(), "document" | "backend_active" | "backend_done" | "backend_failed"
            | "modules_active" | "modules_done" | "modules_failed" | "workspace_active"
            | "workspace_done" | "workspace_failed" | "ready")
            && value.is_finite() && (0.0..=300_000.0).contains(value)
    }).collect()
}

#[tauri::command]
pub fn record_startup_timing(state: tauri::State<StartupTiming>, timings: BTreeMap<String, f64>) {
    state.record(timings);
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn only_accepts_bounded_numeric_milestones() {
        let values = BTreeMap::from([
            ("ready".into(), 123.0), ("path".into(), 1.0),
            ("document".into(), -1.0), ("modules_done".into(), f64::INFINITY),
            ("backend_done".into(), 300_001.0),
        ]);
        assert_eq!(filtered(values), BTreeMap::from([("ready".into(), 123.0)]));
    }
}
