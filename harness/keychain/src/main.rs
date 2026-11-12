use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::{Duration, Instant};
use std::{env, fs, thread};

use serde_json::json;
use solana_keychain::traits::SolanaSigner;
use solana_keychain::{LedgerConfig, LedgerSigner, SignerError};

const USAGE: &str =
    "usage: keychain-harness <A|B|C|D|E> <commit> <hidraw0000> <hidraw0001> <key0000> <key0001>";
const READS: usize = 50;
const RESTART_BEFORE: usize = 26;
const TIMEOUT: Duration = Duration::from_secs(60);
const BRIDGE_0001: [&str; 4] = ["ledger_rig", "bridge", "--serial", "0001"];
const NO_ERROR_VALUE: &str = "is_available() returned false; no error value";
const BUSY_INFERRED: &str =
    "is_available() call 2 of 2 returned false back to back; busy inferred, no error value";

struct Run {
    hidraw: [String; 2],
    keys: [String; 2],
}

struct Failure {
    error: String,
    detail: String,
}

impl Failure {
    fn unavailable(error: String) -> Self {
        Failure {
            error,
            detail: NO_ERROR_VALUE.to_string(),
        }
    }

    fn at(mut self, i: usize) -> Self {
        self.error = format!("read {i}: {}", self.error);
        self
    }
}

impl From<String> for Failure {
    fn from(error: String) -> Self {
        Failure {
            detail: error.clone(),
            error,
        }
    }
}

impl From<&str> for Failure {
    fn from(error: &str) -> Self {
        error.to_string().into()
    }
}

#[tokio::main(flavor = "current_thread")]
async fn main() {
    let args: Vec<String> = env::args().skip(1).collect();
    let start = Instant::now();
    let (pass, failure) = match args.as_slice() {
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
                "E" => outcome(scenario_e(&run).await),
                _ => (false, Some(format!("unknown scenario {scenario}").into())),
            }
        }
        _ => (false, Some(USAGE.into())),
    };
    println!(
        "{}",
        json!({
            "commit": args.get(1),
            "scenario": args.first(),
            "pass": pass,
            "error": failure.as_ref().map(|f| &f.error),
            "detail": failure.as_ref().map(|f| &f.detail),
            "wall_ms": start.elapsed().as_millis() as u64,
        })
    );
}

fn outcome(result: Result<(), Failure>) -> (bool, Option<Failure>) {
    (result.is_ok(), result.err())
}

fn hold(run: &Run) -> Result<[LedgerSigner; 2], Failure> {
    Ok([
        connect(Some(&run.hidraw[0]))?,
        connect(Some(&run.hidraw[1]))?,
    ])
}

async fn scenario_a(run: &Run) -> Result<(), Failure> {
    let held = hold(run)?;
    for i in 1..=READS {
        let device = 1 - i % 2;
        let key = read(&held[device]).await.map_err(|e| e.at(i))?;
        check(run, i, device, &key)?;
    }
    Ok(())
}

async fn scenario_b(run: &Run) -> (bool, Option<Failure>) {
    let [s0, mut s1] = match hold(run) {
        Ok(held) => held,
        Err(e) => return (false, Some(e)),
    };
    let mut error = None;
    for i in 1..=READS {
        if i == RESTART_BEFORE {
            let path = match restart_0001() {
                Ok(path) => path,
                Err(e) => return (false, error.or(Some(e.into()))),
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
                    return (false, error.or(Some(e.into())));
                }
            }
            Err(e) => {
                error.get_or_insert(e.at(i));
            }
        }
    }
    (true, error)
}

async fn scenario_c(run: &Run) -> Result<(), Failure> {
    let (argv, log) = kill_0001()?;
    let unnamed = connect(None);
    let path = respawn_0001(&argv, &log)?;
    let unnamed = unnamed?;
    if unnamed.pubkey().to_string() != run.keys[0] {
        return Err(format!("unnamed signer returned {}", unnamed.pubkey()).into());
    }
    let named = connect(Some(&path))?;
    for i in 1..=READS {
        if i % 2 == 1 {
            if !unnamed.is_available().await {
                return Err(Failure::unavailable(format!(
                    "unnamed signer unavailable at read {i}"
                )));
            }
        } else {
            let key = read(&named).await.map_err(|e| e.at(i))?;
            check(run, i, 1, &key)?;
        }
    }
    Ok(())
}

async fn scenario_d(run: &Run) -> Result<(), Failure> {
    let held = connect(Some(&run.hidraw[0]))?;
    let key = read(&held).await.map_err(|e| e.at(1))?;
    check(run, 1, 0, &key)?;
    let path = hidraw_0001().ok_or("bridge 0001 not running")?;
    let _second = connect(Some(&path))?;
    let key = read(&held).await.map_err(|e| e.at(2))?;
    Ok(check(run, 2, 0, &key)?)
}

async fn scenario_e(run: &Run) -> Result<(), Failure> {
    let signer = connect(Some(&run.hidraw[0]))?;
    let key = read(&signer).await.map_err(|e| e.at(1))?;
    check(run, 1, 0, &key)?;
    if !signer.is_available().await {
        return Err(Failure {
            error: "read 2: signer unavailable".to_string(),
            detail: BUSY_INFERRED.to_string(),
        });
    }
    Ok(())
}

fn connect(path: Option<&str>) -> Result<LedgerSigner, Failure> {
    let mut config = LedgerConfig {
        auto_open_app: false,
        ..LedgerConfig::default()
    };
    if let Some(path) = path {
        config.host_device_path = Some(path.into());
    }
    LedgerSigner::connect_with(config).map_err(|e| {
        let inner = match &e {
            SignerError::NotAvailable(s)
            | SignerError::UserRejected(s)
            | SignerError::ConfigError(s)
            | SignerError::IoError(s)
            | SignerError::Other(s)
            | SignerError::SigningFailed(s)
            | SignerError::InvalidPublicKey(s) => s.clone(),
            _ => e.to_string(),
        };
        Failure {
            error: e.to_string(),
            detail: format!("{e:?}: {inner}"),
        }
    })
}

async fn read(signer: &LedgerSigner) -> Result<String, Failure> {
    if !signer.is_available().await {
        return Err(Failure::unavailable("signer unavailable".to_string()));
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
    let (argv, log) = kill_0001()?;
    respawn_0001(&argv, &log)
}

fn kill_0001() -> Result<(Vec<String>, PathBuf), String> {
    let (pid, argv) = bridge_0001().ok_or("bridge 0001 not running")?;
    let log = fs::read_link(format!("/proc/{pid}/fd/2"))
        .map_err(|e| format!("read_link /proc/{pid}/fd/2: {e}"))?;
    let killed = Command::new("kill").args(["-9", pid.as_str()]).status();
    if !killed.is_ok_and(|s| s.success()) {
        return Err(format!("kill -9 {pid} failed"));
    }
    wait_for(|| hidraw_0001().is_none().then_some(()))?;
    Ok((argv, log))
}

// A child of PID 1, so `strace -f` on the harness still exits.
fn respawn_0001(argv: &[String], log: &Path) -> Result<String, String> {
    let spawned = Command::new("systemd-run")
        .args(["--quiet", "--collect"])
        .arg(format!("--property=StandardError=append:{}", log.display()))
        .arg("--")
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
