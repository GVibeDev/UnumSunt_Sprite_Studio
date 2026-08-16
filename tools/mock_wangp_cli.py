from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

import cv2
import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Development WanGP-compatible fixture.')
    parser.add_argument('--process', required=True)
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--verbose', default='2')
    parser.add_argument('--dry-run', action='store_true')
    return parser.parse_args()


def extract_generation(payload: dict) -> dict:
    if isinstance(payload.get('__unum_sunt_request__'), dict):
        request = payload['__unum_sunt_request__']
        generation = request.get('generation', {})
        return {
            'width': int(generation.get('width', 128)),
            'height': int(generation.get('height', 128)),
            'frames': int(generation.get('frames', 12)),
            'fps': float(generation.get('fps', 12.0)),
            'seed': int(generation.get('seed', 1)),
        }
    generation = payload.get('generation', {})
    return {
        'width': int(generation.get('width', payload.get('width', 128))),
        'height': int(generation.get('height', payload.get('height', 128))),
        'frames': int(generation.get('frames', payload.get('frames', 12))),
        'fps': float(generation.get('fps', payload.get('fps', 12.0))),
        'seed': int(generation.get('seed', payload.get('seed', 1))),
    }


def main() -> int:
    args = parse_args()
    settings_path = Path(args.process)
    output_dir = Path(args.output_dir)
    payload = json.loads(settings_path.read_text(encoding='utf-8'))
    print('Loading model — development fixture', flush=True)
    time.sleep(0.03)
    print('Preprocessing inputs', flush=True)
    time.sleep(0.03)
    if args.dry_run:
        print('[1/1] Dry-run validation completed', flush=True)
        return 0

    generation = extract_generation(payload)
    width = max(32, generation['width'])
    height = max(32, generation['height'])
    frames = max(2, generation['frames'])
    fps = max(1.0, generation['fps'])
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / 'wangp_generated.mp4'
    writer = cv2.VideoWriter(
        str(output_path),
        cv2.VideoWriter_fourcc(*'mp4v'),
        fps,
        (width, height),
    )
    if not writer.isOpened():
        print('Unable to create output video', file=sys.stderr, flush=True)
        return 3
    rng = np.random.default_rng(generation['seed'])
    try:
        for index in range(frames):
            frame = np.zeros((height, width, 3), dtype=np.uint8)
            frame[:] = (35, 210, 75)
            x = int(width * 0.2 + (width * 0.6) * index / max(1, frames - 1))
            y = int(height * 0.5 + np.sin(index / max(1, frames - 1) * np.pi * 2) * height * 0.08)
            cv2.circle(frame, (x, y), max(4, min(width, height) // 12), (90, 50, 170), -1, cv2.LINE_AA)
            noise = rng.normal(0, 0.4, frame.shape).astype(np.int16)
            frame = np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)
            writer.write(frame)
            print(f'[{index + 1}/{frames}] Prompt 1/1 - Denoising', flush=True)
            time.sleep(0.005)
    finally:
        writer.release()
    print('VAE decoding', flush=True)
    time.sleep(0.03)
    print('Saving output', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
