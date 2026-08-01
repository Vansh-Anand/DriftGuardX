# DriftGuard-X Patent Application Figures

**Status: CONFIDENTIAL — Pre-Filing. Not Legal Advice.**

Each figure below corresponds to the BRIEF DESCRIPTION OF THE DRAWINGS in the patent claims draft. These are intended for conversion to formal USPTO-compliant black-and-white line drawings by patent illustration counsel.

---

## FIG. 1 — Overall System Architecture

```mermaid
flowchart TB
    classDef box fill:#fff,stroke:#333,stroke-width:1px,color:#000
    classDef store fill:#f9f9f9,stroke:#666,stroke-dasharray:4 2,color:#000

    A["100\nTRACE INGESTION\nINTERFACE\n(SpanRecord Ingestor)"]:::box
    B["110\nCAUSAL DAG\nCONSTRUCTION\nMODULE"]:::box
    C["120\nNODE FEATURE\nEXTRACTOR\n(6-Dim Vector)"]:::box
    D["130\nGRAPH ATTENTION\nNETWORK ENGINE\n(3-Layer GAT)"]:::box
    E["140\nSYMPTOM REGISTRY\n& ROOT-CAUSE\nRANKER"]:::box
    F["150\nBCRB SCHEDULER\n(UCB + Knapsack)"]:::box
    G["160\nARC-ISOLATED\nSANDBOX\n(Subprocess)"]:::box
    H["170\nSTATISTICAL BOUNDS\nCERTIFICATION\n(Hoeffding/Bootstrap/Conformal)"]:::box
    I["180\nHIERARCHICAL\nPOLICY ENGINE\n(4-Level Tightening)"]:::box
    J["190\nCRYPTOGRAPHIC\nMERKLE LEDGER\n(Ed25519 Chain)"]:::box
    K[("200\nPERSISTENT\nTRACE STORE\n(PostgreSQL/SQLite)")]:::store

    A --> B --> C --> D --> E --> F --> G --> H --> I --> J
    G -. "staged mutations\n(VTI 2PC)" .-> K
    A -. "span persistence" .-> K
```

---

## FIG. 2A — End-to-End Data Flow (Sequence Diagram)

```mermaid
sequenceDiagram
    autonumber
    box Operator / CI Pipeline
        actor OPS as 210 Operator
    end
    box DriftGuard-X Control Plane
        participant API as 220 FastAPI Server
        participant DB as 230 Trace Store
        participant GAT as 240 GAT Engine
        participant REG as 250 Symptom Registry
        participant BCRB as 260 BCRB Scheduler
        participant SBX as 270 ARC Sandbox
        participant CERT as 280 Certification Module
        participant POL as 290 Policy Engine
        participant LDG as 295 Merkle Ledger
    end

    OPS->>API: [1] POST /v1/telemetry (span records)
    API->>DB: [2] Persist span records
    OPS->>API: [3] POST /v1/detectors/gat/evaluate-run/{run_id}
    API->>DB: [4] Query spans for run
    API->>GAT: [5] Build DAG + extract 6-dim node features
    GAT->>GAT: [6] Execute 3-layer GAT inference
    GAT->>REG: [7] Register fault classification + root-cause ranking
    REG-->>API: [8] Structured diagnostic report
    API->>BCRB: [9] Schedule bounded counterfactual interventions
    loop For each selected intervention
        BCRB->>SBX: [10] Execute in ARC-isolated subprocess
        SBX-->>BCRB: [11] Outcome + staged actions
        BCRB->>CERT: [12] Compute confidence interval (Hoeffding/Bootstrap/Conformal)
        CERT-->>BCRB: [13] BoundResult or UnsupportedBound
    end
    BCRB-->>API: [14] Best verified intervention + bounds
    API->>POL: [15] Evaluate recovery action against policy hierarchy
    POL-->>API: [16] APPROVED / DENIED
    API->>LDG: [17] Emit Ed25519 recovery certificate
    LDG-->>OPS: [18] Certificate + Merkle proof
```

---

## FIG. 2B — ARC Isolation Subsystem Detail

