# A12 grey-ground series with a noise floor

**Descriptive, with a registered read-out (amendment A12).** Three draws per ground step on three engines; A3's single-draw figures stand as reported. On Wan 2.2 and LTX-2.3, A3's cell ran on other hardware and is shown as the separate point `a3`, outside the noise floor and rho.

## Gen-4 Turbo (15 of 15 files)

- mean chamfer vs frame 0 (px) (the read-out), 15 points: rho vs k -0.48, permutation p (descriptive) 0.0754, noise floor 8.922, dose effect 10.021: **not readable at three draws**
- edge |slope|, 15 points: rho vs k -0.32, permutation p (descriptive) 0.2545, noise floor 0.040, dose effect 0.067: **not readable at three draws**
- style drift, terminal, 15 points: rho vs k -0.26, permutation p (descriptive) 0.3548, noise floor 0.016, dose effect 0.024: **not readable at three draws**

| k | draws | median chamfer | range across draws |
|---|---|---|---|
| 1.00 | 3 | 4.677 | 4.403 |
| 0.90 | 3 | 5.223 | 9.803 |
| 0.80 | 3 | 11.301 | 12.115 |
| 0.65 | 3 | 7.757 | 5.487 |
| 0.52 | 3 | 14.699 | 8.922 |

| k | draw | model_version (runs/manifest.jsonl) |
|---|---|---|
| 1.00 | 1 | gen4_turbo (Runway dev API, X-Runway-Version 2024-11-06) |
| 1.00 | 2 | gen4_turbo (Runway dev API, X-Runway-Version 2024-11-06) |
| 1.00 | 3 | gen4_turbo (Runway dev API, X-Runway-Version 2024-11-06) |
| 0.90 | 1 | gen4_turbo (Runway dev API, X-Runway-Version 2024-11-06) |
| 0.90 | 2 | gen4_turbo (Runway dev API, X-Runway-Version 2024-11-06) |
| 0.90 | 3 | gen4_turbo (Runway dev API, X-Runway-Version 2024-11-06) |
| 0.80 | 1 | gen4_turbo (Runway dev API, X-Runway-Version 2024-11-06) |
| 0.80 | 2 | gen4_turbo (Runway dev API, X-Runway-Version 2024-11-06) |
| 0.80 | 3 | gen4_turbo (Runway dev API, X-Runway-Version 2024-11-06) |
| 0.65 | 1 | gen4_turbo (Runway dev API, X-Runway-Version 2024-11-06) |
| 0.65 | 2 | gen4_turbo (Runway dev API, X-Runway-Version 2024-11-06) |
| 0.65 | 3 | gen4_turbo (Runway dev API, X-Runway-Version 2024-11-06) |
| 0.52 | 1 | gen4_turbo (Runway dev API, X-Runway-Version 2024-11-06) |
| 0.52 | 2 | gen4_turbo (Runway dev API, X-Runway-Version 2024-11-06) |
| 0.52 | 3 | gen4_turbo (Runway dev API, X-Runway-Version 2024-11-06) |

## Wan 2.2 (15 of 15 files)

- mean chamfer vs frame 0 (px) (the read-out), 15 points: rho vs k 0.52, permutation p (descriptive) 0.0466, noise floor 1.627, dose effect -1.763: **not readable at three draws**
- edge |slope|, 15 points: rho vs k -0.71, permutation p (descriptive) 0.0045, noise floor 0.043, dose effect 0.035: **not readable at three draws**
- style drift, terminal, 15 points: rho vs k 0.67, permutation p (descriptive) 0.0076, noise floor 0.023, dose effect -0.034: **not readable at three draws**

| k | draws | median chamfer | range across draws | a3 chamfer (other hardware) |
|---|---|---|---|---|
| 1.00 | 3 | 1.858 | 2.593 | 1.878 |
| 0.90 | 3 | 1.257 | 1.822 | 1.330 |
| 0.80 | 3 | 1.418 | 1.627 | 1.413 |
| 0.65 | 3 | 0.302 | 1.242 | 0.079 |
| 0.52 | 3 | 0.095 | 1.283 | 0.087 |

