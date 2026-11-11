use std::process::Command;
use std::time::{Duration, Instant};
use std::{env, fs, thread};

use serde_json::json;
use solana_keychain::traits::SolanaSigner;
use solana_keychain::{LedgerConfig, LedgerSigner};

const USAGE: &str =
    "usage: keychain-harness <A|B|C|D> <commit> <hidraw0000> <hidraw0001> <key0000> <key0001>";
const READS: usize = 50;
const RESTART_BEFORE: usize = 26;
const TIMEOUT: Duration = Duration::from_secs(60);
const BRIDGE_0001: [&str; 4] = ["ledger_rig", "bridge", "--serial", "0001"];

struct Run {
    hidraw: [String; 2],
    keys: [String; 2],
}

#[tokio::main(flavor = "current_thread")]
async fn main() {
    let args: Vec<String> = env::args().skip(1).collect();
    let start = Instant::now();
    let (pass, error) = match args.as_slice() {
        [scenario, _, h0, h1, k0, k1] => {
            let run = Run {
                hidraw: [h0.clone(), h1.clone()],
                keys: [k0.clone(), k1.clone()],
            };
            match scenario.as_str() {
                "A" => outcome(scenario_a(&run).await),
                "B" => scenario_b(&run).await,
                "C" => outcome(scenario_c(&run).await),
                "D" => outcome(scenario_d(&run).await),
                _ => (false, Some(format!("unknown scenario {scenario}"))),
            }
        }
        _ => (false, Some(USAGE.to_string())),
    };
    println!(
        "{}",
        json!({
            "commit": args.get(1),
            "scenario": args.first(),
            "pass": pass,
            "error": error,
            "wall_ms": start.elapsed().as_millis() as u64,
        })
    );
}

fn outcome(result: Result<(), String>) -> (bool, Option<String>) {
    (result.is_ok(), result.err())
}

fn hold(run: &Run) -> Result<[LedgerSigner; 2], String> {
    Ok([
        connect(Some(&run.hidraw[0]))?,
        connect(Some(&run.hidraw[1]))?,
    ])
}

async fn scenario_a(run: &Run) -> Result<(), String> {
    let held = hold(run)?;
    for i in 1..=READS {
        let device = 1 - i % 2;
        let key = read(&held[device])
            .await
            .map_err(|e| format!("read {i}: {e}"))?;
        check(run, i, device, &key)?;
    }
    Ok(())
}

async fn scenario_b(run: &Run) -> (bool, Option<String>) {
    let [s0, mut s1] = match hold(run) {
        Ok(held) => held,
        Err(e) => return (false, Some(e)),
    };
    let mut error = None;
    for i in 1..=READS {
        if i == RESTART_BEFORE {
            let path = match restart_0001() {
                Ok(path) => path,
                Err(e) => return (false, error.or(Some(e))),
            };
            drop(s1);
            s1 = match connect(Some(&path)) {
                Ok(signer) => signer,
                Err(e) => return (false, error.or(Some(e))),
            };
        }
        let device = 1 - i % 2;
        match read([&s0, &s1][device]).await {
            Ok(key) => {
                if let Err(e) = check(run, i, device, &key) {
                    return (false, error.or(Some(e)));
                }
            }
            Err(e) => {
                error.get_or_insert(format!("read {i}: {e}"));
            }
        }
    }
    (true, error)
}

async fn scenario_c(run: &Run) -> Result<(), String> {
    let argv = kill_0001()?;
    let unnamed = connect(None);
    let path = respawn_0001(&argv)?;
    let unnamed = unnamed?;
    if unnamed.pubkey().to_string() != run.keys[0] {
        return Err(format!("unnamed signer returned {}", unnamed.pubkey()));
    }
    let named = connect(Some(&path))?;
    for i in 1..=READS {
        if i % 2 == 1 {
            if !unnamed.is_available().await {
                return Err(format!("unnamed signer unavailable at read {i}"));
            }
        } else {
            let key = read(&named).await.map_err(|e| format!("read {i}: {e}"))?;
            check(run, i, 1, &key)?;
        }
    }
    Ok(())
}