```mermaid
flowchart LR
    classDef host fill:#e8f4fd,stroke:#2196F3,color:#000
    classDef sub fill:#e8fde8,stroke:#4CAF50,color:#000
    classDef sink fill:#fdecea,stroke:#f44336,color:#000
    classDef block fill:#fff3e0,stroke:#FF9800,color:#000

    subgraph HOST["HOST PROCESS (Main)"]
        H1["300\nSandboxedWorker\n.run(func, inputs)"]:::host
        H2["310\nSpawn Subprocess\n(multiprocessing.Process)"]:::host
        H3["320\nCollect return_dict\nfrom Manager"]:::host
        H4["330\nVTI 2PC: Commit\nStaged Actions to DB"]:::host
    end

    subgraph SUBPROCESS["SUBPROCESS (Isolated Address Space)"]
        S1["340\nRegister sys.addaudithook\n(_sandbox_audit_hook)"]:::sub
        S2["350\narc_isolator.enable()\nMonkey-patch:\nos.system\nsubprocess.run\nsocket.socket"]:::sub
        S3["360\nExecute user func(**inputs)"]:::sub
    end

    subgraph INTERCEPT["INTERCEPTION LAYER"]
        I1["370\nAudit Event:\nsocket.*\nDetected"]:::block
        I2["380\nARCIsolator:\nMockSocket.connect()"]:::block
        I3["390\nHardwareDataSink\n.commit(NETWORK_CALL)"]:::sink
        I4["400\nSynthetic Loopback\nResponse returned\nto func"]:::sink
        I5["410\nSandboxViolation\nError raised\n(if ARC disabled)"]:::block
    end

    H1 --> H2 --> SUBPROCESS
    S1 --> S2 --> S3
    S3 -->|"socket call\ndetected"| I1
    I1 -->|"ARC enabled"| I2 --> I3 --> I4 -->|"return\nto func"| S3
    I1 -->|"ARC disabled"| I5 -->|"error\npropagated"| H3
    S3 -->|"func\ncomplete"| H3 --> H4
```

---

## FIG. 3 — Graph Attention Network Architecture

```mermaid
flowchart TB
    classDef feat fill:#e3f2fd,stroke:#1565C0,color:#000
    classDef conv fill:#f3e5f5,stroke:#6A1B9A,color:#000
    classDef norm fill:#e8f5e9,stroke:#2E7D32,color:#000
    classDef pool fill:#fff3e0,stroke:#E65100,color:#000
    classDef cls fill:#fce4ec,stroke:#880E4F,color:#000

    F["500\nNODE FEATURE VECTORS\ndim = 6\n[log_duration, rel_duration,\nself_time_ratio, is_error,\nfanout, op_hash]"]:::feat

    C1["510\nGATConv LAYER 1\nin=6 → hidden × 4 heads\nheads=4, dropout=0.2\noutput dim = hidden×4"]:::conv
    N1["511\nLayerNorm(hidden×4)"]:::norm
    A1["512\nELU Activation"]:::norm

    C2["520\nGATConv LAYER 2\nin=hidden×4 → hidden × 4 heads\nheads=4, dropout=0.2\noutput dim = hidden×4"]:::conv
    N2["521\nLayerNorm(hidden×4)"]:::norm
    A2["522\nELU Activation"]:::norm

    C3["530\nGATConv LAYER 3\nin=hidden×4 → hidden\nheads=1, concat=False\ndropout=0.2\noutput dim = hidden"]:::conv
    N3["531\nLayerNorm(hidden)"]:::norm
    A3["532\nELU Activation"]:::norm

    P1["540\nGlobal MEAN Pool\ndim = hidden"]:::pool
    P2["541\nGlobal MAX Pool\ndim = hidden"]:::pool
    CAT["542\nConcatenate\ndim = hidden×2"]:::pool

    CLS["550\nCLASSIFIER HEAD\nLinear(hidden×2, 64)\nReLU\nDropout(0.3)\nLinear(64, num_classes)\nSoftmax"]:::cls
    OUT["560\nOUTPUT\nFault Probability per Class\n+ Root-Cause Node Scores"]:::cls

    F --> C1 --> N1 --> A1 --> C2 --> N2 --> A2 --> C3 --> N3 --> A3
    A3 --> P1 & P2
    P1 & P2 --> CAT --> CLS --> OUT
```

---

## FIG. 4 — BCRB Scheduler: UCB + Knapsack Mechanism

