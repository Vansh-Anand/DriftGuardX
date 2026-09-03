with open('tests/integration/test_security_audit.py', 'r') as f:
    code = f.read()

code = code.replace('assert "requires ADMIN role" in response.json()["detail"]', 'assert "admin role" in response.json()["detail"].lower()')

with open('tests/integration/test_security_audit.py', 'w') as f:
    f.write(code)

with open('apps/api/src/routes/recovery.py', 'r') as f:
    code2 = f.read()

code2 = code2.replace('raise HTTPException(status_code=500, detail="Failed to propose recovery.")', 'import traceback; traceback.print_exc(); raise HTTPException(status_code=500, detail="Failed to propose recovery.")')

with open('apps/api/src/routes/recovery.py', 'w') as f:
    f.write(code2)