async fn scenario_d(run: &Run) -> Result<(), String> {
    let held = connect(Some(&run.hidraw[0]))?;
    let key = read(&held).await.map_err(|e| format!("read 1: {e}"))?;
    check(run, 1, 0, &key)?;
    let path = hidraw_0001().ok_or("bridge 0001 not running")?;
    let _second = connect(Some(&path))?;
    let key = read(&held).await.map_err(|e| format!("read 2: {e}"))?;
    check(run, 2, 0, &key)
}

fn connect(path: Option<&str>) -> Result<LedgerSigner, String> {
    let mut config = LedgerConfig {
        auto_open_app: false,
        ..LedgerConfig::default()
    };
    if let Some(path) = path {
        config.host_device_path = Some(path.into());
    }
    LedgerSigner::connect_with(config).map_err(|e| e.to_string())
}

async fn read(signer: &LedgerSigner) -> Result<String, String> {
    if !signer.is_available().await {
        return Err("signer unavailable".to_string());
    }
    Ok(signer.pubkey().to_string())
}

fn check(run: &Run, i: usize, device: usize, key: &str) -> Result<(), String> {
    if key == run.keys[device] {
        return Ok(());
    }
    Err(format!("read {i} on {device:04} returned {key}"))
}

fn restart_0001() -> Result<String, String> {
    let argv = kill_0001()?;
    respawn_0001(&argv)
}

fn kill_0001() -> Result<Vec<String>, String> {
    let (pid, argv) = bridge_0001().ok_or("bridge 0001 not running")?;
    let killed = Command::new("kill").args(["-9", pid.as_str()]).status();
    if !killed.is_ok_and(|s| s.success()) {
        return Err(format!("kill -9 {pid} failed"));
    }
    wait_for(|| hidraw_0001().is_none().then_some(()))?;
    Ok(argv)
}

// A child of PID 1, so `strace -f` on the harness still exits.
fn respawn_0001(argv: &[String]) -> Result<String, String> {
    let spawned = Command::new("systemd-run")
        .args(["--quiet", "--collect", "--"])
        .args(argv)
        .status();
    if !spawned.is_ok_and(|s| s.success()) {
        return Err("systemd-run failed".to_string());
    }
    wait_for(hidraw_0001)
}

fn bridge_0001() -> Option<(String, Vec<String>)> {
    fs::read_dir("/proc").ok()?.flatten().find_map(|entry| {
        let pid = entry.file_name().into_string().ok()?;
        let cmdline = fs::read(format!("/proc/{pid}/cmdline")).ok()?;
        let argv: Vec<String> = cmdline
            .split(|&b| b == 0)
            .filter(|a| !a.is_empty())
            .map(|a| String::from_utf8_lossy(a).into_owned())
            .collect();
        BRIDGE_0001
            .iter()
            .all(|word| argv.iter().any(|a| a == word))
            .then_some((pid, argv))
    })
}

fn hidraw_0001() -> Option<String> {
    fs::read_dir("/sys/class/hidraw")
        .ok()?
        .flatten()
        .find(|node| {
            fs::read_to_string(node.path().join("device/uevent"))
                .is_ok_and(|u| u.lines().any(|line| line == "HID_UNIQ=0001"))
        })
        .map(|node| format!("/dev/{}", node.file_name().to_string_lossy()))
}

fn wait_for<T>(check: impl Fn() -> Option<T>) -> Result<T, String> {
    let deadline = Instant::now() + TIMEOUT;
    loop {
        if let Some(found) = check() {
            return Ok(found);
        }
        if Instant::now() > deadline {
            return Err("bridge 0001 did not come back".to_string());
        }
        thread::sleep(Duration::from_millis(100));
    }
}