Machine: RTX5090-32GB CUDA driver 595.91.07 (RunPod secure, A10/A12) (every draw with a manifest line).

| k | draw | model_version (runs/manifest.jsonl) |
|---|---|---|
| 1.00 | 1 | Wan2.2-TI2V-5B GGUF Q5_K_M (QuantStack) + umt5-xxl GGUF Q5_K_M (city96) + Wan2.2_VAE, ComfyUI 0.31.0 [RTX5090-32GB CUDA driver 595.91.07 (RunPod secure, A10/A12)] |
| 1.00 | 2 | Wan2.2-TI2V-5B GGUF Q5_K_M (QuantStack) + umt5-xxl GGUF Q5_K_M (city96) + Wan2.2_VAE, ComfyUI 0.31.0 [RTX5090-32GB CUDA driver 595.91.07 (RunPod secure, A10/A12)] |
| 1.00 | 3 | Wan2.2-TI2V-5B GGUF Q5_K_M (QuantStack) + umt5-xxl GGUF Q5_K_M (city96) + Wan2.2_VAE, ComfyUI 0.31.0 [RTX5090-32GB CUDA driver 595.91.07 (RunPod secure, A10/A12)] |
| 0.90 | 1 | Wan2.2-TI2V-5B GGUF Q5_K_M (QuantStack) + umt5-xxl GGUF Q5_K_M (city96) + Wan2.2_VAE, ComfyUI 0.31.0 [RTX5090-32GB CUDA driver 595.91.07 (RunPod secure, A10/A12)] |
| 0.90 | 2 | Wan2.2-TI2V-5B GGUF Q5_K_M (QuantStack) + umt5-xxl GGUF Q5_K_M (city96) + Wan2.2_VAE, ComfyUI 0.31.0 [RTX5090-32GB CUDA driver 595.91.07 (RunPod secure, A10/A12)] |
| 0.90 | 3 | Wan2.2-TI2V-5B GGUF Q5_K_M (QuantStack) + umt5-xxl GGUF Q5_K_M (city96) + Wan2.2_VAE, ComfyUI 0.31.0 [RTX5090-32GB CUDA driver 595.91.07 (RunPod secure, A10/A12)] |
| 0.80 | 1 | Wan2.2-TI2V-5B GGUF Q5_K_M (QuantStack) + umt5-xxl GGUF Q5_K_M (city96) + Wan2.2_VAE, ComfyUI 0.31.0 [RTX5090-32GB CUDA driver 595.91.07 (RunPod secure, A10/A12)] |
| 0.80 | 2 | Wan2.2-TI2V-5B GGUF Q5_K_M (QuantStack) + umt5-xxl GGUF Q5_K_M (city96) + Wan2.2_VAE, ComfyUI 0.31.0 [RTX5090-32GB CUDA driver 595.91.07 (RunPod secure, A10/A12)] |
| 0.80 | 3 | Wan2.2-TI2V-5B GGUF Q5_K_M (QuantStack) + umt5-xxl GGUF Q5_K_M (city96) + Wan2.2_VAE, ComfyUI 0.31.0 [RTX5090-32GB CUDA driver 595.91.07 (RunPod secure, A10/A12)] |
| 0.65 | 1 | Wan2.2-TI2V-5B GGUF Q5_K_M (QuantStack) + umt5-xxl GGUF Q5_K_M (city96) + Wan2.2_VAE, ComfyUI 0.31.0 [RTX5090-32GB CUDA driver 595.91.07 (RunPod secure, A10/A12)] |
| 0.65 | 2 | Wan2.2-TI2V-5B GGUF Q5_K_M (QuantStack) + umt5-xxl GGUF Q5_K_M (city96) + Wan2.2_VAE, ComfyUI 0.31.0 [RTX5090-32GB CUDA driver 595.91.07 (RunPod secure, A10/A12)] |
| 0.65 | 3 | Wan2.2-TI2V-5B GGUF Q5_K_M (QuantStack) + umt5-xxl GGUF Q5_K_M (city96) + Wan2.2_VAE, ComfyUI 0.31.0 [RTX5090-32GB CUDA driver 595.91.07 (RunPod secure, A10/A12)] |
| 0.52 | 1 | Wan2.2-TI2V-5B GGUF Q5_K_M (QuantStack) + umt5-xxl GGUF Q5_K_M (city96) + Wan2.2_VAE, ComfyUI 0.31.0 [RTX5090-32GB CUDA driver 595.91.07 (RunPod secure, A10/A12)] |
| 0.52 | 2 | Wan2.2-TI2V-5B GGUF Q5_K_M (QuantStack) + umt5-xxl GGUF Q5_K_M (city96) + Wan2.2_VAE, ComfyUI 0.31.0 [RTX5090-32GB CUDA driver 595.91.07 (RunPod secure, A10/A12)] |
| 0.52 | 3 | Wan2.2-TI2V-5B GGUF Q5_K_M (QuantStack) + umt5-xxl GGUF Q5_K_M (city96) + Wan2.2_VAE, ComfyUI 0.31.0 [RTX5090-32GB CUDA driver 595.91.07 (RunPod secure, A10/A12)] |

