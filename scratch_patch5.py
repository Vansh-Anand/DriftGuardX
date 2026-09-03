with open('tests/integration/test_security_audit.py', 'r') as f:
    code = f.read()

code = code.replace('assert cert["approval_state"] == "APPROVED"', 'assert cert["is_valid"] == True')

with open('tests/integration/test_security_audit.py', 'w') as f:
    f.write(code)
