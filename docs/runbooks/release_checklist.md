# Release Checklist

> [!CAUTION]
> Do not approve a production deployment until ALL items are checked and signed off by the Release Manager.

## Pre-Flight
- [ ] Clean CI pass from the main branch.
- [ ] Container Vulnerability Scans (`generate_sbom_scan.py`) meet severity gates (0 Critical, 0 High).
- [ ] SLSA Provenance Attestation is generated and signed.

## Staging & Smoke Testing
- [ ] Deployed to staging cluster.
- [ ] Staging Smoke Tests passed: Trace ingestion -> Budget verification -> Policy generation -> Certificate issuance.
- [ ] Dashboard metrics in Grafana reflect staging traffic correctly.

## Production Audit
- [ ] Database migrations are reviewed and confirmed strictly additive.
- [ ] `docs/runbooks/disaster_recovery.md` has been reviewed and a backup drill was performed in the last 30 days.

## Sign Off
- **Release Manager**: _____________
- **Security Auditor**: _____________
