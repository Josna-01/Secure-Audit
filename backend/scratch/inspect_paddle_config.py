import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import paddle.inference as paddle_infer

print("paddle_infer.Config methods:")
methods = [m for m in dir(paddle_infer.Config) if not m.startswith("_")]
print(methods)

cfg = paddle_infer.Config()
print("\nTesting methods on cfg:")
for m in methods:
    if "pir" in m.lower() or "ir" in m.lower() or "dnn" in m.lower() or "exec" in m.lower():
        print("  -", m)
