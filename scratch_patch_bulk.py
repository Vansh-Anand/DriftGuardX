import os
from glob import glob

directory = "c:\\Users\\VANSH ANAND\\Desktop\\DriftGuardX"

search_text = "EvidenceClassification"
replace_text = "EvidenceClassification"

count = 0
for root, dirs, files in os.walk(directory):
    if ".git" in root or "node_modules" in root or ".next" in root or "__pycache__" in root:
        continue
    for file in files:
        if file.endswith(".py") or file.endswith(".tsx"):
            path = os.path.join(root, file)
            with open(path, encoding="utf-8") as f:
                content = f.read()
            if search_text in content:
                content = content.replace(search_text, replace_text)

                # Also do specific enum value replacements
                content = content.replace("EvidenceClassification.SYNTHETIC_SIMULATION", "EvidenceClassification.SYNTHETIC_SIMULATION")
                content = content.replace("EvidenceClassification.REAL_CONTROLLED_EXPERIMENT", "EvidenceClassification.REAL_CONTROLLED_EXPERIMENT")
                content = content.replace("EvidenceClassification.TEST_FIXTURE", "EvidenceClassification.TEST_FIXTURE")
                content = content.replace("EvidenceClassification.PRODUCTION", "EvidenceClassification.PRODUCTION")
                content = content.replace("EvidenceClassification.SYNTHETIC_SIMULATION", "EvidenceClassification.SYNTHETIC_SIMULATION")

                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                count += 1
                print(f"Updated {path}")
print(f"Total files updated: {count}")