```mermaid
flowchart TB
    classDef init fill:#e3f2fd,stroke:#1565C0,color:#000
    classDef score fill:#f3e5f5,stroke:#6A1B9A,color:#000
    classDef sel fill:#fff3e0,stroke:#E65100,color:#000
    classDef exec fill:#e8f5e9,stroke:#2E7D32,color:#000
    classDef upd fill:#fce4ec,stroke:#880E4F,color:#000

    I["600\nINITIALIZE\nFor each arm i:\n  mu_i = diffusion prior\n  n_i = 0\n  t = 0\nBudget B, Costs c_i"]:::init

    SC["610\nCOMPUTE SCORES\nFor each arm i:\n  UCB_i = mu_i + sqrt(2*ln(t)/n_i)\n  priority_i = UCB_i * (v_i / c_i)"]:::score

    KS["620\nKNAPSACK SELECTION\nSort arms by priority_i desc\nGreedy-select arms while\n  sum(c_selected) <= B"]:::sel

    EX["630\nEXECUTE SELECTED\nFor each selected arm:\n  Run in ARC sandbox\n  Observe reward r_i\n  Compute bound"]:::exec

    UPD["640\nUPDATE BELIEFS\n  mu_i = (mu_i * n_i + r_i) / (n_i + 1)\n  n_i += 1\n  t += 1\n  Remaining_B -= c_i"]:::upd

    DONE["650\nTERMINATE\nWhen B exhausted\nor no arms selectable\nReturn best arm argmax(mu_i)"]:::sel

    I --> SC --> KS --> EX --> UPD --> SC
    UPD -->|"budget\nexhausted"| DONE
```

---

## FIG. 5 — Four-Level Policy Inheritance Hierarchy

```mermaid
flowchart TB
    classDef lvl fill:#e3f2fd,stroke:#1565C0,color:#000
    classDef deny fill:#fce4ec,stroke:#C62828,color:#000
    classDef approve fill:#e8f5e9,stroke:#1B5E20,color:#000
    classDef critical fill:#fff3e0,stroke:#E65100,color:#000

    ORG["700\nLEVEL 1: ORGANIZATION\nGlobal max_cost_usd, forbidden_actions\nDefault-deny on unknown"]:::lvl
    BU["710\nLEVEL 2: BUSINESS UNIT\nTenant isolation\nInherits from Org (tightening only)"]:::lvl
    PIP["720\nLEVEL 3: PIPELINE\nPipeline-scoped budget constraints\nInherits from BU (tightening only)"]:::lvl
    AGT["730\nLEVEL 4: AGENT\nAgent-level action allowlist\nInherits from Pipeline (tightening only)"]:::lvl

    RESOLVE["740\nTIGHTENING RESOLVER\nEffective policy =\nmost restrictive node\nacross all 4 levels"]:::lvl

    RISK["750\nRISK TIER REGISTRY\nLOW / MEDIUM / HIGH / CRITICAL"]:::lvl

    subgraph CRITICAL_FLOW["CRITICAL ACTION FLOW"]
        direction LR
        C1["760\nRequest created\nby Requestor"]:::critical
        C2["761\nSelf-approval check:\nSelfApprovalError if\nrequestor == approver"]:::deny
        C3["762\nApprover 1 APPROVED\n(delegated_approver only)"]:::approve
        C4["763\nApprover 2 APPROVED\n(distinct from Approver 1)"]:::approve
        C5["764\nStatus: APPROVED\n(2 of 2 required)"]:::approve
        C1 --> C2 --> C3 --> C4 --> C5
    end

    BG["770\nBREAK-GLASS\nOverride\n(Emergency)"]:::deny
    AUDIT["771\nAudit log entry emitted:\nrequires_post_hoc_review=True"]:::deny

    ORG --> BU --> PIP --> AGT --> RESOLVE --> RISK
    RISK -->|"CRITICAL"| CRITICAL_FLOW
    RISK -->|"Emergency"| BG --> AUDIT
```

---

## FIG. 6 — Statistical Bounds Certification Pipeline

