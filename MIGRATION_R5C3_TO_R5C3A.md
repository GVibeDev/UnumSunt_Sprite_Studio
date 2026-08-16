# Migration R5c3 → R5c3b

R5c3b is a compatibility/runtime-binding hotfix. It does not require reinstalling a healthy managed runtime or redownloading Wan Animate.

On first start, when a valid R5c3 managed runtime state is present, Sprite Studio repairs the bridge configuration to use `wangp_env/python.exe`. Historical runtime paths embedded in application/project snapshots are ignored.
