"""
Download Qwen2.5-Coder-7B model using Modelscope SDK
"""

import sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')

from modelscope import snapshot_download

MODEL_NAME = "Qwen/Qwen2.5-Coder-7B"
SAVE_PATH = str(Path.home() / ".cache/huggingface/models/Qwen2.5-Coder-7B")

def download():
    print("=" * 60)
    print("Downloading Qwen2.5-Coder-7B from Modelscope")
    print("=" * 60)
    
    try:
        print(f"Model: {MODEL_NAME}")
        print(f"Target: {SAVE_PATH}")
        print()
        
        # Download via Modelscope
        local_path = snapshot_download(
            model_id=MODEL_NAME,
            cache_dir=str(Path.home() / ".cache/huggingface/models"),
            revision='master'
        )
        
        print()
        print("=" * 60)
        print("Download complete!")
        print(f"Model saved to: {local_path}")
        print("=" * 60)
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = download()
    sys.exit(0 if success else 1)
