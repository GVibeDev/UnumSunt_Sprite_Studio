from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
import zipfile
from typing import Any, Callable, Mapping

from app.generation.local_wangp import LocalWanGPConfig
from app.generation.image_provider import LocalWanGPImageConfig
from app.runtime_paths import local_data_root
from app.runtime_preflight import RuntimePreflightConfig, STATUS_BLOCKED, run_runtime_preflight
from app.runtime_gpu_compat import probe_torch_runtime_gpu

MANIFEST_RELATIVE_PATH = Path("assets") / "runtime" / "runtime_components.json"
WAN_ANIMATE_TEMPLATE_RELATIVE_PATH = Path("assets") / "runtime" / "wan_animate_settings_template.json"
INSTALL_STATE_NAME = "runtime_install_state.json"

ProgressCallback = Callable[[str, float, str], None]
CancelCallback = Callable[[], bool]


class RuntimeInstallError(RuntimeError):
    pass


class RuntimeInstallCancelled(RuntimeInstallError):
    pass


@dataclass(frozen=True)
class RuntimeModelSpec:
    id: str
    label: str
    filename: str
    size_bytes: int
    gated: bool = False
    url: str = ""
    repo_id: str = ""
    sha256: str = ""
    license_url: str = ""
    access_url: str = ""

    @classmethod
    def from_dict(cls, model_id: str, data: Mapping[str, Any]) -> "RuntimeModelSpec":
        return cls(
            id=model_id,
            label=str(data.get("label", model_id)),
            filename=str(data.get("filename", "")),
            size_bytes=max(0, int(data.get("size_bytes", 0))),
            gated=bool(data.get("gated", False)),
            url=str(data.get("url", "")),
            repo_id=str(data.get("repo_id", "")),
            sha256=str(data.get("sha256", "")),
            license_url=str(data.get("license_url", "")),
            access_url=str(data.get("access_url", "")),
        )


@dataclass(frozen=True)
class RuntimeComponentsManifest:
    schema: str
    profile_id: str
    miniconda_url: str
    miniconda_filename: str
    miniconda_publisher_hint: str
    wangp_archive_url: str
    wangp_archive_root: str
    wangp_repository: str
    wangp_revision: str
    python_version: str
    pytorch_version: str
    torchvision_version: str
    torchaudio_version: str
    pytorch_index_url: str
    models: dict[str, RuntimeModelSpec]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RuntimeComponentsManifest":
        miniconda = data.get("miniconda") if isinstance(data.get("miniconda"), Mapping) else {}
        wangp = data.get("wangp") if isinstance(data.get("wangp"), Mapping) else {}
        python = data.get("python") if isinstance(data.get("python"), Mapping) else {}
        pytorch = data.get("pytorch") if isinstance(data.get("pytorch"), Mapping) else {}
        raw_models = data.get("models") if isinstance(data.get("models"), Mapping) else {}
        models = {
            str(model_id): RuntimeModelSpec.from_dict(str(model_id), payload)
            for model_id, payload in raw_models.items()
            if isinstance(payload, Mapping)
        }
        return cls(
            schema=str(data.get("schema", "unum-sunt-runtime-components-v1")),
            profile_id=str(data.get("profile_id", "default")),
            miniconda_url=str(miniconda.get("url", "")),
            miniconda_filename=str(miniconda.get("filename", "Miniconda3-latest-Windows-x86_64.exe")),
            miniconda_publisher_hint=str(miniconda.get("publisher_hint", "Anaconda")),
            wangp_archive_url=str(wangp.get("archive_url", "")),
            wangp_archive_root=str(wangp.get("archive_root", "Wan2GP-main")),
            wangp_repository=str(wangp.get("repository", "")),
            wangp_revision=str(wangp.get("revision", "main")),
            python_version=str(python.get("version", "3.11.14")),
            pytorch_version=str(pytorch.get("version", "2.10.0")),
            torchvision_version=str(pytorch.get("torchvision", "0.25.0")),
            torchaudio_version=str(pytorch.get("torchaudio", "2.10.0")),
            pytorch_index_url=str(pytorch.get("index_url", "https://download.pytorch.org/whl/cu130")),
            models=models,
        )


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _runtime_asset_roots() -> list[Path]:
    import sys

    roots: list[Path] = []
    if bool(getattr(sys, "frozen", False)):
        roots.append(Path(sys.executable).resolve().parent)
    roots.append(_project_root())
    return roots


