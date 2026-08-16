from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path, PureWindowsPath
import platform
import re
import shutil
import subprocess
import tempfile
from typing import Any, Callable, Iterable, Mapping, Sequence

from app.runtime_paths import local_data_root
from app.runtime_gpu_compat import TorchRuntimeGpuProbe, probe_torch_runtime_gpu
from app.version import APP_VERSION

GIB = 1024 ** 3
PLAN_RELATIVE_PATH = Path("assets") / "runtime" / "runtime_install_plan.json"
PREFLIGHT_CONFIG_NAME = "runtime_preflight_config.json"

STATUS_READY = "READY"
STATUS_WARNING = "WARNING"
STATUS_BLOCKED = "BLOCKED"
STATUS_INFO = "INFO"


@dataclass(frozen=True)
class RuntimeComponentEstimate:
    id: str
    label: str
    destination: str
    installed_gib: float
    download_gib: float = 0.0
    temporary_gib: float = 0.0
    estimate: bool = True
    notes: str = ""

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RuntimeComponentEstimate":
        return cls(
            id=str(data.get("id", "component")),
            label=str(data.get("label", data.get("id", "Component"))),
            destination=str(data.get("destination", "runtime")),
            installed_gib=max(0.0, float(data.get("installed_gib", 0.0))),
            download_gib=max(0.0, float(data.get("download_gib", 0.0))),
            temporary_gib=max(0.0, float(data.get("temporary_gib", 0.0))),
            estimate=bool(data.get("estimate", True)),
            notes=str(data.get("notes", "")),
        )


@dataclass(frozen=True)
class RuntimeInstallPlan:
    schema: str
    profile_id: str
    label: str
    minimum_reported_cuda: str
    recommended_toolkit: str
    python_version: str
    pytorch_version: str
    components: tuple[RuntimeComponentEstimate, ...]
    safety_margin_percent: float = 10.0
    notes: str = ""

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RuntimeInstallPlan":
        cuda = data.get("cuda") if isinstance(data.get("cuda"), Mapping) else {}
        raw_components = data.get("components") if isinstance(data.get("components"), Sequence) else []
        components = tuple(
            RuntimeComponentEstimate.from_dict(item)
            for item in raw_components
            if isinstance(item, Mapping)
        )
        return cls(
            schema=str(data.get("schema", "unum-sunt-runtime-install-plan-v1")),
            profile_id=str(data.get("profile_id", "default")),
            label=str(data.get("label", "Local AI runtime")),
            minimum_reported_cuda=str(cuda.get("minimum_reported_cuda", "13.0")),
            recommended_toolkit=str(cuda.get("recommended_toolkit", "13.1")),
            python_version=str(cuda.get("python", "3.11.14")),
            pytorch_version=str(cuda.get("pytorch", "2.10.0")),
            components=components,
            safety_margin_percent=max(0.0, float(data.get("safety_margin_percent", 10.0))),
            notes=str(cuda.get("notes", data.get("notes", ""))),
        )


@dataclass
class RuntimePreflightConfig:
    runtime_root: str = ""
    model_root: str = ""

    @staticmethod
    def default_path() -> Path:
        return local_data_root() / PREFLIGHT_CONFIG_NAME

    @classmethod
    def default(cls) -> "RuntimePreflightConfig":
        base = local_data_root()
        return cls(
            runtime_root=str(base / "ai_runtime"),
            model_root=str(base / "ai_models"),
        )

    @classmethod
    def load(cls, path: str | Path | None = None) -> "RuntimePreflightConfig":
        target = Path(path) if path is not None else cls.default_path()
        if not target.exists():
            return cls.default()
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except Exception:
            return cls.default()
        if not isinstance(data, Mapping):
            return cls.default()
        default = cls.default()
        return cls(
            runtime_root=str(data.get("runtime_root") or default.runtime_root),
            model_root=str(data.get("model_root") or default.model_root),
        )

    def save(self, path: str | Path | None = None) -> Path:
        target = Path(path) if path is not None else self.default_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")
        return target


@dataclass(frozen=True)
class NvidiaGpuInfo:
    name: str
    driver_version: str
    memory_mib: int | None = None


