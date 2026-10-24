use serde_json::{json, Value};
use std::{sync::Mutex, time::Duration};
use tauri::{Emitter, Manager};
use tokio::{
    io::{AsyncReadExt, AsyncWriteExt},
    net::windows::named_pipe::{NamedPipeServer, ServerOptions},
    sync::watch,
};

#[derive(Default)]
pub struct PreviewIpc {
    updates: Mutex<Option<watch::Sender<Value>>>,
}

fn snapshot(app: &tauri::AppHandle) -> Value {
    let state = app.state::<crate::AppState>();
    let mods = state.mod_manager.lock().unwrap().get_mods();
    json!({ "mods": mods })
}

async fn write_message(pipe: &mut NamedPipeServer, value: Value) -> std::io::Result<()> {
    let bytes = serde_json::to_vec(&value)?;
    pipe.write_u32(bytes.len() as u32).await?;
    pipe.write_all(&bytes).await
}

fn create_pipe(first: bool) -> std::io::Result<NamedPipeServer> {
    use windows_sys::Win32::{
        Foundation::{CloseHandle, LocalFree},
        Security::{
            Authorization::{
                ConvertSidToStringSidW, ConvertStringSecurityDescriptorToSecurityDescriptorW,
            },
            GetTokenInformation, TokenUser, SECURITY_ATTRIBUTES, TOKEN_QUERY, TOKEN_USER,
        },
        System::Threading::{GetCurrentProcess, OpenProcessToken},
    };
    let mut descriptor = std::ptr::null_mut();
    unsafe {
        // Use the user SID, including when the manager runs as administrator.
        let mut token = std::ptr::null_mut();
        if OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &mut token) == 0 {
            return Err(std::io::Error::last_os_error());
        }
        let mut length = 0;
        GetTokenInformation(token, TokenUser, std::ptr::null_mut(), 0, &mut length);
        let mut buffer = vec![0usize; (length as usize).div_ceil(std::mem::size_of::<usize>())];
        let result = GetTokenInformation(
            token,
            TokenUser,
            buffer.as_mut_ptr().cast(),
            length,
            &mut length,
        );
        let error = std::io::Error::last_os_error();
        CloseHandle(token);
        if result == 0 {
            return Err(error);
        }
        let user = &*(buffer.as_ptr() as *const TOKEN_USER);
        let mut sid = std::ptr::null_mut();
        if ConvertSidToStringSidW(user.User.Sid, &mut sid) == 0 {
            return Err(std::io::Error::last_os_error());
        }
        let mut length = 0;
        while *sid.add(length) != 0 {
            length += 1;
        }
        let user_sid = String::from_utf16_lossy(std::slice::from_raw_parts(sid, length));
        LocalFree(sid.cast());
        let sddl: Vec<u16> = format!("D:P(A;;GA;;;{user_sid})(A;;GA;;;SY)\0")
            .encode_utf16()
            .collect();
        if ConvertStringSecurityDescriptorToSecurityDescriptorW(
            sddl.as_ptr(),
            1,
            &mut descriptor,
            std::ptr::null_mut(),
        ) == 0
        {
            return Err(std::io::Error::last_os_error());
        }
        let mut attributes = SECURITY_ATTRIBUTES {
            nLength: std::mem::size_of::<SECURITY_ATTRIBUTES>() as u32,
            lpSecurityDescriptor: descriptor,
            bInheritHandle: 0,
        };
        let result = ServerOptions::new()
            .first_pipe_instance(first)
            .reject_remote_clients(true)
            .create_with_security_attributes_raw(
                format!(
                    r"\\.\pipe\BD2ModManager-preview-{}",
                    std::env::var("USERNAME").unwrap_or_default()
                ),
                &mut attributes as *mut _ as *mut _,
            );
        LocalFree(descriptor);
        result
    }
}

