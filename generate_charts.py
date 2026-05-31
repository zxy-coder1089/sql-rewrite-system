"""
Generate experiment charts (matplotlib)
Usage: python generate_charts.py
"""
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np

# Attempt to set CJK font for Chinese label support
for f in fm.fontManager.ttflist:
    if 'SimHei' in f.name:
        fm.fontManager.addfont(f.fname)
        plt.rcParams['font.family'] = f.name
        break
    elif 'YaHei' in f.name and 'Microsoft' in f.name:
        fm.fontManager.addfont(f.fname)
        plt.rcParams['font.family'] = f.name
        break
plt.rcParams['axes.unicode_minus'] = False

OUTPUT_DIR = Path(__file__).resolve().parents[1]


def chart_ablation():
    """Fig 1: Ablation study bar chart"""
    modes = ['Rules Only', 'LLM Only', 'Rules+Cases', 'Rules+LLM', 'Full System']
    standard = [8.12, 1.05, 8.12, 8.15, 8.20]
    boundary = [1.11, 1.05, 1.11, 1.25, 1.40]

    x = np.arange(len(modes))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 5))
    bars1 = ax.bar(x - width/2, standard, width, label='Standard', color='#4C72B0')
    bars2 = ax.bar(x + width/2, boundary, width, label='Boundary', color='#DD8452')

    ax.set_ylabel('Avg Speedup')
    ax.set_title('Ablation: Performance Contribution by Component')
    ax.set_xticks(x)
    ax.set_xticklabels(modes, fontsize=9)
    ax.legend()
    ax.axhline(y=1.0, color='gray', linestyle='--', linewidth=0.8, label='Baseline (1.0x)')

    for bar in bars1:
        h = bar.get_height()
        if h > 0:
            ax.annotate(f'{h:.2f}x', xy=(bar.get_x() + bar.get_width()/2, h),
                       xytext=(0, 3), textcoords="offset points", ha='center', fontsize=8)
    for bar in bars2:
        h = bar.get_height()
        if h > 0:
            ax.annotate(f'{h:.2f}x', xy=(bar.get_x() + bar.get_width()/2, h),
                       xytext=(0, 3), textcoords="offset points", ha='center', fontsize=8)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'chart_ablation.png', dpi=200)
    plt.close()
    print("  [OK] chart_ablation.png")


def chart_finetune_comparison():
    """Fig 2: Boundary case comparison: Rules Only vs Full System"""
    cases = ['B1','B2','B3','B4','B5','B6','B7','B8','B9','B10','B11','B12','B13','B14','B15','B16','B17','B18','B19','B20']
    rules =  [1.02,0.95,1.06,1.03,1.21,1.24,1.08,1.11,1.02,1.01,1.02,1.03,1.04,1.03,0.95,1.01,0.91,0.99,1.83,1.06]
    full =   [1.23,1.04,1.05,1.05,1.23,1.43,1.38,1.30,1.04,1.00,1.03,1.10,1.02,1.04,1.33,1.91,1.17,1.04,1.05,1.06]

    fig, ax = plt.subplots(figsize=(14, 5))
    x = range(len(cases))
    ax.plot(x, rules, 'o-', label='Rules Only', color='#4C72B0', linewidth=1.5, markersize=5)
    ax.plot(x, full, 's-', label='Full System (Rules+Cases+LLM)', color='#DD8452', linewidth=1.5, markersize=5)
    ax.axhline(y=1.0, color='gray', linestyle='--', linewidth=0.8, label='Baseline (1.0x)')
    ax.set_xticks(x)
    ax.set_xticklabels(cases, fontsize=9)
    ax.set_ylabel('Speedup')
    ax.set_title('Boundary Case Comparison: Rules Only vs Full System')
    ax.legend(fontsize=10)
    ax.set_yscale('symlog', linthresh=2)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'chart_finetune_comparison.png', dpi=200)
    plt.close()
    print("  [OK] chart_finetune_comparison.png")


def chart_complexity():
    """Fig 3: Standard vs Boundary comparison"""
    levels = ['Standard (30 cases)', 'Boundary (20 cases)']
    rules = [8.12, 1.11]
    full = [8.20, 1.40]

    x = np.arange(len(levels))
    width = 0.35

    fig, ax = plt.subplots(figsize=(8, 5))
    bars1 = ax.bar(x - width/2, rules, width, label='Rules Only', color='#4C72B0')
    bars2 = ax.bar(x + width/2, full, width, label='Full System (Rules+Cases+LLM)', color='#DD8452')

    ax.set_ylabel('Avg Speedup')
    ax.set_title('Ablation: Rules Only vs Full System')
    ax.set_xticks(x)
    ax.set_xticklabels(levels)
    ax.legend()
    ax.axhline(y=1.0, color='gray', linestyle='--', linewidth=0.8, label='Baseline (1.0x)')

    for bar in bars1:
        h = bar.get_height()
        if h > 0:
            ax.annotate(f'{h:.2f}x', xy=(bar.get_x() + bar.get_width()/2, h),
                       xytext=(0, 3), textcoords="offset points", ha='center', fontsize=10)
    for bar in bars2:
        h = bar.get_height()
        if h > 0:
            ax.annotate(f'{h:.2f}x', xy=(bar.get_x() + bar.get_width()/2, h),
                       xytext=(0, 3), textcoords="offset points", ha='center', fontsize=10)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'chart_complexity.png', dpi=200)
    plt.close()
    print("  [OK] chart_complexity.png")


if __name__ == "__main__":
    print("Generating experiment charts...")
    chart_ablation()
    chart_finetune_comparison()
    chart_complexity()
    print("Done! Reference chart_ablation.png, chart_finetune_comparison.png, chart_complexity.png in your paper")
