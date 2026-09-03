with open('apps/api/src/routes/recovery.py', 'r') as f:
    code = f.read()

code = code.replace('    db.add(decision_orm)\n\n    if decision', '    db.add(decision_orm)\n    await db.flush()\n\n    if decision')
code = code.replace('evidence_kind=ctx["evidence_kind"],', 'evidence_kind=RecoveryEvidenceKind(ctx["evidence_kind"]),')

with open('apps/api/src/routes/recovery.py', 'w') as f:
    f.write(code)
