import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import paddle
import paddle.base.core as core

print("core attributes:")
attrs = [a for a in dir(core) if "flag" in a.lower() or "onednn" in a.lower() or "pir" in a.lower() or "global" in a.lower()]
print(attrs)

for a in attrs:
    val = getattr(core, a)
    print(f"  {a}: {type(val)} = {val}")

