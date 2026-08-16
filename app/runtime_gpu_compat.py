from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Callable, Mapping


@dataclass(frozen=True)
class TorchGpuDevice:
    index: int
    name: str
    capability: str
    architecture: str
    compatible: bool


@dataclass(frozen=True)
class TorchRuntimeGpuProbe:
    available: bool
    python_version: str = ""
    torch_version: str = ""
    torch_cuda_version: str = ""
    cuda_available: bool = False
    supported_architectures: tuple[str, ...] = ()
    devices: tuple[TorchGpuDevice, ...] = ()
    raw_error: str = ""

    @property
    def default_device_compatible(self) -> bool:
        return bool(self.cuda_available and self.devices and self.devices[0].compatible)

    @property
    def any_device_compatible(self) -> bool:
        return bool(self.cuda_available and any(device.compatible for device in self.devices))

    def detail(self) -> str:
        if not self.available:
            return self.raw_error or "PyTorch runtime non interrogabile"
        supported = " ".join(self.supported_architectures) or "non dichiarate"
        if not self.devices:
            return (
                f"Python {self.python_version} · torch {self.torch_version} · CUDA {self.torch_cuda_version or '?'} · "
                f"torch.cuda.is_available={self.cuda_available} · architetture wheel: {supported}"
            )
        device_text = "; ".join(
            f"GPU{device.index} {device.name} · {device.architecture} ({'compatibile' if device.compatible else 'NON compatibile'})"
            for device in self.devices
        )
        return (
            f"Python {self.python_version} · torch {self.torch_version} · CUDA {self.torch_cuda_version or '?'} · "
            f"architetture wheel: {supported} · {device_text}"
        )


def capability_to_architecture(value: str | tuple[int, int] | list[int]) -> str:
    if isinstance(value, (tuple, list)) and len(value) >= 2:
        return f"sm_{int(value[0])}{int(value[1])}"
    numbers = re.findall(r"\d+", str(value))
    if len(numbers) >= 2:
        return f"sm_{int(numbers[0])}{int(numbers[1])}"
    return ""


def architecture_supported(capability: str | tuple[int, int] | list[int], supported: tuple[str, ...] | list[str]) -> bool:
    architecture = capability_to_architecture(capability)
    if not architecture:
        return False
    normalized = {str(item).strip().lower() for item in supported if str(item).strip()}
    compute = architecture.replace("sm_", "compute_", 1)
    return architecture.lower() in normalized or compute.lower() in normalized


def torch_gpu_probe_script() -> str:
    # Keep this probe kernel-free. We query the wheel's compiled architecture
    # contract and device properties without allocating tensors on the GPU.
    return (
        "import json,platform,torch;"
        "archs=list(torch.cuda.get_arch_list()) if hasattr(torch.cuda,'get_arch_list') else [];"
        "devices=[];"
        "cuda_ok=bool(torch.cuda.is_available());"
        "count=int(torch.cuda.device_count()) if cuda_ok else 0;"
        "[(lambda i,p: devices.append({'index':i,'name':p.name,'capability':[int(p.major),int(p.minor)]}))"
        "(i,torch.cuda.get_device_properties(i)) for i in range(count)];"
        "print(json.dumps({'python_version':platform.python_version(),'torch_version':torch.__version__,"
        "'torch_cuda_version':torch.version.cuda or '','cuda_available':cuda_ok,'arch_list':archs,'devices':devices}))"
    )


def parse_torch_gpu_probe(payload: Mapping[str, Any]) -> TorchRuntimeGpuProbe:
    supported = tuple(str(item) for item in payload.get("arch_list", ()) if str(item).strip())
    devices: list[TorchGpuDevice] = []
    raw_devices = payload.get("devices", ())
    if isinstance(raw_devices, list):
        for item in raw_devices:
            if not isinstance(item, Mapping):
                continue
            capability_raw = item.get("capability", ())
            if isinstance(capability_raw, (list, tuple)) and len(capability_raw) >= 2:
                capability = f"{int(capability_raw[0])}.{int(capability_raw[1])}"
            else:
                capability = str(capability_raw or "")
            architecture = capability_to_architecture(capability)
            devices.append(TorchGpuDevice(
                index=int(item.get("index", len(devices))),
                name=str(item.get("name", "NVIDIA GPU")),
                capability=capability,
                architecture=architecture,
                compatible=architecture_supported(capability, supported),
            ))
    return TorchRuntimeGpuProbe(
        available=True,
        python_version=str(payload.get("python_version", "")),
        torch_version=str(payload.get("torch_version", "")),
        torch_cuda_version=str(payload.get("torch_cuda_version", "")),
        cuda_available=bool(payload.get("cuda_available", False)),
        supported_architectures=supported,
        devices=tuple(devices),
    )


def probe_torch_runtime_gpu(
    python_executable: str | Path,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    timeout: int = 60,
) -> TorchRuntimeGpuProbe:
    python = Path(python_executable)
    if not python.is_file():
        return TorchRuntimeGpuProbe(False, raw_error=f"Python runtime non trovato: {python}")
    try:
        completed = runner(
            [str(python), "-c", torch_gpu_probe_script()],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except Exception as exc:
        return TorchRuntimeGpuProbe(False, raw_error=str(exc))
    if completed.returncode != 0:
        return TorchRuntimeGpuProbe(False, raw_error=(completed.stderr or completed.stdout or f"exit {completed.returncode}").strip())
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    if not lines:
        return TorchRuntimeGpuProbe(False, raw_error=(completed.stderr or "Probe PyTorch senza output").strip())
    try:
        payload = json.loads(lines[-1])
    except Exception as exc:
        detail = (completed.stderr or "").strip()
        return TorchRuntimeGpuProbe(False, raw_error=f"Output probe PyTorch non valido: {exc}. {detail}".strip())
    if not isinstance(payload, Mapping):
        return TorchRuntimeGpuProbe(False, raw_error="Output probe PyTorch non è un oggetto JSON")
    return parse_torch_gpu_probe(payload)
