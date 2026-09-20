fn main() {
    tauri_build::build();
    if std::env::var("CARGO_CFG_TARGET_OS").as_deref() == Ok("windows")
        && std::env::var("CARGO_CFG_TARGET_ENV").as_deref() == Ok("msvc")
    {
        // Library unit-test executables do not inherit Tauri's binary resources.
        // TaskDialogIndirect requires Common Controls v6 at process startup.
        println!("cargo:rustc-link-arg=/MANIFEST:EMBED");
        println!("cargo:rustc-link-arg=/MANIFESTDEPENDENCY:type='win32' name='Microsoft.Windows.Common-Controls' version='6.0.0.0' processorArchitecture='*' publicKeyToken='6595b64144ccf1df' language='*'");
        // The application already embeds Tauri's complete manifest in resource.lib.
        // Do not generate a second resource with the same ID for that binary.
        println!("cargo:rustc-link-arg-bin=mklink-ai-probe=/MANIFEST:NO");
    }
}
