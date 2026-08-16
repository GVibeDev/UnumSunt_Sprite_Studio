# Migration R5c3c → R5c3d

No runtime or model reinstall is required.

R5c3d adds capability diagnostics only. Existing Miniconda, `wangp_env`, WanGP and downloaded checkpoints are reused.

After launching R5c3d:

1. open **File → Gestione runtime AI…**;
2. run **Health Check**;
3. confirm `torch.gpu_compatibility`;
4. in **Genera → Runtime WAN**, run Health Check and Dry-run;
5. run a real generation only when the GPU ↔ PyTorch check is compatible.