```mermaid
flowchart TB
    classDef input fill:#e3f2fd,stroke:#1565C0,color:#000
    classDef hoeff fill:#f3e5f5,stroke:#6A1B9A,color:#000
    classDef boot fill:#e8f5e9,stroke:#2E7D32,color:#000
    classDef conf fill:#fff3e0,stroke:#E65100,color:#000
    classDef sent fill:#fce4ec,stroke:#C62828,color:#000
    classDef cert fill:#e0f2f1,stroke:#004D40,color:#000

    IN["800\nREWARD OBSERVATIONS\nX_1,...,X_n from replay episodes\nn, confidence delta, regime"]:::input

    H["810\nHOEFFDING BOUND\nAssumptions:\n  X_i in [0,1] (verified)\n  n >= 1, i.i.d.\nepsilon = sqrt(ln(2/delta)/(2n))"]:::hoeff
    B["820\nBOOTSTRAP INTERVAL\nAssumptions:\n  n >= 10\n  Exchangeable\nB=2000 resamples\n[alpha/2, 1-alpha/2] quantiles"]:::boot
    C["830\nCONFORMAL INTERVAL\nAssumptions:\n  Separate calibration split\n  Exchangeable scores\nMarginal coverage guarantee"]:::conf

    CHECK["840\nASSUMPTION\nCHECKER\n  n sufficient?\n  Bounds in range?\n  Calibration fresh?"]:::input

    SENT["850\nUnsupportedBound\nis_supported=False\n(Fail-closed sentinel)"]:::sent

    MON["860\nCOVERAGE MONITOR\nEmpirical coverage\nvs nominal level\nRolling production window"]:::cert

    ALERT["861\nUndercoverageAlert\n(coverage drift detected)"]:::sent
    DOWNGRADE["862\nCERTIFIED → UNCERTIFIED\n(certificate downgrade)"]:::sent

    CERT["870\nBoundResult\nis_supported=True\nlower, upper bounds\nconfidence level"]:::cert

    IN --> H & B & C
    H & B & C --> CHECK
    CHECK -->|"assumptions\nfail"| SENT
    CHECK -->|"assumptions\npass"| CERT
    CERT --> MON
    MON -->|"undercoverage\ndetected"| ALERT --> DOWNGRADE
```

---

## FIG. 7 — Tamper-Evident Ed25519 Merkle Ledger

```mermaid
flowchart TB
    classDef entry fill:#e3f2fd,stroke:#1565C0,color:#000
    classDef sig fill:#f3e5f5,stroke:#6A1B9A,color:#000
    classDef chain fill:#e8f5e9,stroke:#2E7D32,color:#000
    classDef verify fill:#fff3e0,stroke:#E65100,color:#000
    classDef tamper fill:#fce4ec,stroke:#C62828,color:#000

    G["900\nGENESIS ENTRY\ncert_id_0\ntimestamp_0\naction_id_0\nprev_hash = '0'*64"]:::entry

    E1["910\nCERTIFICATE ENTRY 1\ncert_id_1\ntimestamp_1\naction_id_1\nprev_hash = SHA256(entry_0)"]:::entry
    S1["911\nEd25519 Signature\nover canonical_fields(entry_1)\nusing private_key"]:::sig

    E2["920\nCERTIFICATE ENTRY 2\ncert_id_2\ntimestamp_2\naction_id_2\nprev_hash = SHA256(entry_1)"]:::entry
    S2["921\nEd25519 Signature\nover canonical_fields(entry_2)"]:::sig

    EN["930\nCERTIFICATE ENTRY N\nprev_hash = SHA256(entry_N-1)\nEd25519 Signature"]:::entry

    VER["940\nCLI VERIFIER\n  For each entry i:\n    Recompute SHA256(entry_i-1)\n    Verify == entry_i.prev_hash\n    Verify Ed25519 sig\n    using public_key"]:::verify

    OK["950\nVERIFICATION: PASS\nChain integrity confirmed\nNo private key required"]:::chain
    FAIL["951\nVERIFICATION: FAIL\nTampering detected at entry i\nHash chain broken"]:::tamper

    G --> E1 --> E2 --> EN
    E1 --- S1
    E2 --- S2
    EN --> VER
    VER -->|"all sigs valid\nhash chain intact"| OK
    VER -->|"mismatch\ndetected"| FAIL
```

---

*CONFIDENTIAL — These figures are intended for conversion to formal USPTO black-and-white line drawings by patent illustration counsel. Not a legal filing.*