a3 point's model_version: n/a.

## LTX-2.3 (15 of 15 files)

- mean chamfer vs frame 0 (px) (the read-out), 15 points: rho vs k -0.45, permutation p (descriptive) 0.1040, noise floor 7.138, dose effect 17.080: **monotone claim allowed (darker ground, more drift)**
- edge |slope|, 15 points: rho vs k 0.20, permutation p (descriptive) 0.4919, noise floor 0.270, dose effect -0.009: **not readable at three draws**
- style drift, terminal, 15 points: rho vs k 0.23, permutation p (descriptive) 0.4185, noise floor 0.138, dose effect -0.055: **not readable at three draws**

| k | draws | median chamfer | range across draws | a3 chamfer (other hardware) |
|---|---|---|---|---|
| 1.00 | 3 | 9.006 | 5.051 | 10.041 |
| 0.90 | 3 | 4.627 | 5.023 | 1.510 |
| 0.80 | 3 | 6.455 | 7.138 | 13.381 |
| 0.65 | 3 | 18.448 | 42.685 | 19.774 |
| 0.52 | 3 | 26.085 | 44.391 | 27.065 |

Machine: RTX5090-32GB CUDA driver 595.91.07 (RunPod secure, A10/A12) (every draw with a manifest line).

| k | draw | model_version (runs/manifest.jsonl) |
|---|---|---|
| 1.00 | 1 | LTX-2.3-22B distilled-1.1 GGUF Q4_K_M (unsloth) + gemma-3-12B-it fp8_scaled (Comfy-Org) + LTX23 bf16 VAEs (Kijai), ComfyUI 0.31.0 [RTX5090-32GB CUDA driver 595.91.07 (RunPod secure, A10/A12)] |
| 1.00 | 2 | LTX-2.3-22B distilled-1.1 GGUF Q4_K_M (unsloth) + gemma-3-12B-it fp8_scaled (Comfy-Org) + LTX23 bf16 VAEs (Kijai), ComfyUI 0.31.0 [RTX5090-32GB CUDA driver 595.91.07 (RunPod secure, A10/A12)] |
| 1.00 | 3 | LTX-2.3-22B distilled-1.1 GGUF Q4_K_M (unsloth) + gemma-3-12B-it fp8_scaled (Comfy-Org) + LTX23 bf16 VAEs (Kijai), ComfyUI 0.31.0 [RTX5090-32GB CUDA driver 595.91.07 (RunPod secure, A10/A12)] |
| 0.90 | 1 | LTX-2.3-22B distilled-1.1 GGUF Q4_K_M (unsloth) + gemma-3-12B-it fp8_scaled (Comfy-Org) + LTX23 bf16 VAEs (Kijai), ComfyUI 0.31.0 [RTX5090-32GB CUDA driver 595.91.07 (RunPod secure, A10/A12)] |
| 0.90 | 2 | LTX-2.3-22B distilled-1.1 GGUF Q4_K_M (unsloth) + gemma-3-12B-it fp8_scaled (Comfy-Org) + LTX23 bf16 VAEs (Kijai), ComfyUI 0.31.0 [RTX5090-32GB CUDA driver 595.91.07 (RunPod secure, A10/A12)] |
| 0.90 | 3 | LTX-2.3-22B distilled-1.1 GGUF Q4_K_M (unsloth) + gemma-3-12B-it fp8_scaled (Comfy-Org) + LTX23 bf16 VAEs (Kijai), ComfyUI 0.31.0 [RTX5090-32GB CUDA driver 595.91.07 (RunPod secure, A10/A12)] |
| 0.80 | 1 | LTX-2.3-22B distilled-1.1 GGUF Q4_K_M (unsloth) + gemma-3-12B-it fp8_scaled (Comfy-Org) + LTX23 bf16 VAEs (Kijai), ComfyUI 0.31.0 [RTX5090-32GB CUDA driver 595.91.07 (RunPod secure, A10/A12)] |
| 0.80 | 2 | LTX-2.3-22B distilled-1.1 GGUF Q4_K_M (unsloth) + gemma-3-12B-it fp8_scaled (Comfy-Org) + LTX23 bf16 VAEs (Kijai), ComfyUI 0.31.0 [RTX5090-32GB CUDA driver 595.91.07 (RunPod secure, A10/A12)] |
| 0.80 | 3 | LTX-2.3-22B distilled-1.1 GGUF Q4_K_M (unsloth) + gemma-3-12B-it fp8_scaled (Comfy-Org) + LTX23 bf16 VAEs (Kijai), ComfyUI 0.31.0 [RTX5090-32GB CUDA driver 595.91.07 (RunPod secure, A10/A12)] |
| 0.65 | 1 | LTX-2.3-22B distilled-1.1 GGUF Q4_K_M (unsloth) + gemma-3-12B-it fp8_scaled (Comfy-Org) + LTX23 bf16 VAEs (Kijai), ComfyUI 0.31.0 [RTX5090-32GB CUDA driver 595.91.07 (RunPod secure, A10/A12)] |
| 0.65 | 2 | LTX-2.3-22B distilled-1.1 GGUF Q4_K_M (unsloth) + gemma-3-12B-it fp8_scaled (Comfy-Org) + LTX23 bf16 VAEs (Kijai), ComfyUI 0.31.0 [RTX5090-32GB CUDA driver 595.91.07 (RunPod secure, A10/A12)] |
| 0.65 | 3 | LTX-2.3-22B distilled-1.1 GGUF Q4_K_M (unsloth) + gemma-3-12B-it fp8_scaled (Comfy-Org) + LTX23 bf16 VAEs (Kijai), ComfyUI 0.31.0 [RTX5090-32GB CUDA driver 595.91.07 (RunPod secure, A10/A12)] |
| 0.52 | 1 | LTX-2.3-22B distilled-1.1 GGUF Q4_K_M (unsloth) + gemma-3-12B-it fp8_scaled (Comfy-Org) + LTX23 bf16 VAEs (Kijai), ComfyUI 0.31.0 [RTX5090-32GB CUDA driver 595.91.07 (RunPod secure, A10/A12)] |
| 0.52 | 2 | LTX-2.3-22B distilled-1.1 GGUF Q4_K_M (unsloth) + gemma-3-12B-it fp8_scaled (Comfy-Org) + LTX23 bf16 VAEs (Kijai), ComfyUI 0.31.0 [RTX5090-32GB CUDA driver 595.91.07 (RunPod secure, A10/A12)] |
| 0.52 | 3 | LTX-2.3-22B distilled-1.1 GGUF Q4_K_M (unsloth) + gemma-3-12B-it fp8_scaled (Comfy-Org) + LTX23 bf16 VAEs (Kijai), ComfyUI 0.31.0 [RTX5090-32GB CUDA driver 595.91.07 (RunPod secure, A10/A12)] |

a3 point's model_version: LTX-2.3-22B distilled-1.1 GGUF Q4_K_M (unsloth) + gemma-3-12B-it fp8_scaled (Comfy-Org) + LTX23 bf16 VAEs (Kijai), ComfyUI 0.31.0.

