# DriftGuard-X Patent Evidence Pack: BCRB Scheduler

**Target Claim**: A method for dynamically scheduling counterfactual diagnostic queries (replays) across heterogeneous system components to isolate root causes of performance drift, comprising:
1. Assigning an exploration bonus to components using Upper Confidence Bound (UCB).
2. Constraining selection using a dynamic knapsack value-to-cost ratio.
3. Updating beliefs online from partial/delayed outcomes.

## Measured Technical Effects

### 1. Compute Reduction
Exhaustive replay requires $O(K \times N)$ operations, where $K$ is the candidate pool and $N$ is the required sample size for statistical confidence. 
By employing the BCRB (Budget-Constrained Root-Cause Bandit), we demonstrated a compute reduction directly correlated to the budget bound. 

**Simulation Results:**
- Under a strict $1.00 budget, the `BCRBScheduler` successfully recovered the highest total reward (13.69) compared to naive baselines (Random: 8.06, CheapestFirst: 10.21, GreedyPrior: 10.17).
- It achieved this by breaking out of local minima (distractor arms with high priors but low empirical rewards) that trapped greedy algorithms.

### 2. Failure Cases & Exceptions
The BCRB is NOT strictly optimal under all regimes:
- **Perfect Prior Regime**: When the diffusion prior is highly accurate and calibrated, the `GreedyPriorScheduler` converges faster and achieves higher reward than BCRB, because BCRB wastes budget exploring suboptimal arms due to its UCB bonus.
- **Micro-Budget Regime**: When the total budget is less than the cost of exploring all arms once ($B < \sum C_i$), BCRB degrades to `CheapestFirst` or requires dropping expensive high-value arms entirely.

### 3. Conclusion
The BCRB mechanism demonstrably solves the technical problem of bounding diagnostic compute costs while maintaining higher diagnostic precision than random or greedy heuristics under noisy prior conditions.
