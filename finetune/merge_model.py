"""
Model merge script - optimized
Merge LoRA adapter into base model

Usage:
1. Run on AutoDL: python merge_model.py
2. Merged model is used for GGUF conversion
"""

import os
import sys
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
MERGED_DIR = OUTPUT_DIR / "merged_model"
MODEL_PATH = "/root/autodl-tmp/models/Qwen2.5-Coder-7B"

def merge_model():
    print("=" * 60)
    print("Model Merge - Optimized")
    print("=" * 60)
    
    lora_path = OUTPUT_DIR / "lora_adapter"
    
    if not lora_path.exists():
        print(f"Error: LoRA adapter not found: {lora_path}")
        print("Please run python train_pg.py first")
        sys.exit(1)
    
    print(f"Base model: {MODEL_PATH}")
    print(f"LoRA adapter: {lora_path}")
    print(f"Output directory: {MERGED_DIR}")
    
    print("\nLoading base model...")
    base_model = AutoModelForCausalLM.from_pretrained(
        MODEL_PATH,
        device_map="cpu",
        torch_dtype=torch.float16,
        trust_remote_code=True,
    )
    
    print("Loading LoRA adapter...")
    model = PeftModel.from_pretrained(base_model, str(lora_path))
    
    print("Merging weights...")
    merged_model = model.merge_and_unload()
    
    print("Saving merged model...")
    MERGED_DIR.mkdir(parents=True, exist_ok=True)
    merged_model.save_pretrained(str(MERGED_DIR))
    
    print("Saving tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
    tokenizer.save_pretrained(str(MERGED_DIR))
    
    print("\n" + "=" * 60)
    print("Merge complete!")
    print(f"Model saved at: {MERGED_DIR}")
    print("=" * 60)
    
    print("\nNext step - convert to GGUF:")
    print("1. Download llama.cpp to /root/autodl-tmp/llama.cpp")
    print("2. Convert: python llama.cpp/convert.py {} --outtype q8_0 --outfile merged-model-f16.gguf".format(MERGED_DIR))
    print("3. Quantize: llama.cpp/build/bin/llama-quantize merged-model-f16.gguf qwen2.5-coder-7b-sql-f16.gguf Q4_K_M")
    print("4. Download to local .ollama/models/ directory")

if __name__ == "__main__":
    merge_model()
