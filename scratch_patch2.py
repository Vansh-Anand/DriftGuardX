with open('apps/api/src/services/recovery_pipeline.py', 'r') as f:
    code = f.read()

code = code.replace('if not candidates:\n            return None', 'if not candidates:\n            print("No candidates returned by BCRBOrchestrator")\n            return None')
code = code.replace('if not diagnosis.root_cause_component:\n            return None', 'if not diagnosis.root_cause_component:\n            print("No root_cause_component in diagnosis")\n            return None')
code = code.replace('if not self.canary_framework.validate_quarantine(rule, run_id):\n                return None', 'if not self.canary_framework.validate_quarantine(rule, run_id):\n                print("validate_quarantine failed")\n                return None')

with open('apps/api/src/services/recovery_pipeline.py', 'w') as f:
    f.write(code)
