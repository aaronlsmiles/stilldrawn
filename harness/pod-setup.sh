#!/bin/bash
# StillDrawn A2 pod environment (RunPod CUDA) — idempotent-ish, run once on a fresh
# pytorch pod. Installs ComfyUI + ComfyUI-GGUF, pulls the pinned model files,
# starts the server. Payload (dataset/panels, harness/) is rsynced separately
# into /workspace/stilldrawn by the orchestrator.
set -euo pipefail
cd /workspace

pip install -q -U "huggingface_hub[cli]" hf_transfer
export HF_HUB_ENABLE_HF_TRANSFER=1

if [ ! -d ComfyUI ]; then
  git clone -q https://github.com/comfyanonymous/ComfyUI
fi
cd ComfyUI
pip install -q -r requirements.txt
if [ ! -d custom_nodes/ComfyUI-GGUF ]; then
  git -C custom_nodes clone -q https://github.com/city96/ComfyUI-GGUF
fi
pip install -q gguf sentencepiece

M=/workspace/ComfyUI/models
hf download QuantStack/Wan2.2-TI2V-5B-GGUF Wan2.2-TI2V-5B-Q5_K_M.gguf --local-dir $M/diffusion_models/
hf download QuantStack/Wan2.2-TI2V-5B-GGUF VAE/Wan2.2_VAE.safetensors --local-dir /tmp/wanvae
mv -f /tmp/wanvae/VAE/Wan2.2_VAE.safetensors $M/vae/
hf download city96/umt5-xxl-encoder-gguf umt5-xxl-encoder-Q5_K_M.gguf --local-dir $M/text_encoders/
hf download unsloth/LTX-2.3-GGUF distilled-1.1/ltx-2.3-22b-distilled-1.1-Q4_K_M.gguf --local-dir /tmp/ltx
mv -f /tmp/ltx/distilled-1.1/ltx-2.3-22b-distilled-1.1-Q4_K_M.gguf $M/diffusion_models/
hf download Kijai/LTX2.3_comfy vae/LTX23_video_vae_bf16.safetensors vae/LTX23_audio_vae_bf16.safetensors text_encoders/ltx-2.3_text_projection_bf16.safetensors --local-dir /tmp/kj
mv -f /tmp/kj/vae/LTX23_video_vae_bf16.safetensors /tmp/kj/vae/LTX23_audio_vae_bf16.safetensors $M/vae/
mv -f /tmp/kj/text_encoders/ltx-2.3_text_projection_bf16.safetensors $M/text_encoders/
hf download Comfy-Org/ltx-2 split_files/text_encoders/gemma_3_12B_it_fp8_scaled.safetensors --local-dir /tmp/g
mv -f /tmp/g/split_files/text_encoders/gemma_3_12B_it_fp8_scaled.safetensors $M/text_encoders/
ln -sf $M/text_encoders/ltx-2.3_text_projection_bf16.safetensors $M/checkpoints/
ln -sf $M/vae/LTX23_audio_vae_bf16.safetensors $M/checkpoints/

cd /workspace/ComfyUI
nohup python main.py --listen 127.0.0.1 --port 8188 > /workspace/comfy.log 2>&1 &
sleep 20
curl -s -m 5 http://127.0.0.1:8188/system_stats | head -c 200
echo
echo "POD-SETUP-DONE"