@dataclass(frozen=True)
class NvidiaProbe:
    available: bool
    cuda_version: str | None
    gpus: tuple[NvidiaGpuInfo, ...] = ()
    raw_error: str = ""


@dataclass
class PreflightCheck:
    id: str
    label: str
    status: str
    detail: str
    blocking: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StorageTarget:
    destination: str
    path: str
    drive_key: str
    required_bytes: int
    free_bytes: int | None
    components: list[str]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["required_gib"] = round(self.required_bytes / GIB, 2)
        data["free_gib"] = None if self.free_bytes is None else round(self.free_bytes / GIB, 2)
        return data


@dataclass
class RuntimePreflightReport:
    status: str
    profile_id: str
    checked_at_utc: str
    runtime_root: str
    model_root: str
    cuda_target: str
    checks: list[PreflightCheck]
    storage_targets: list[StorageTarget]
    components: list[dict[str, Any]]
    system_info: dict[str, Any]
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "profile_id": self.profile_id,
            "checked_at_utc": self.checked_at_utc,
            "runtime_root": self.runtime_root,
            "model_root": self.model_root,
            "cuda_target": self.cuda_target,
            "checks": [item.to_dict() for item in self.checks],
            "storage_targets": [item.to_dict() for item in self.storage_targets],
            "components": list(self.components),
            "system_info": dict(self.system_info),
            "notes": list(self.notes),
        }

    def save(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        return target

    def summary(self) -> str:
        lines = [f"Local AI Runtime Preflight: {self.status}", f"CUDA target: {self.cuda_target}"]
        for item in self.checks:
            lines.append(f"[{item.status}] {item.label}: {item.detail}")
        return "\n".join(lines)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve_install_plan_path(*, roots: Iterable[Path] | None = None) -> Path | None:
    search_roots = list(roots) if roots is not None else [Path(sys_executable_dir()), _project_root()]
    seen: set[str] = set()
    for root in search_roots:
        resolved = str(Path(root).resolve())
        if resolved in seen:
            continue
        seen.add(resolved)
        candidate = Path(root) / PLAN_RELATIVE_PATH
        if candidate.is_file():
            return candidate
    return None


def sys_executable_dir() -> str:
    import sys
    if bool(getattr(sys, "frozen", False)):
        return str(Path(sys.executable).resolve().parent)
    return str(_project_root())


def load_install_plan(path: str | Path | None = None) -> RuntimeInstallPlan:
    target = Path(path) if path is not None else resolve_install_plan_path()
    if target is None or not target.is_file():
        raise FileNotFoundError("runtime_install_plan.json non trovato")
    data = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError("runtime_install_plan.json deve contenere un oggetto JSON")
    plan = RuntimeInstallPlan.from_dict(data)
    if not plan.components:
        raise ValueError("Il piano runtime non contiene componenti")
    return plan


def version_tuple(value: str | None, *, parts: int = 2) -> tuple[int, ...]:
    if not value:
        return tuple(0 for _ in range(parts))
    numbers = [int(token) for token in re.findall(r"\d+", str(value))[:parts]]
    while len(numbers) < parts:
        numbers.append(0)
    return tuple(numbers)


def cuda_version_compatible(reported: str | None, required: str) -> bool:
    return version_tuple(reported, parts=2) >= version_tuple(required, parts=2)


def parse_nvidia_smi_summary(text: str) -> tuple[str | None, str | None]:
    driver = None
    cuda = None
    driver_match = re.search(r"Driver Version:\s*([0-9.]+)", text, re.IGNORECASE)
    cuda_match = re.search(r"CUDA Version:\s*([0-9.]+)", text, re.IGNORECASE)
    if driver_match:
        driver = driver_match.group(1)
    if cuda_match:
        cuda = cuda_match.group(1)
    return driver, cuda


def parse_gpu_csv(text: str) -> tuple[NvidiaGpuInfo, ...]:
    gpus: list[NvidiaGpuInfo] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 2:
            continue
        memory = None
        if len(parts) >= 3:
            try:
                memory = int(float(parts[2]))
            except ValueError:
                memory = None
        gpus.append(NvidiaGpuInfo(parts[0], parts[1], memory))
    return tuple(gpus)


def probe_nvidia(
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    which: Callable[[str], str | None] = shutil.which,
) -> NvidiaProbe:
    command = which("nvidia-smi")
    if not command:
        return NvidiaProbe(False, None, (), "nvidia-smi non trovato")
    try:
        summary = runner([command], capture_output=True, text=True, timeout=8, check=False)
        if summary.returncode != 0:
            return NvidiaProbe(False, None, (), (summary.stderr or summary.stdout or "nvidia-smi fallito").strip())
        driver, cuda = parse_nvidia_smi_summary(summary.stdout)
        query = runner(
            [command, "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        gpus = parse_gpu_csv(query.stdout) if query.returncode == 0 else ()
        if not gpus and driver:
            gpus = (NvidiaGpuInfo("NVIDIA GPU", driver, None),)
        return NvidiaProbe(bool(cuda and gpus), cuda, gpus, "")
    except Exception as exc:
        return NvidiaProbe(False, None, (), str(exc))


_WINDOWS_INVALID_CHARS = set('<>"|?*')
_WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)}


def validate_windows_path_text(path_text: str) -> tuple[bool, list[str]]:
    value = str(path_text or "").strip()
    errors: list[str] = []
    if not value:
        return False, ["Percorso vuoto"]
    path = PureWindowsPath(value)
    if not path.is_absolute():
        errors.append("Il percorso deve essere assoluto")
    for part in path.parts:
        if part in {path.anchor, "\\", "/"}:
            continue
        clean = part.rstrip(" .")
        if clean != part:
            errors.append(f"Segmento non valido (spazio/punto finale): {part}")
        stem = clean.split(".", 1)[0].upper()
        if stem in _WINDOWS_RESERVED:
            errors.append(f"Nome riservato Windows: {part}")
        if any(char in _WINDOWS_INVALID_CHARS for char in part):
            errors.append(f"Carattere non valido nel segmento: {part}")
        if ":" in part:
            errors.append(f"Due punti non validi nel segmento: {part}")
    return not errors, errors


def nearest_existing_path(path: Path) -> Path | None:
    current = path
    while True:
        if current.exists():
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent


def path_drive_key(path: Path, *, platform_name: str | None = None) -> str:
    platform_name = os.name if platform_name is None else platform_name
    if platform_name == "nt":
        anchor = PureWindowsPath(str(path)).anchor
        return anchor.lower() if anchor else str(path).lower()
    anchor = path.anchor or str(path.resolve().anchor)
    return anchor.lower() if anchor else str(path.resolve())


def probe_writable_path(path: Path) -> tuple[bool, str]:
    existing = nearest_existing_path(path)
    if existing is None:
        return False, "Nessun parent esistente raggiungibile"
    base = existing if existing.is_dir() else existing.parent
    try:
        with tempfile.NamedTemporaryFile(prefix="unum_sunt_preflight_", dir=base, delete=True) as handle:
            handle.write(b"ok")
            handle.flush()
        return True, f"Scrivibile tramite {base}"
    except Exception as exc:
        return False, str(exc)


def disk_free_bytes(path: Path, *, disk_usage: Callable[[str | Path], Any] = shutil.disk_usage) -> int | None:
    existing = nearest_existing_path(path)
    if existing is None:
        return None
    try:
        usage = disk_usage(existing)
        return int(usage.free)
    except Exception:
        return None


def component_peak_bytes(component: RuntimeComponentEstimate) -> int:
    # During installation the final payload and temporary extraction/download
    # can coexist. Download size is informational; temporary_gib represents the
    # extra on-disk headroom explicitly reserved by the plan.
    return int(round((component.installed_gib + component.temporary_gib) * GIB))


def storage_requirements_by_destination(plan: RuntimeInstallPlan) -> dict[str, int]:
    raw: dict[str, int] = {"runtime": 0, "models": 0}
    for component in plan.components:
        raw.setdefault(component.destination, 0)
        raw[component.destination] += component_peak_bytes(component)
    multiplier = 1.0 + plan.safety_margin_percent / 100.0
    return {key: int(round(value * multiplier)) for key, value in raw.items()}


def _physical_memory_bytes() -> int | None:
    try:
        if os.name == "nt":
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = MEMORYSTATUSEX()
            status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return int(status.ullTotalPhys)
        if hasattr(os, "sysconf"):
            pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
            return int(pages * page_size)
    except Exception:
        return None
    return None




def inspect_existing_wangp_config() -> PreflightCheck:
    config_path = local_data_root() / "local_wangp.json"
    if not config_path.is_file():
        return PreflightCheck(
            "runtime.existing",
            "Runtime WanGP esistente",
            STATUS_INFO,
            "Nessuna configurazione WanGP precedente registrata.",
            blocking=False,
        )
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return PreflightCheck(
            "runtime.existing",
            "Runtime WanGP esistente",
            STATUS_WARNING,
            f"Configurazione esistente non leggibile: {exc}",
            blocking=False,
        )
    if not isinstance(data, Mapping):
        return PreflightCheck(
            "runtime.existing",
            "Runtime WanGP esistente",
            STATUS_WARNING,
            "Configurazione esistente non valida.",
            blocking=False,
        )
    candidates = []
    for key in ("working_directory", "python_executable", "wangp_script"):
        value = str(data.get(key, "")).strip()
        if value:
            candidates.append((key, value, Path(value).exists()))
    missing = [f"{key}={value}" for key, value, exists in candidates if not exists]
    if missing:
        return PreflightCheck(
            "runtime.existing",
            "Runtime WanGP esistente",
            STATUS_WARNING,
            "Configurazione trovata ma alcuni percorsi non esistono: " + "; ".join(missing),
            blocking=False,
        )
    if candidates:
        return PreflightCheck(
            "runtime.existing",
            "Runtime WanGP esistente",
            STATUS_INFO,
            "Configurazione WanGP già presente: " + "; ".join(f"{key}={value}" for key, value, _ in candidates),
            blocking=False,
        )
    return PreflightCheck(
        "runtime.existing",
        "Runtime WanGP esistente",
        STATUS_INFO,
        f"Configurazione presente in {config_path}, ma senza percorsi runtime compilati.",
        blocking=False,
    )

def _path_check(
    check_id: str,
    label: str,
    path_text: str,
    *,
    platform_name: str,
    writable_probe: Callable[[Path], tuple[bool, str]],
) -> list[PreflightCheck]:
    checks: list[PreflightCheck] = []
    path = Path(path_text).expanduser()
    if platform_name == "nt":
        valid, errors = validate_windows_path_text(path_text)
    else:
        valid = path.is_absolute()
        errors = [] if valid else ["Il percorso deve essere assoluto"]
    checks.append(PreflightCheck(
        f"{check_id}.syntax",
        f"{label} · validità",
        STATUS_READY if valid else STATUS_BLOCKED,
        str(path) if valid else "; ".join(errors),
        blocking=not valid,
    ))
    if valid:
        writable, detail = writable_probe(path)
        checks.append(PreflightCheck(
            f"{check_id}.writable",
            f"{label} · scrittura",
            STATUS_READY if writable else STATUS_BLOCKED,
            detail,
            blocking=not writable,
        ))
        if platform_name == "nt" and len(str(path)) >= 220:
            checks.append(PreflightCheck(
                f"{check_id}.length",
                f"{label} · lunghezza",
                STATUS_WARNING,
                f"Percorso lungo ({len(str(path))} caratteri): alcuni tool AI possono non gestirlo correttamente.",
                blocking=False,
            ))
    return checks


def run_runtime_preflight(
    config: RuntimePreflightConfig,
    *,
    plan: RuntimeInstallPlan | None = None,
    platform_name: str | None = None,
    is_64bit: bool | None = None,
    nvidia_probe: NvidiaProbe | None = None,
    writable_probe: Callable[[Path], tuple[bool, str]] = probe_writable_path,
    disk_usage: Callable[[str | Path], Any] = shutil.disk_usage,
    memory_bytes: int | None = None,
    existing_runtime_check: Callable[[], PreflightCheck] = inspect_existing_wangp_config,
    torch_runtime_probe: TorchRuntimeGpuProbe | None | bool = False,
) -> RuntimePreflightReport:
    plan = load_install_plan() if plan is None else plan
    platform_name = os.name if platform_name is None else platform_name
    is_64bit = platform.machine().endswith("64") if is_64bit is None else bool(is_64bit)
    nvidia_probe = probe_nvidia() if nvidia_probe is None else nvidia_probe
    memory_bytes = _physical_memory_bytes() if memory_bytes is None else memory_bytes

    checks: list[PreflightCheck] = []
    checks.append(PreflightCheck(
        "platform.windows_x64",
        "Windows x64",
        STATUS_READY if platform_name == "nt" and is_64bit else STATUS_BLOCKED,
        "Windows x64 rilevato" if platform_name == "nt" and is_64bit else f"Piattaforma corrente: {platform.system()} {platform.machine()}",
        blocking=not (platform_name == "nt" and is_64bit),
    ))

    if not nvidia_probe.available:
        checks.append(PreflightCheck(
            "cuda.nvidia_smi",
            "CUDA / driver NVIDIA",
            STATUS_BLOCKED,
            nvidia_probe.raw_error or "nvidia-smi non disponibile o nessuna GPU CUDA rilevabile",
            blocking=True,
        ))
    else:
        compatible = cuda_version_compatible(nvidia_probe.cuda_version, plan.minimum_reported_cuda)
        gpu_summary = "; ".join(
            f"{gpu.name} · driver {gpu.driver_version}" + (f" · {gpu.memory_mib} MiB VRAM" if gpu.memory_mib is not None else "")
            for gpu in nvidia_probe.gpus
        )
        checks.append(PreflightCheck(
            "cuda.compatibility",
            "Compatibilità CUDA",
            STATUS_READY if compatible else STATUS_BLOCKED,
            f"Driver espone CUDA {nvidia_probe.cuda_version or '?'}; richiesto >= {plan.minimum_reported_cuda}. {gpu_summary}",
            blocking=not compatible,
            metadata={"reported_cuda": nvidia_probe.cuda_version, "required_cuda": plan.minimum_reported_cuda},
        ))

    # RAM and GPU model/VRAM are deliberately informational in the R5c7 release-candidate line.
    if memory_bytes is not None:
        checks.append(PreflightCheck(
            "system.ram",
            "RAM fisica",
            STATUS_INFO,
            f"{memory_bytes / GIB:.1f} GiB rilevati · nessuna soglia bloccante in {APP_VERSION}",
            blocking=False,
        ))
    if nvidia_probe.gpus:
        checks.append(PreflightCheck(
            "system.gpu_policy",
            "Policy GPU / VRAM",
            STATUS_INFO,
            "Modello GPU e VRAM registrati a scopo diagnostico; nessuna soglia minima applicata. La compatibilità effettiva viene verificata contro la wheel PyTorch installata.",
            blocking=False,
        ))

    if torch_runtime_probe is False:
        managed_python = Path(config.runtime_root).expanduser() / "wangp_env" / "python.exe"
        torch_probe = probe_torch_runtime_gpu(managed_python) if managed_python.is_file() else None
    else:
        torch_probe = torch_runtime_probe if torch_runtime_probe is not None else None
    if torch_probe is None:
        checks.append(PreflightCheck(
            "torch.gpu_compatibility",
            "GPU ↔ PyTorch runtime",
            STATUS_INFO,
            "Runtime PyTorch non ancora disponibile: la compute capability verrà verificata dopo l'installazione del runtime.",
            blocking=False,
        ))
    elif not torch_probe.available:
        checks.append(PreflightCheck(
            "torch.gpu_compatibility",
            "GPU ↔ PyTorch runtime",
            STATUS_WARNING,
            torch_probe.raw_error or "PyTorch runtime non interrogabile",
            blocking=False,
        ))
    else:
        compatible = torch_probe.default_device_compatible
        checks.append(PreflightCheck(
            "torch.gpu_compatibility",
            "GPU ↔ PyTorch runtime",
            STATUS_READY if compatible else STATUS_WARNING,
            torch_probe.detail(),
            blocking=False,
            metadata={
                "python_version": torch_probe.python_version,
                "torch_version": torch_probe.torch_version,
                "torch_cuda_version": torch_probe.torch_cuda_version,
                "supported_architectures": list(torch_probe.supported_architectures),
                "default_device_compatible": compatible,
            },
        ))

    checks.append(existing_runtime_check())
    checks.extend(_path_check("path.runtime", "Runtime AI", config.runtime_root, platform_name=platform_name, writable_probe=writable_probe))
    checks.extend(_path_check("path.models", "Modelli AI", config.model_root, platform_name=platform_name, writable_probe=writable_probe))

    requirements = storage_requirements_by_destination(plan)
    destination_paths = {"runtime": Path(config.runtime_root).expanduser(), "models": Path(config.model_root).expanduser()}
    drive_buckets: dict[str, dict[str, Any]] = {}
    for destination, required in requirements.items():
        path = destination_paths.get(destination, Path(config.runtime_root).expanduser())
        key = path_drive_key(path, platform_name=platform_name)
        bucket = drive_buckets.setdefault(key, {"required": 0, "path": path, "destinations": [], "components": []})
        bucket["required"] += required
        bucket["destinations"].append(destination)
        bucket["components"].extend([c.label for c in plan.components if c.destination == destination])

    storage_targets: list[StorageTarget] = []
    for key, bucket in drive_buckets.items():
        free = disk_free_bytes(bucket["path"], disk_usage=disk_usage)
        required = int(bucket["required"])
        enough = free is not None and free >= required
        detail = (
            f"Richiesti {required / GIB:.1f} GiB (incluso margine {plan.safety_margin_percent:.0f}%); "
            + (f"liberi {free / GIB:.1f} GiB" if free is not None else "spazio libero non determinabile")
        )
        checks.append(PreflightCheck(
            f"storage.{key or 'target'}",
            f"Spazio disco · {key or bucket['path']}",
            STATUS_READY if enough else STATUS_BLOCKED,
            detail,
            blocking=not enough,
        ))
        storage_targets.append(StorageTarget(
            destination="+".join(bucket["destinations"]),
            path=str(bucket["path"]),
            drive_key=key,
            required_bytes=required,
            free_bytes=free,
            components=list(bucket["components"]),
        ))

    provisional = [component.label for component in plan.components if component.estimate]
    notes = [
        "Il preflight è non distruttivo: non installa né modifica driver, CUDA, Python, Miniconda, PyTorch, WanGP o modelli.",
        "Nessuna soglia minima di RAM, modello GPU o VRAM viene applicata: i valori sono solo diagnostici.",
    ]
    if provisional:
        notes.append("Stime provvisorie di spazio: " + ", ".join(provisional) + ". La linea R5c3 usa il manifest runtime corrente e mantiene separate le stime ancora provvisorie.")

    has_block = any(item.blocking and item.status == STATUS_BLOCKED for item in checks)
    has_warning = any(item.status == STATUS_WARNING for item in checks)
    status = STATUS_BLOCKED if has_block else (STATUS_WARNING if has_warning else STATUS_READY)
    components = []
    for component in plan.components:
        item = asdict(component)
        item["peak_gib"] = round(component_peak_bytes(component) / GIB, 2)
        components.append(item)

    system_info = {
        "platform": platform.system(),
        "platform_release": platform.release(),
        "machine": platform.machine(),
        "ram_gib": None if memory_bytes is None else round(memory_bytes / GIB, 2),
        "cuda_reported": nvidia_probe.cuda_version,
        "gpus": [asdict(gpu) for gpu in nvidia_probe.gpus],
    }
    return RuntimePreflightReport(
        status=status,
        profile_id=plan.profile_id,
        checked_at_utc=datetime.now(timezone.utc).isoformat(),
        runtime_root=str(Path(config.runtime_root).expanduser()),
        model_root=str(Path(config.model_root).expanduser()),
        cuda_target=plan.minimum_reported_cuda,
        checks=checks,
        storage_targets=storage_targets,
        components=components,
        system_info=system_info,
        notes=notes,
    )
