//! Exercise the production updater library on disposable native installations.
//! MockRuntime supplies only AppHandle; download, signature and install are real.
use std::{env, fs, time::Duration};
use tauri_plugin_updater::UpdaterExt;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = env::args().collect();
    assert_eq!(
        args.len(),
        7,
        "config origin executable current-version expected-file mode"
    );
    let config: serde_json::Value = serde_json::from_slice(&fs::read(&args[1])?)?;
    let mut context = tauri::test::mock_context(tauri::test::noop_assets());
    context.package_info_mut().version = args[4].parse()?;
    context.config_mut().plugins.0.insert(
        "updater".into(),
        serde_json::json!({
            "pubkey": config["plugins"]["updater"]["pubkey"],
            "dangerousInsecureTransportProtocol": true
        }),
    );
    // Loopback HTTP is limited to this test executable; no product configuration changes.
    assert!(args[2].starts_with("http://127.0.0.1:"));
    let app = tauri::test::mock_builder()
        .plugin(tauri_plugin_updater::Builder::new().build())
        .build(context)?;
    tauri::async_runtime::block_on(async {
        let updater = app
            .updater_builder()
            .executable_path(&args[3])
            .no_proxy()
            .timeout(Duration::from_secs(120))
            .endpoints(vec![
                format!("{}/unavailable", args[2]).parse()?,
                format!("{}/latest.json", args[2]).parse()?,
            ])?
            .build()?;
        let update = updater.check().await?;
        if args[6] == "current" {
            assert!(update.is_none(), "Same version must not update");
            println!("NO_UPDATE_PASS");
            return Ok::<(), Box<dyn std::error::Error>>(());
        }
        let update = update.expect("Expected update from synthetic old-version AppHandle");
        assert!(
            update.download_url.path().ends_with(&args[5]),
            "Wrong installer selected"
        );
        let bytes = update.download(|_, _| {}, || {}).await;
        if args[6] == "bad-signature" {
            assert!(bytes.is_err(), "Invalid signature must be rejected");
            println!("INVALID_SIGNATURE_REJECTED");
        } else {
            let bytes = bytes?;
            update.install(bytes)?;
            println!("SIGNED_NATIVE_INSTALL_PASS");
        }
        Ok(())
    })
}
