#!/bin/bash
# AutoDL QLoRA training script - optimized

echo "============================================================"
echo "AutoDL QLoRA Fine-tuning - Optimized"
echo "============================================================"

# Environment setup
source ~/miniconda3/etc/profile.d/conda.sh
conda activate base

cd /root/autodl-tmp/sql_rewrite_system

# Set domestic mirror for HF
export HF_ENDPOINT=https://hf-mirror.com

# Model path
MODEL_PATH="/root/autodl-tmp/models/Qwen2.5-Coder-7B"

echo "[1/6] Checking/downloading model..."
if [ -d "$MODEL_PATH" ] && [ -f "$MODEL_PATH/config.json" ]; then
    echo "Model already exists: $MODEL_PATH"
else
    echo "Downloading model (using domestic mirror)..."
    huggingface-cli download Qwen/Qwen2.5-Coder-7B --local-dir $MODEL_PATH --local-dir-use-symlinks False
fi

# Verify model files
if [ ! -f "$MODEL_PATH/config.json" ]; then
    echo "Error: Model files incomplete"
    ls -la $MODEL_PATH
    exit 1
fi

# Install dependencies
echo "[2/6] Installing dependencies..."
pip install torch transformers peft bitsandbytes accelerate -q 2>/dev/null

# Training
echo "[3/6] Starting training..."
echo "Config:"
echo "  - LoRA rank: 16"
echo "  - Epochs: 2"
echo "  - Learning rate: 1e-4"
echo "  - Max length: 256"

python finetune/train_pg.py \
    --model "$MODEL_PATH" \
    --epochs 2 \
    --lora-rank 16 \
    --learning-rate 1e-4 \
    --max-length 256

# Check output
echo "[4/6] Checking training output..."
if [ -d "finetune/output/lora_adapter" ]; then
    echo "LoRA adapter saved!"
    ls -la finetune/output/lora_adapter/
else
    echo "Warning: LoRA adapter not found!"
fi

echo "[5/6] Done!"
