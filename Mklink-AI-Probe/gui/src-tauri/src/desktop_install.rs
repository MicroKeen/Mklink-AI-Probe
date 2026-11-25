use std::fs::{File, OpenOptions, TryLockError};
use std::io;
use std::path::Path;
use std::sync::Mutex;
use tauri::{Manager, State};

#[derive(Default)]
pub struct DesktopInstall(Mutex<Option<File>>);

impl DesktopInstall {
    fn begin(&self, home: &Path) -> io::Result<bool> {
        let mut held = self.0.lock().unwrap();
        if held.is_some() {
            return Ok(false);
        }
        // Shared with firmware writes from the GUI, CLI and MCP, across probes
        // and workspaces. An idle window or a capture holds no lock.
        let dir = home.join(".mklink");
        std::fs::create_dir_all(&dir)?;
        let file = OpenOptions::new()
            .read(true)
            .write(true)
            .create(true)
            .truncate(false)
            .open(dir.join("desktop-install.lock"))?;
        match file.try_lock() {
            Ok(()) => {
                *held = Some(file);
                Ok(true)
            }
            Err(TryLockError::WouldBlock) => Ok(false),
            Err(TryLockError::Error(error)) => Err(error),
        }
    }
}

#[tauri::command]
pub fn begin_desktop_install(
    app: tauri::AppHandle,
    install: State<'_, DesktopInstall>,
) -> Result<bool, String> {
    let home = app.path().home_dir().map_err(|e| e.to_string())?;
    install.begin(&home).map_err(|e| {
        format!(
            "{}: {e}",
            home.join(".mklink/desktop-install.lock").display()
        )
    })
}

#[tauri::command]
pub fn end_desktop_install(install: State<'_, DesktopInstall>) {
    install.inner().0.lock().unwrap().take();
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn firmware_and_installers_coordinate_across_handles() {
        let home = std::env::temp_dir().join(format!("mklink-update-{}", rand::random::<u64>()));
        let first = DesktopInstall::default();
        let second = DesktopInstall::default();
        assert!(first.begin(&home).unwrap());
        assert!(!first.begin(&home).unwrap());
        assert!(!second.begin(&home).unwrap());
        let path = home.join(".mklink/desktop-install.lock");
        let reader = File::open(&path).unwrap();
        assert!(matches!(
            reader.try_lock_shared(),
            Err(TryLockError::WouldBlock)
        ));
        first.0.lock().unwrap().take();
        reader.try_lock_shared().unwrap();
        assert!(!second.begin(&home).unwrap());
        drop(reader);
        assert!(second.begin(&home).unwrap());
        drop(second);
        std::fs::remove_file(path).unwrap();
        std::fs::remove_dir(home.join(".mklink")).unwrap();
        std::fs::remove_dir(home).unwrap();
    }
}
