import os

for root, _, files in os.walk("tests"):
    for file in files:
        if file.endswith(".py"):
            filepath = os.path.join(root, file)
            with open(filepath, encoding="utf-8") as f:
                content = f.read()
            if "is_synthetic=True" in content or "is_synthetic=False" in content:
                content = content.replace("is_synthetic=True", "evidence_class=\"SYNTHETIC_SIMULATION\"")
                content = content.replace("is_synthetic=False", "evidence_class=\"REAL_PRODUCTION\"")
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)
                print(f"Fixed {filepath}")
