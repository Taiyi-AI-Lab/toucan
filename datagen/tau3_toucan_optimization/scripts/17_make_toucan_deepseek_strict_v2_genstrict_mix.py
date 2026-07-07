#!/usr/bin/env python3
"""Build strict-v2 Toucan mix using strict-filtered generated data."""

import os
import runpy
from pathlib import Path


if __name__ == "__main__":
    # Reuse the v2 mix builder but point it at the strict generated export.
    os.environ["GENERATED_SFT"] = str(
        Path("/data/scripts/Toucan/datagen/tau3_toucan_optimization/data/generated_tau3_style_clean_sft_strict.jsonl")
    )
    os.environ["TOUCAN_MIX_OUT_DIR"] = str(
        Path("/data/scripts/Toucan/datagen/tau3_toucan_optimization/data/toucan_optimized_mix_deepseek_strict_v2_genstrict")
    )
    runpy.run_path(
        "/data/scripts/Toucan/datagen/tau3_toucan_optimization/scripts/15_make_toucan_deepseek_strict_v2_mix.py",
        run_name="__main__",
    )
