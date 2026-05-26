//! Tauri shell — spawns bundled mcs-server sidecar and loads the local UI.

use std::net::TcpStream;
use std::time::Duration;
use tauri::{Manager, Url};
use tauri_plugin_shell::{process::CommandEvent, ShellExt};

fn wait_for_port(port: u16, attempts: u32) -> bool {
    let addr = format!("127.0.0.1:{}", port);
    for _ in 0..attempts {
        if TcpStream::connect_timeout(
            &addr.parse().expect("socket addr"),
            Duration::from_millis(300),
        )
        .is_ok()
        {
            return true;
        }
        std::thread::sleep(Duration::from_millis(100));
    }
    false
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let port = std::env::var("MCS_PORT").unwrap_or_else(|_| "8765".into());
            let shell = app.shell();
            let sidecar = shell
                .sidecar("mcs-server")
                .expect("sidecar binary mcs-server not bundled");
            let (mut rx, _child) = sidecar
                .env("MCS_PORT", &port)
                .env("MCS_HEADLESS", "1")
                .spawn()
                .expect("failed to spawn mcs-server");

            let handle = app.handle().clone();
            let port_num: u16 = port.parse().unwrap_or(8765);
            std::thread::spawn(move || {
                if wait_for_port(port_num, 400) {
                    if let Some(win) = handle.get_webview_window("main") {
                        let url = format!("http://127.0.0.1:{}", port_num);
                        if let Ok(parsed) = Url::parse(&url) {
                            let _ = win.navigate(parsed);
                        }
                    }
                }
                while let Some(event) = rx.blocking_recv() {
                    if let CommandEvent::Terminated(payload) = event {
                        eprintln!("mcs-server exited: {:?}", payload);
                        break;
                    }
                }
            });
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