async fn serve(app: tauri::AppHandle, mut pipe: NamedPipeServer) -> Result<(), String> {
    let length = tokio::time::timeout(Duration::from_secs(10), pipe.read_u32())
        .await
        .map_err(|e| e.to_string())?
        .map_err(|e| e.to_string())?;
    if length > 65536 {
        return Err("IPC request is too large".into());
    }
    let mut bytes = vec![0; length as usize];
    tokio::time::timeout(Duration::from_secs(10), pipe.read_exact(&mut bytes))
        .await
        .map_err(|e| e.to_string())?
        .map_err(|e| e.to_string())?;
    let request: Value = serde_json::from_slice(&bytes).map_err(|e| e.to_string())?;
    if request["command"] == "subscribe" {
        let mut updates = app
            .state::<PreviewIpc>()
            .updates
            .lock()
            .unwrap()
            .as_ref()
            .unwrap()
            .subscribe();
        loop {
            let value = updates.borrow_and_update().clone();
            tokio::time::timeout(Duration::from_secs(10), write_message(&mut pipe, value))
                .await
                .map_err(|e| e.to_string())?
                .map_err(|e| e.to_string())?;
            tokio::select! {
                result = updates.changed() => if result.is_err() { break; },
                _ = pipe.read_u8() => break,
            }
        }
    } else if request["command"] == "setModEnabled" {
        let name = request["modName"].as_str().ok_or("Missing mod name")?;
        let enabled = request["enabled"]
            .as_bool()
            .ok_or("Missing enabled state")?;
        let result = (|| -> Result<Value, String> {
            let state = app.state::<crate::AppState>();
            let mut manager = state
                .mod_manager
                .try_lock()
                .map_err(|_| "ModManager is busy")?;
            let entry = manager.get_mod_by_name(name).ok_or("Mod was not found")?;
            if !entry.errors.is_empty() {
                return Err("This mod has errors and cannot be changed".into());
            }
            let changed = if enabled {
                manager.enable_mods(vec![name.to_string()])
            } else {
                manager.disable_mods(vec![name.to_string()])
            };
            let mods = manager.get_mods();
            drop(manager);
            app.emit_to("main", "preview-mods-changed", changed)
                .map_err(|e| e.to_string())?;
            Ok(json!({ "mods": mods }))
        })();
        let response = match result {
            Ok(response) => {
                if let Some(sender) = app.state::<PreviewIpc>().updates.lock().unwrap().as_ref() {
                    sender.send_replace(response.clone());
                }
                response
            }
            Err(error) => json!({ "error": error }),
        };
        write_message(&mut pipe, response)
            .await
            .map_err(|e| e.to_string())?;
    } else {
        write_message(&mut pipe, json!({ "error": "Unknown IPC command" }))
            .await
            .map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[tauri::command]
pub async fn start_preview_ipc(app: tauri::AppHandle) -> Result<(), String> {
    let state = app.state::<PreviewIpc>();
    let mut updates = state.updates.lock().unwrap();
    if updates.is_some() {
        return Ok(());
    }
    let mut pipe = create_pipe(true).map_err(|e| e.to_string())?;
    let (sender, _) = watch::channel(snapshot(&app));
    *updates = Some(sender);
    drop(updates);
    tauri::async_runtime::spawn(async move {
        loop {
            if let Err(error) = pipe.connect().await {
                log::error!("Preview IPC connection failed: {error}");
                break;
            }
            let next = match create_pipe(false) {
                Ok(next) => next,
                Err(error) => {
                    log::error!("Preview IPC failed: {error}");
                    break;
                }
            };
            let connected = std::mem::replace(&mut pipe, next);
            let app = app.clone();
            tauri::async_runtime::spawn(async move {
                if let Err(error) = serve(app, connected).await {
                    log::debug!("Preview IPC: {error}");
                }
            });
        }
    });
    Ok(())
}

#[tauri::command]
pub fn publish_preview_mods(app: tauri::AppHandle) {
    if let Some(sender) = app.state::<PreviewIpc>().updates.lock().unwrap().as_ref() {
        sender.send_replace(snapshot(&app));
    }
}