def resolve_runtime_asset(relative_path: Path) -> Path | None:
    for root in _runtime_asset_roots():
        candidate = root / relative_path
        if candidate.is_file():
            return candidate
    return None


def resolve_runtime_components_manifest() -> Path | None:
    return resolve_runtime_asset(MANIFEST_RELATIVE_PATH)


def resolve_wan_animate_settings_template() -> Path | None:
    return resolve_runtime_asset(WAN_ANIMATE_TEMPLATE_RELATIVE_PATH)


def load_runtime_components_manifest(path: str | Path | None = None) -> RuntimeComponentsManifest:
    target = Path(path) if path is not None else resolve_runtime_components_manifest()
    if target is None or not target.is_file():
        raise FileNotFoundError("runtime_components.json non trovato")
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("runtime_components.json non valido")
    manifest = RuntimeComponentsManifest.from_dict(payload)
    if not manifest.miniconda_url or not manifest.wangp_archive_url or not manifest.models:
        raise ValueError("runtime_components.json incompleto")
    return manifest


@dataclass
class RuntimeInstallOptions:
    install_runtime: bool = True
    install_wan_animate: bool = True
    install_krea2: bool = True
    accept_anaconda_tos: bool = False
    accept_krea_license: bool = False
    hf_token: str = ""
    repair: bool = False


@dataclass
class RuntimeInstallState:
    schema: str = "unum-sunt-runtime-install-state-v2"
    profile_id: str = ""
    status: str = "not_installed"
    ownership: str = "managed"
    updated_at_utc: str = ""
    runtime_root: str = ""
    model_root: str = ""
    miniconda_root: str = ""
    env_root: str = ""
    wangp_root: str = ""
    python_executable: str = ""
    wangp_script: str = ""
    settings_template: str = ""
    models: dict[str, dict[str, Any]] = field(default_factory=dict)
    last_error: str = ""

    @staticmethod
    def default_path() -> Path:
        return local_data_root() / INSTALL_STATE_NAME

    @classmethod
    def load(cls, path: str | Path | None = None) -> "RuntimeInstallState":
        target = Path(path) if path is not None else cls.default_path()
        if not target.is_file():
            return cls()
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
        except Exception:
            return cls()
        if not isinstance(payload, Mapping):
            return cls()
        return cls(
            schema=str(payload.get("schema", cls().schema)),
            profile_id=str(payload.get("profile_id", "")),
            status=str(payload.get("status", "not_installed")),
            ownership=str(payload.get("ownership", "managed")),
            updated_at_utc=str(payload.get("updated_at_utc", "")),
            runtime_root=str(payload.get("runtime_root", "")),
            model_root=str(payload.get("model_root", "")),
            miniconda_root=str(payload.get("miniconda_root", "")),
            env_root=str(payload.get("env_root", "")),
            wangp_root=str(payload.get("wangp_root", "")),
            python_executable=str(payload.get("python_executable", "")),
            wangp_script=str(payload.get("wangp_script", "")),
            settings_template=str(payload.get("settings_template", "")),
            models=dict(payload.get("models", {})) if isinstance(payload.get("models"), Mapping) else {},
            last_error=str(payload.get("last_error", "")),
        )

    def save(self, path: str | Path | None = None) -> Path:
        target = Path(path) if path is not None else self.default_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")
        return target


@dataclass(frozen=True)
class RuntimeHealthItem:
    id: str
    ok: bool
    detail: str
    required: bool = True


