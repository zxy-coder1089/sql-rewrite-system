"""
QLoRA fine-tuning script - optimized
For qwen2.5-coder:7b model

Optimized parameters:
- LoRA rank: r=16 (was 8)
- Training epochs: 2 (was 3)
- Quantization: 4bit NF4
- Learning rate: 1e-4 (was 2e-4)
- Max length: 256 (was 512)
"""

import os
import sys
import argparse
from pathlib import Path

import torch
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
    DataCollatorForLanguageModeling,
    Trainer,
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"

MODEL_NAME = "/root/autodl-tmp/models/Qwen2.5-Coder-7B"

def parse_args():
    parser = argparse.ArgumentParser(description="SQL optimization model QLoRA fine-tuning - optimized")
    parser.add_argument("--model", type=str, default=MODEL_NAME, 
                       help="Model path or name")
    parser.add_argument("--epochs", type=int, default=2, help="Training epochs (default 2)")
    parser.add_argument("--batch-size", type=int, default=1, help="Batch size")
    parser.add_argument("--lora-rank", type=int, default=16, help="LoRA rank (default 16)")
    parser.add_argument("--learning-rate", type=float, default=1e-4, help="Learning rate (default 1e-4)")
    parser.add_argument("--max-length", type=int, default=256, help="Max sequence length (default 256)")
    return parser.parse_args()

args = parse_args()
MODEL_NAME = args.model

def load_model_and_tokenizer():
    """Load quantized model and tokenizer"""
    print("=" * 60)
    print("Loading model and tokenizer...")
    print("=" * 60)
    
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
    )
    
    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_NAME,
        padding_side="right",
        use_fast=False,
    )
    
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    
    print(f"Loading model: {MODEL_NAME}")
    
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
        max_memory=None,
    )
    
    model = prepare_model_for_kbit_training(model)
    
    print(f"Model loaded!")
    print(f"Model parameters: {model.num_parameters() / 1e9:.2f}B")
    
    return model, tokenizer

def setup_lora(model):
    """Configure LoRA"""
    print("\n" + "=" * 60)
    print("Configuring LoRA...")
    print(f"LoRA rank: {args.lora_rank}")
    print(f"Learning rate: {args.learning_rate}")
    print(f"Training epochs: {args.epochs}")
    print(f"Max length: {args.max_length}")
    print("=" * 60)
    
    lora_config = LoraConfig(
        r=args.lora_rank,
        lora_alpha=args.lora_rank * 2,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=[
            "q_proj", "v_proj",
            "k_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ],
    )
    
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()
    
    return model

def prepare_dataset(tokenizer):
    """Prepare dataset"""
    print("\n" + "=" * 60)
    print("Preparing dataset...")
    print("=" * 60)
    
    def format_data(example):
        """Format conversation data"""
        messages = example["messages"]
        text = ""
        for msg in messages:
            if msg["role"] == "system":
                text += f"<|im_start|>system\n{msg['content']}<|im_end|>\n"
            elif msg["role"] == "user":
                text += f"<|im_start|>user\n{msg['content']}<|im_end|>\n"
            elif msg["role"] == "assistant":
                text += f"<|im_start|>assistant\n{msg['content']}<|im_end|>\n"
        
        text += "<|im_end|>"
        
        return {"text": text}
    
    train_file = BASE_DIR.parent / "data" / "clean_train.jsonl"
    valid_file = BASE_DIR.parent / "data" / "clean_valid.jsonl"
    
    if not train_file.exists():
        print(f"Error: Training data file not found: {train_file}")
        print("Please run generate_clean_data.py first to generate data")
        sys.exit(1)
    
    print(f"Loading training data: {train_file}")
    
    import json
    train_data = []
    with open(train_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                train_data.append(json.loads(line))
    
    valid_data = []
    if valid_file.exists():
        print(f"Loading validation data: {valid_file}")
        with open(valid_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    valid_data.append(json.loads(line))
    
    print("Formatting data...")
    train_formatted = [format_data(item) for item in train_data]
    
    if valid_data:
        valid_formatted = [format_data(item) for item in valid_data]
    else:
        valid_formatted = None
    
    def tokenize(example):
        result = tokenizer(
            example["text"],
            truncation=True,
            max_length=args.max_length,
            padding="max_length",
        )
        result["labels"] = result["input_ids"].copy()
        return result
    
    print("Tokenizing...")
    train_dataset = [tokenize(item) for item in train_formatted]
    
    if valid_formatted:
        valid_dataset = [tokenize(item) for item in valid_formatted]
    else:
        valid_dataset = None
    
    print(f"Training set size: {len(train_dataset)}")
    if valid_dataset:
        print(f"Validation set size: {len(valid_dataset)}")
    
    return train_dataset, valid_dataset

def setup_trainer(model, tokenizer, train_dataset, valid_dataset):
    """Setup trainer"""
    print("\n" + "=" * 60)
    print("Configuring trainer...")
    print("=" * 60)
    
    training_args = TrainingArguments(
        output_dir=str(OUTPUT_DIR),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=1,
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=16,
        gradient_checkpointing=True,
        optim="adamw_torch",
        learning_rate=args.learning_rate,
        weight_decay=0.01,
        fp16=True,
        logging_steps=10,
        save_strategy="epoch",
        save_total_limit=2,
        load_best_model_at_end=True if valid_dataset else False,
        warmup_ratio=0.03,
        lr_scheduler_type="cosine",
        report_to="none",
        eval_strategy="epoch" if valid_dataset else "no",
        eval_accumulation_steps=4,
        max_grad_norm=0.3,
    )
    
    data_collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer,
        mlm=False,
    )
    
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=valid_dataset,
        data_collator=data_collator,
    )
    
    return trainer

def main():
    print("=" * 60)
    print("QLoRA Fine-tuning - Optimized")
    print(f"Model: {MODEL_NAME}")
    print(f"LoRA rank: {args.lora_rank}")
    print(f"Training epochs: {args.epochs}")
    print(f"Learning rate: {args.learning_rate}")
    print(f"Max length: {args.max_length}")
    print("=" * 60)
    
    model, tokenizer = load_model_and_tokenizer()
    model = setup_lora(model)
    train_dataset, valid_dataset = prepare_dataset(tokenizer)
    trainer = setup_trainer(model, tokenizer, train_dataset, valid_dataset)
    
    print("\n" + "=" * 60)
    print("Starting training...")
    print("=" * 60)
    
    trainer.train()
    
    print("\n" + "=" * 60)
    print("Training complete!")
    print("=" * 60)
    
    output_path = OUTPUT_DIR / "lora_adapter"
    print(f"Saving LoRA adapter to: {output_path}")
    model.save_pretrained(output_path)
    
    print("\nNext steps:")
    print("1. Merge LoRA weights: python merge_model.py")
    print("2. Convert to GGUF: python convert_to_gguf.py")
    print("3. Quantize: llama-quantize")

if __name__ == "__main__":
    main()
