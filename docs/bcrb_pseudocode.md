# Measured Resource-Admission Controller (BCRB)

The Budget-Constrained Root-Cause Bandit (BCRB) is designed to optimize the selection of diagnostic replays in constrained environments (e.g., edge devices or highly concurrent serverless environments).

This document outlines the formal pseudocode and assumptions for the Resource-Admission Controller.

## Assumptions

1.  **Multi-Dimensional Exhaustion**: A replay sandbox may crash or be terminated if it exceeds limits in wall-clock time, memory, token usage, tool calls, CPU, or GPU. The controller must model the limit of the *most constrained* resource. For simplicity, we project multi-dimensional constraints onto a single normalized "cost" metric (e.g., USD or a composite score), but hard-enforce the multi-dimensional budget constraints.
2.  **Uncertainty Distribution**: Cost (latency, memory, etc.) is modelled as a Gaussian distribution. While real-world tail latencies are often long-tailed (e.g., log-normal), using the empirical mean and variance provides a fast, bounded heuristic.
3.  **Stationarity**: We assume the cost distribution is roughly stationary over the short duration of a diagnostic session.
4.  **Telemetry Honesty**: We assume the telemetry reported back from the sandbox accurately reflects physical resource usage (no adversarial hiding of GPU cycles).

## Pseudocode

```text
Algorithm: Resource-Admitted BCRB
Inputs:
  - C: Candidate arms {a_1, a_2, ..., a_n}
  - B: Remaining budget
  - R: Rollback reserve margin
  - k: Uncertainty multiplier (e.g., 2.0 for ~95% CI)
  - E: Execution Budget (multi-dimensional hardware limits)
  
State:
  - H: History of actual measured costs H[a] = [c_1, c_2, ...]
  - U: Utilities (Expected rewards) U[a]
  - N: Pull counts N[a]

Function SelectArm(C):
    # 1. Multi-dimensional hard-limit check
    if E is exhausted in any physical dimension:
        return None (Terminate)
        
    Admitted = []
    
    # 2. Pre-emptive Shedding (Admission Rule)
    for a in C:
        if length(H[a]) >= 2:
            mu_a = mean(H[a])
            sigma_a = std_dev(H[a])
        else:
            mu_a = a.prior_cost
            sigma_a = 0.0
            
        uncertainty_margin = k * sigma_a
        
        # Explicit Admission Rule
        if (mu_a + uncertainty_margin) <= (B - R):
            Admitted.append(a)
            
    if Admitted is empty:
        return None (Terminate)
        
    # 3. Deterministic Tie-Breaking
    Sort Admitted lexically by a.arm_id
    
    # 4. Knapsack-UCB Selection
    best_arm = None
    best_score = -infinity
    
    for a in Admitted:
        if N[a] == 0:
            reward = a.prior_reward
            bonus = exploration_constant
        else:
            reward = U[a] / N[a]
            bonus = exploration_constant * sqrt(log(sum(N)) / N[a])
            
        ucb = reward + bonus
        effective_cost = max(mean(H[a]), epsilon)
        score = ucb / effective_cost
        
        if score > best_score:
            best_score = score
            best_arm = a
            
    return best_arm
```