@dataclass(frozen=True)
class RuntimeHealthReport:
    ready: bool
    items: tuple[RuntimeHealthItem, ...]

    def summary(self) -> str:
        return "\n".join(("READY" if self.ready else "NOT READY",) + tuple(
            f"{'OK' if item.ok else 'FAIL'} · {item.id}: {item.detail}" for item in self.items
        ))


class RuntimeInstaller:
    def __init__(
        self,
        config: RuntimePreflightConfig,
        *,
        manifest: RuntimeComponentsManifest | None = None,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
        urlopen: Callable[..., Any] = urllib.request.urlopen,
        progress: ProgressCallback | None = None,
        cancelled: CancelCallback | None = None,
    ) -> None:
        self.config = config
        self.manifest = manifest or load_runtime_components_manifest()
        self.runner = runner
        self.urlopen = urlopen
        self.progress = progress or (lambda phase, fraction, message: None)
        self.cancelled = cancelled or (lambda: False)
        self.runtime_root = Path(config.runtime_root).expanduser()
        self.model_root = Path(config.model_root).expanduser()
        self.miniconda_root = self.runtime_root / "miniconda"
        self.env_root = self.runtime_root / "wangp_env"
        self.wangp_root = self.runtime_root / "WanGP"
        self.download_root = self.runtime_root / ".downloads"
        self.ckpts_root = self.model_root / "wangp_ckpts"
        self.state = RuntimeInstallState.load()

    def _emit(self, phase: str, fraction: float, message: str) -> None:
        if self.cancelled():
            raise RuntimeInstallCancelled("Installazione annullata dall'utente")
        self.progress(phase, max(0.0, min(1.0, fraction)), message)

    def _run(self, command: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None, timeout: int = 0) -> subprocess.CompletedProcess[str]:
        self._emit("command", 0.0, " ".join(command[:4]))
        completed = self.runner(
            command,
            cwd=str(cwd) if cwd else None,
            env=env,
            capture_output=True,
            text=True,
            timeout=None if timeout <= 0 else timeout,
            check=False,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or f"exit {completed.returncode}").strip()
            raise RuntimeInstallError(f"Comando fallito ({completed.returncode}): {' '.join(command)}\n{detail}")
        return completed

    @staticmethod
    def _sha256(path: Path, *, chunk_size: int = 8 * 1024 * 1024) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(chunk_size), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _download(self, url: str, target: Path, *, expected_size: int = 0, expected_sha256: str = "", phase: str = "download") -> Path:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_file():
            size_ok = not expected_size or target.stat().st_size == expected_size
            hash_ok = not expected_sha256 or self._sha256(target).lower() == expected_sha256.lower()
            if size_ok and hash_ok:
                self._emit(phase, 1.0, f"Già presente: {target.name}")
                return target
        part = target.with_suffix(target.suffix + ".part")
        existing = part.stat().st_size if part.exists() else 0
        headers = {"User-Agent": "UnumSuntSpriteStudio-R5c6"}
        if existing:
            headers["Range"] = f"bytes={existing}-"
        request = urllib.request.Request(url, headers=headers)
        try:
            response = self.urlopen(request, timeout=60)
        except urllib.error.HTTPError as exc:
            if exc.code == 416 and part.exists():
                part.replace(target)
                return self._download(url, target, expected_size=expected_size, expected_sha256=expected_sha256, phase=phase)
            raise RuntimeInstallError(f"Download HTTP {exc.code}: {url}") from exc
        content_length = int(response.headers.get("Content-Length") or 0)
        total = expected_size or (existing + content_length if content_length else 0)
        mode = "ab" if existing and getattr(response, "status", 200) == 206 else "wb"
        if mode == "wb":
            existing = 0
        written = existing
        with part.open(mode) as handle:
            while True:
                if self.cancelled():
                    raise RuntimeInstallCancelled("Download annullato")
                chunk = response.read(8 * 1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
                written += len(chunk)
                fraction = (written / total) if total else 0.0
                self.progress(phase, fraction, f"{target.name}: {written / (1024**3):.2f} / {(total / (1024**3)) if total else 0:.2f} GiB")
        part.replace(target)
        if expected_size and target.stat().st_size != expected_size:
            raise RuntimeInstallError(f"Dimensione non valida per {target.name}: {target.stat().st_size} != {expected_size}")
        if expected_sha256:
            actual = self._sha256(target)
            if actual.lower() != expected_sha256.lower():
                raise RuntimeInstallError(f"SHA-256 non valido per {target.name}: {actual}")
        return target

    def _verify_windows_signature(self, path: Path, publisher_hint: str) -> None:
        if os.name != "nt":
            return
        escaped = str(path).replace("'", "''")
        command = [
            "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
            f"$s=Get-AuthenticodeSignature -LiteralPath '{escaped}'; Write-Output ($s.Status.ToString()+'|'+$s.SignerCertificate.Subject); if($s.Status -ne 'Valid'){{exit 7}}",
        ]
        completed = self._run(command, timeout=60)
        output = (completed.stdout or "").strip()
        if publisher_hint and publisher_hint.lower() not in output.lower():
            raise RuntimeInstallError(f"Firma Miniconda valida ma publisher inatteso: {output}")

    def _ensure_miniconda(self, *, accept_tos: bool) -> None:
        conda = self.miniconda_root / "Scripts" / "conda.exe"
        if conda.is_file():
            self._emit("miniconda", 1.0, "Miniconda già installato")
            return
        if not accept_tos:
            raise RuntimeInstallError("È necessario accettare i termini Anaconda/Miniconda prima dell'installazione automatica.")
        installer = self._download(
            self.manifest.miniconda_url,
            self.download_root / self.manifest.miniconda_filename,
            phase="miniconda.download",
        )
        self._verify_windows_signature(installer, self.manifest.miniconda_publisher_hint)
        self.miniconda_root.parent.mkdir(parents=True, exist_ok=True)
        if os.name != "nt":
            raise RuntimeInstallError("L'installazione Miniconda R5c6 è supportata solo su Windows.")
        args = [
            str(installer),
            "/InstallationType=JustMe",
            "/RegisterPython=0",
            "/AddToPath=0",
            "/S",
            f"/D={self.miniconda_root}",
        ]
        self._run(args, timeout=1800)
        if not conda.is_file():
            raise RuntimeInstallError(f"Miniconda installato ma conda.exe non trovato: {conda}")

    def _ensure_env(self, *, accept_tos: bool) -> Path:
        python = self.env_root / "python.exe"
        if python.is_file():
            completed = self._run([str(python), "-c", "import platform; print(platform.python_version())"], timeout=30)
            if completed.stdout.strip().startswith("3.11."):
                return python
            if self.env_root.exists():
                shutil.rmtree(self.env_root)
        conda = self.miniconda_root / "Scripts" / "conda.exe"
        env = os.environ.copy()
        if accept_tos:
            env["CONDA_PLUGINS_AUTO_ACCEPT_TOS"] = "yes"
        self._run([
            str(conda), "create", "-y", "-p", str(self.env_root), f"python={self.manifest.python_version}"
        ], env=env, timeout=1800)
        if not python.is_file():
            raise RuntimeInstallError("Ambiente WanGP creato senza python.exe")
        return python

    def _ensure_wangp_source(self, *, repair: bool) -> None:
        marker = self.wangp_root / "wgp.py"
        settings_marker = self.wangp_root / "models" / "_settings.json"
        if marker.is_file() and settings_marker.is_file() and not repair:
            self._emit("wangp.source", 1.0, "Sorgenti WanGP già presenti")
            return
        archive_target = self.download_root / "Wan2GP-main.zip"
        if repair and archive_target.exists():
            archive_target.unlink()
        archive = self._download(self.manifest.wangp_archive_url, archive_target, phase="wangp.download")
        staging = self.runtime_root / ".wangp_extract"
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive, "r") as zf:
            zf.extractall(staging)
        source = staging / self.manifest.wangp_archive_root
        if not source.is_dir():
            raise RuntimeInstallError(f"Root archivio WanGP non trovata: {source}")
        backup = self.runtime_root / "WanGP.backup"
        if backup.exists():
            shutil.rmtree(backup)
        if self.wangp_root.exists():
            self.wangp_root.replace(backup)
        source.replace(self.wangp_root)
        shutil.rmtree(staging, ignore_errors=True)
        if backup.exists():
            for relative in ("settings", "wgp_config.json", "plugins_local.json"):
                old = backup / relative
                new = self.wangp_root / relative
                if old.exists() and not new.exists():
                    if old.is_dir():
                        shutil.copytree(old, new)
                    else:
                        shutil.copy2(old, new)
        self._ensure_ckpts_link()

    def _ensure_ckpts_link(self) -> None:
        self.ckpts_root.mkdir(parents=True, exist_ok=True)
        link = self.wangp_root / "ckpts"
        if link.exists():
            return
        if os.name == "nt":
            completed = self.runner(["cmd.exe", "/c", "mklink", "/J", str(link), str(self.ckpts_root)], capture_output=True, text=True, check=False)
            if completed.returncode == 0 and link.exists():
                return
        # Safe fallback when junction creation is unavailable: use a normal
        # directory under WanGP and update the effective ckpts root.
        link.mkdir(parents=True, exist_ok=True)
        self.ckpts_root = link

    def _install_python_stack(self, python: Path) -> None:
        self._run([str(python), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"], timeout=1800)
        self._run([
            str(python), "-m", "pip", "install",
            f"torch=={self.manifest.pytorch_version}",
            f"torchvision=={self.manifest.torchvision_version}",
            f"torchaudio=={self.manifest.torchaudio_version}",
            "--index-url", self.manifest.pytorch_index_url,
        ], timeout=3600)
        requirements = self.wangp_root / "requirements.txt"
        if not requirements.is_file():
            raise RuntimeInstallError(f"requirements.txt WanGP non trovato: {requirements}")
        self._run([str(python), "-m", "pip", "install", "-r", str(requirements)], cwd=self.wangp_root, timeout=7200)
        # WanGP currently pins Transformers 4.54.0, whose runtime contract
        # requires huggingface-hub >=0.34,<1.0.  Do not blindly upgrade the
        # Hub client to 1.x after resolving WanGP requirements: that makes
        # Transformers fail at import time.  Re-assert the compatible range
        # explicitly so both fresh installs and Repair downgrade an already
        # broken environment deterministically.
        self._run([
            str(python), "-m", "pip", "install", "--upgrade",
            "huggingface_hub[hf_xet]>=0.34.0,<1.0",
        ], timeout=1800)

    def _install_animate(self) -> Path:
        spec = self.manifest.models["wan_animate"]
        self._ensure_ckpts_link()
        return self._download(
            spec.url,
            self.ckpts_root / spec.filename,
            expected_size=spec.size_bytes,
            expected_sha256=spec.sha256,
            phase="model.animate",
        )

    def _install_krea2(self, python: Path, *, token: str, accepted: bool) -> Path:
        spec = self.manifest.models["krea2_turbo"]
        if not accepted:
            raise RuntimeInstallError("Krea 2 richiede accettazione esplicita della Krea 2 Community License e AUP.")
        if not token.strip():
            raise RuntimeInstallError("Krea 2 è gated: inserire un token Hugging Face con accesso già autorizzato al modello.")
        self._ensure_ckpts_link()
        target = self.ckpts_root / spec.filename
        if target.is_file() and (not spec.size_bytes or target.stat().st_size >= int(spec.size_bytes * 0.95)):
            return target
        helper = (
            "from huggingface_hub import hf_hub_download; import os,sys; "
            "p=hf_hub_download(repo_id=sys.argv[1], filename=sys.argv[2], token=os.environ.get('HF_TOKEN'), "
            "local_dir=sys.argv[3]); print(p)"
        )
        env = os.environ.copy()
        env["HF_TOKEN"] = token.strip()
        self._run([str(python), "-c", helper, spec.repo_id, spec.filename, str(self.ckpts_root)], env=env, timeout=21600)
        if not target.is_file():
            raise RuntimeInstallError(f"Download Krea 2 completato ma checkpoint non trovato: {target}")
        return target

    def expected_wangp_python(self) -> Path:
        return self.env_root / "python.exe"

    def _validate_bridge_python(self, python: Path) -> None:
        expected = self.expected_wangp_python().resolve()
        actual = Path(python).expanduser().resolve()
        if actual != expected:
            raise RuntimeInstallError(
                f"Interprete bridge WanGP non valido: {actual}. Atteso ambiente dedicato: {expected}"
            )
        if not actual.is_file():
            raise RuntimeInstallError(f"Python WanGP non trovato: {actual}")
        completed = self._run([
            str(actual), "-c",
            "import platform,torch; print(platform.python_version()); print(torch.__version__); print(torch.cuda.is_available())",
        ], timeout=60)
        lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
        if len(lines) < 3 or not lines[0].startswith("3.11."):
            raise RuntimeInstallError(
                "Ambiente WanGP non conforme: richiesto Python 3.11.x con PyTorch installato."
            )
        if lines[2].lower() != "true":
            raise RuntimeInstallError(
                "PyTorch è presente nell'ambiente WanGP ma CUDA non è disponibile (torch.cuda.is_available() == False)."
            )

    def sync_bridge_configs(self, *, validate: bool = True) -> Path:
        python = self.expected_wangp_python()
        if validate:
            self._validate_bridge_python(python)
        self._write_bridge_config(python, _validated=True)
        return python

    def _managed_animate_template(self) -> Path:
        template = resolve_wan_animate_settings_template()
        if template is None:
            raise RuntimeInstallError(
                f"Template Wan Animate gestito non trovato: {WAN_ANIMATE_TEMPLATE_RELATIVE_PATH.as_posix()}"
            )
        try:
            payload = json.loads(template.read_text(encoding="utf-8"))
        except Exception as exc:
            raise RuntimeInstallError(f"Template Wan Animate gestito non valido: {exc}") from exc
        if not isinstance(payload, Mapping):
            raise RuntimeInstallError("Template Wan Animate gestito non contiene un oggetto JSON.")
        if str(payload.get("model_type", "")).strip().lower() != "animate":
            raise RuntimeInstallError("Template Wan Animate gestito privo di model_type='animate'.")
        if not str(payload.get("model_filename", "")).strip():
            raise RuntimeInstallError("Template Wan Animate gestito privo di model_filename.")
        return template.resolve()

    def _write_bridge_config(self, python: Path, *, _validated: bool = False) -> None:
        if not _validated:
            self._validate_bridge_python(python)
        animate_template = self._managed_animate_template()
        video_config = LocalWanGPConfig.load()
        video_config.python_executable = str(python)
        video_config.wangp_script = str(self.wangp_root / "wgp.py")
        video_config.settings_template = str(animate_template)
        video_config.working_directory = str(self.wangp_root)
        video_config.strict_python_311 = True
        video_config.require_template = True
        video_config.save()

        image_config = LocalWanGPImageConfig.load()
        image_config.python_executable = str(python)
        image_config.wangp_script = str(self.wangp_root / "wgp.py")
        image_config.working_directory = str(self.wangp_root)
        image_config.strict_python_311 = True
        image_config.save()

    def install(self, options: RuntimeInstallOptions) -> RuntimeInstallState:
        report = run_runtime_preflight(self.config)
        if report.status == STATUS_BLOCKED:
            raise RuntimeInstallError("Preflight BLOCKED. Correggere CUDA, spazio o percorsi prima dell'installazione.\n" + report.summary())
        self.runtime_root.mkdir(parents=True, exist_ok=True)
        self.model_root.mkdir(parents=True, exist_ok=True)
        self.download_root.mkdir(parents=True, exist_ok=True)
        self.state = RuntimeInstallState(
            profile_id=self.manifest.profile_id,
            status="installing",
            ownership="managed",
            updated_at_utc=datetime.now(timezone.utc).isoformat(),
            runtime_root=str(self.runtime_root),
            model_root=str(self.model_root),
            miniconda_root=str(self.miniconda_root),
            env_root=str(self.env_root),
            wangp_root=str(self.wangp_root),
            models=dict(self.state.models),
        )
        self.state.save()
        try:
            python: Path | None = None
            if options.install_runtime:
                self._emit("runtime", 0.02, "Preparazione Miniconda")
                self._ensure_miniconda(accept_tos=options.accept_anaconda_tos)
                self._emit("runtime", 0.12, "Creazione ambiente Python 3.11")
                python = self._ensure_env(accept_tos=options.accept_anaconda_tos)
                self._emit("runtime", 0.20, "Installazione/aggiornamento WanGP")
                self._ensure_wangp_source(repair=options.repair)
                self._emit("runtime", 0.32, "Installazione PyTorch CUDA e dipendenze WanGP")
                self._install_python_stack(python)
                self.sync_bridge_configs(validate=True)
            else:
                python = self.env_root / "python.exe"
                if not python.is_file():
                    raise RuntimeInstallError("Runtime base non installato: impossibile installare/gestire i modelli.")
                self._ensure_ckpts_link()

            if options.install_wan_animate:
                self._emit("model.animate", 0.50, "Installazione Wan 2.2 Animate 14B")
                path = self._install_animate()
                self.state.models["wan_animate"] = {"status": "installed", "path": str(path), "bytes": path.stat().st_size}
                self.state.save()
            if options.install_krea2:
                self._emit("model.krea2", 0.72, "Installazione Krea 2 Turbo")
                path = self._install_krea2(python, token=options.hf_token, accepted=options.accept_krea_license)
                self.state.models["krea2_turbo"] = {"status": "installed", "path": str(path), "bytes": path.stat().st_size}
                self.state.save()

            self.state.python_executable = str(self.env_root / "python.exe")
            self.state.wangp_script = str(self.wangp_root / "wgp.py")
            try:
                self.state.settings_template = str(self._managed_animate_template())
            except Exception:
                self.state.settings_template = ""
            health = self.health_check()
            self.state.status = "ready" if health.ready else "warning"
            self.state.updated_at_utc = datetime.now(timezone.utc).isoformat()
            self.state.last_error = ""
            self.state.save()
            self._emit("complete", 1.0, "Runtime AI installato e configurato")
            return self.state
        except Exception as exc:
            self.state.status = "failed"
            self.state.updated_at_utc = datetime.now(timezone.utc).isoformat()
            self.state.last_error = str(exc)
            self.state.save()
            raise

    def health_check(self) -> RuntimeHealthReport:
        items: list[RuntimeHealthItem] = []
        conda = self.miniconda_root / "Scripts" / "conda.exe"
        python = self.env_root / "python.exe"
        wgp = self.wangp_root / "wgp.py"
        settings = self.wangp_root / "models" / "_settings.json"
        items.append(RuntimeHealthItem("miniconda", conda.is_file(), str(conda)))
        items.append(RuntimeHealthItem("python311", python.is_file(), str(python)))
        items.append(RuntimeHealthItem("wangp", wgp.is_file() and settings.is_file(), str(wgp)))
        try:
            managed_template = self._managed_animate_template()
            template_payload = json.loads(managed_template.read_text(encoding="utf-8"))
            template_ok = (
                isinstance(template_payload, Mapping)
                and str(template_payload.get("model_type", "")).strip().lower() == "animate"
                and bool(str(template_payload.get("model_filename", "")).strip())
            )
            template_detail = f"{managed_template} · model_type={template_payload.get('model_type')!r}"
        except Exception as exc:
            template_ok = False
            template_detail = str(exc)
        items.append(RuntimeHealthItem("wan.animate_template", template_ok, template_detail))
        nvcc = shutil.which("nvcc")
        if not nvcc:
            cuda_path = os.environ.get("CUDA_PATH", "").strip()
            if cuda_path:
                candidate = Path(cuda_path) / "bin" / "nvcc.exe"
                if candidate.is_file():
                    nvcc = str(candidate)
        if nvcc:
            toolkit_probe = self.runner([nvcc, "--version"], capture_output=True, text=True, timeout=30, check=False)
            toolkit_detail = (toolkit_probe.stdout or toolkit_probe.stderr or nvcc).strip().replace("\n", " | ")
            items.append(RuntimeHealthItem("cuda.toolkit", toolkit_probe.returncode == 0, toolkit_detail, required=False))
        else:
            items.append(RuntimeHealthItem(
                "cuda.toolkit",
                False,
                "CUDA Toolkit/nvcc non rilevato. Non blocca il runtime PyTorch cu130; può essere richiesto da kernel/acceleratori opzionali WanGP.",
                required=False,
            ))
        if python.is_file():
            torch_probe = probe_torch_runtime_gpu(python, runner=self.runner)
            torch_runtime_ok = (
                torch_probe.available
                and torch_probe.python_version.startswith("3.11.")
                and torch_probe.cuda_available
            )
            items.append(RuntimeHealthItem("torch.cuda", torch_runtime_ok, torch_probe.detail()))
            gpu_contract_ok = torch_runtime_ok and torch_probe.default_device_compatible
            items.append(RuntimeHealthItem(
                "torch.gpu_compatibility",
                gpu_contract_ok,
                torch_probe.detail() if torch_probe.available else torch_probe.raw_error,
            ))

            hf_probe = self.runner(
                [
                    str(python), "-c",
                    "import transformers,huggingface_hub; "
                    "print(transformers.__version__); print(huggingface_hub.__version__)",
                ],
                capture_output=True, text=True, timeout=60, check=False,
            )
            hf_lines = [line.strip() for line in hf_probe.stdout.splitlines() if line.strip()]
            hf_detail = " | ".join(hf_lines) if hf_lines else (hf_probe.stderr or "Transformers/Hugging Face probe failed").strip()
            items.append(RuntimeHealthItem("huggingface.compat", hf_probe.returncode == 0, hf_detail))

            pip_check = self.runner(
                [str(python), "-m", "pip", "check"],
                capture_output=True, text=True, timeout=120, check=False,
            )
            pip_detail = (pip_check.stdout or pip_check.stderr or "pip check: OK").strip().replace("\n", " | ")
            items.append(RuntimeHealthItem("python.pip_check", pip_check.returncode == 0, pip_detail, required=False))
        for model_id, spec in self.manifest.models.items():
            path = self.ckpts_root / spec.filename
            if model_id == "wan_animate" and path.is_file() and spec.sha256:
                ok = path.stat().st_size == spec.size_bytes
                detail = f"{path} · {path.stat().st_size} bytes"
            else:
                ok = path.is_file() and (not spec.size_bytes or path.stat().st_size >= int(spec.size_bytes * 0.95))
                detail = str(path)
            items.append(RuntimeHealthItem(f"model.{model_id}", ok, detail, required=False))
        ready = all(item.ok for item in items if item.required)
        return RuntimeHealthReport(ready, tuple(items))

    def remove_model(self, model_id: str) -> bool:
        spec = self.manifest.models.get(model_id)
        if spec is None:
            raise KeyError(model_id)
        path = self.ckpts_root / spec.filename
        removed = False
        if path.is_file():
            path.unlink()
            removed = True
        self.state.models.pop(model_id, None)
        self.state.updated_at_utc = datetime.now(timezone.utc).isoformat()
        self.state.save()
        return removed
