**FinSkillBench: Evaluating AI Agents and Domain Skills for Investment Management**

**WHAT IT IS**

FinSkillBench is a domain-specific evaluation suite designed to measure whether large language model (LLM) agents can effectively leverage financial domain skills to solve real investment management tasks. Unlike general-purpose LLM benchmarks that test open-ended generation, FinSkillBench targets a high-stakes workflow where agents must retrieve point-in-time data, assemble correct computational inputs, invoke specialized quantitative methods, and produce auditable structured outputs. The benchmark spans three core investment management domains:

- **Portfolio Construction** – building and optimizing asset allocations under constraints
- **Risk Management** – quantifying and mitigating portfolio-level and factor-level exposures
- **Fundamental Analysis** – extracting and reasoning over company-level financial and operational data

The suite comprises **12 distinct subtasks** across these three domains, totaling **2,603 task episodes** in the primary evaluation. Each episode is structured around three components:

- **Point-in-time inputs** – historical or snapshot data that the agent must work with (no look-ahead bias)
- **Hidden ground truth** – a pre-computed correct answer that is not exposed to the agent during inference
- **Task-specific verifier** – a deterministic or rule-based scoring function tailored to each subtask, ensuring objective and reproducible grading rather than LLM-as-judge subjectivity

**HOW IT WORKS**

The evaluation is organized around three experimental conditions that isolate the effect of "skills" (reusable procedural knowledge and executable components) from raw model capability:

- **Condition 1 – No Skill:** The agent receives only the task prompt and raw data, with no external procedural guidance. This establishes the baseline capability of each model.
- **Condition 2 – Curated Skill Packages:** The agent is provided with hand-engineered skill packages consisting of (a) **procedural documents** (structured natural-language instructions describing the correct workflow, formulas, and decision logic for a given subtask) and (b) **executable components** (pre-written code modules or function stubs the agent can call to perform specific computations such as Sharpe ratio calculation, factor exposure decomposition, or cash-flow statement reconciliation).
- **Condition 3 – Self-Generated Skills:** The agent is allowed to **write its own procedural code and documentation during an episode** and then **reuse those self-authored procedures** across subsequent steps within the same episode. This tests whether the agent can bootstrap its own toolchain on the fly.

**Scale of the evaluation:**

- **Primary run:** 9 LLMs tested across all 2,603 episodes under all three conditions.
- **Independent replication run:** Conducted using a **separate agent framework (Hermes Agent)** with **8 models** and **5,280 total episodes**, confirming that findings are not an artifact of a single orchestration stack.

**Key quantitative findings:**

- Curated skill packages **consistently raise mean task-completion scores from 0.366 (no skill) to 0.528**, representing a relative improvement of roughly 44%.
- The **largest absolute gains** from curated skills appear in **portfolio construction** and **risk management** subtasks, where multi-step computational pipelines (e.g., constructing a mean-variance frontier, computing Value-at-Risk, or stress-testing factor exposures) benefit most from pre-specified procedural scaffolding and correct function calls.
- **Self-generated skills provide minimal performance benefit** despite incurring **higher computational cost** (additional inference rounds for writing, testing, and iterating on self-authored code), indicating that current-generation models struggle to reliably bootstrap correct financial computation pipelines without external guidance.
- The directional pattern (curated > no skill >> self-generated) **reproduces across all three domains** in the independent Hermes Agent evaluation, though the **magnitude of the skill effect varies by subtask and by the specific agent harness** used.

**WHY IT MATTERS TO DEVELOPERS AND RESEARCHERS**

- **Skill access is a first-class design variable.** The results demonstrate that for investment management agents, the quality and availability of procedural skills can matter **as much as the choice of base model**. A mid-tier model paired with well-structured curated skills can outperform a top-tier model running with no skills, directly informing cost-benefit decisions in production deployments.
- **Auditable, structured output is validated.** Because each episode uses a deterministic verifier and hidden ground truth, FinSkillBench provides a framework for building **regulator-friendly, explainable AI pipelines** in finance—critical for firms subject to SEC, Basel, or Solvency II obligations.
- **Self-generation is not a silver bullet.** The finding that agents writing their own code and procedures within an episode yields little upside and higher latency is a concrete caution for teams exploring "self-referential tool-building" patterns (e.g., ReAct-style self-coding agents) in quantitative finance contexts.
- **Open resources for the community.** The authors release the **full benchmark, evaluation tooling, curated skill packages, and complete agent trajectories** (step-by-step action/observation logs), enabling reproducibility, ablation studies, and rapid integration into internal model-evaluation pipelines.
- **Cross-framework robustness check.** By replicating results on the **Hermes Agent** framework with a different set of models, the authors mitigate the common criticism that benchmark results are overfit to a single orchestration layer (e.g., LangChain or AutoGen-specific behaviors).

**Specific use cases and subtask types covered (12 subtasks across 3 domains):**

- Portfolio construction: mean-variance optimization, constraint-based allocation, rebalancing under transaction costs
- Risk management: VaR/CVaR computation, factor exposure decomposition, stress-test scenario generation
- Fundamental analysis: financial statement ratio extraction, cash-flow reconciliation, earnings-quality flagging

**Architecture and framework names referenced:**

- **FinSkillBench** (the benchmark suite)
- **Hermes Agent** (independent replication framework)
- 9 models in primary evaluation; 8 models in replication (specific model names listed in the full paper)
- Curated skill packages (procedural documents + executable components)

The work is published under arXiv:2608.18099v1 in the **cs.AI** category.

Source: https://arxiv.org/abs/2608.18099

---

**WHAT THIS IS**

Hierarchical Self-Improvement (HSI) is a research framework that rethinks how LLM-based agents are improved after deployment. Instead of treating the "harness"—the executable scaffold, prompt structure, tool bindings, and workflow logic that wraps around a frozen language model—as a static, hand-tuned artifact, HSI makes the harness itself a continuously evolvable, task-specific object. The core premise is that for a given frozen backbone model (e.g., DeepSeek-V4-Flash-Preview), significant performance gains can still be extracted by iteratively rewriting the surrounding agent code, guided by environment feedback, without a single parameter update to the model. The paper positions this as a practical middle ground between full fine-tuning (expensive, task-locked) and prompt-only tuning (shallow, fragile).

**HOW IT WORKS — ARCHITECTURE AND MECHANICS**

- **Three-level hierarchical scope (the "HSI stack"):**
  - **Level 1 – Task Harness (H):** A self-contained executable module that ingests a task description through a fixed task-injection seam, interacts with the environment (perceive → think → act loop), and emits actions. H is the artifact that gets hot-swapped between iterations. Each task family (e.g., text-based planning, 2D grid-worlds) maintains its own H.
  - **Level 2 – Evolver:** A meta-program (itself LLM-generated code) whose sole job is to inspect execution traces, reward signals, and failure logs from the current H and then *rewrite H* into a next-generation version. The evolver reads and writes source-level harness code, not just prompts.
  - **Level 3 – Meta-Evolver:** Operates under a frozen outer anchor (a fixed set of constraints and guardrails). It does not rewrite H directly; instead, it rewrites the *evolver's strategy code*—the heuristics, search policies, and mutation operators the evolver uses—so that the evolver itself improves over time. This creates a two-derivative optimization loop (evolver improves H; meta-evolver improves the evolver).

- **Thinking-on / Thinking-off design:** To isolate the contribution of harness evolution from the model's own chain-of-thought capability, HSI deliberately *disables* the backbone's extended reasoning (thinking) during task execution at Level 1, while *enabling* it at Levels 2 and 3 during self-modification. This experimental control shows that gains come from structural code changes in H, not from the model simply "thinking harder" at inference time.

- **Evolution loop (per iteration):**
  1. Freeze backbone M.
  2. Inject current task T via the fixed seam into the current H.
  3. Execute H in the environment; collect trajectories, rewards, and failure traces.
  4. Evolver reads traces + reward → generates a rewritten H'.
  5. Meta-Evolver periodically inspects the evolver's own mutation history → rewrites the evolver's strategy under the frozen outer anchor.
  6. Repeat (hot-swap H → H' → H'' …).

- **Two theoretical bounds that cap HSI:**
  - **Feedback-fidelity bound:** Evolution is only as good as the reward/signal pipeline. If the environment reward is sparse, noisy, or misaligned, the evolver cannot perform meaningful selection, and harness rewrites regress toward noise.
  - **Backbone capability bound:** Harness redesign can reorganize *how* the model is queried, but it cannot conjure reasoning capabilities the frozen model M simply lacks. This is empirically confirmed (see NLE results below).

**KEY BENCHMARKS AND METRICS**

All results use **DeepSeek-V4-Flash-Preview** as the frozen backbone, evaluated on the **BALROG** benchmark suite:

- **BabyAI (moderate-difficulty 2D grid-world):** +39.3 percentage points in raw % Progress over the initial hand-written harness.
- **Crafter (2D crafting/exploration):** +33.0 pp.
- **TextWorld (text-based game planning):** +25.0 pp.
- **MiniHack (Roguelike-style grid game):** +15.0 pp.
- **BabaIsAI (logic/puzzle, held-out generalization from a 20% unseen split):**
  - BreakStop sub-suite: **0.98 best-test** accuracy.
  - GoTo sub-suite: **1.00 best-test** accuracy (perfect score on unseen puzzles).
- **NLE (high-difficulty natural-language game, beyond backbone capability):** Harness evolution yields **no measurable improvement**—the backbone capability bound is binding.

**WHY THIS MATTERS TO DEVELOPERS**

- **No fine-tuning required.** Teams shipping LLM agents can keep the backbone model frozen (cost, latency, and licensing unchanged) and still close a 15–40 point gap on moderate tasks purely through harness-level code evolution.
- **Task-specific, portable harnesses.** Because each task family owns its own H, a logistics-planning agent, a customer-support agent, and a code-review agent can each evolve independently without cross-contamination, yet share the same backbone.
- **Clear, auditable failure modes.** The two theoretical bounds (feedback fidelity, backbone capability) give engineers a diagnostic checklist: if HSI plateaus, either instrument better reward signals or upgrade the backbone—rather than blindly rewriting prompts.
- **Reproducible, open-source implementation.** The full framework is public at https://github.com/TailinZhou/hsi, making it directly applicable to production agent pipelines that need iterative, feedback-driven refinement without retraining.
- **Generalization evidence.** The BabaIsAI results (0.98–1.00 on 20% unseen splits) suggest the evolved harness encodes transferable structural strategies, not overfit task-specific hacks—important for teams deploying agents to new, unseen scenarios.
- **Practical boundary-setting.** The NLE null result is as useful as the positive results: it tells developers that no amount of scaffold engineering will make a 1B-scale flash model solve tasks requiring deep multi-step planning, preventing wasted R&D cycles.

**SOURCE**

https://huggingface.co/papers/2608.08466

---

**WHAT IT IS**

GOAG (Generative and Object-Agnostic Grasp Planner) is a novel deep generative model designed for dexterous multifingered robotic grasping. Developed by researchers at CEA-LIST, it fundamentally rethinks how grasp planners are formulated: rather than learning object-specific grasp policies from large, curated datasets, GOAG inverts the paradigm by learning a *gripper-centric* representation of its own contact surface distribution and then resolving valid grasps at inference time against whatever object is presented. It targets the core limitation of existing deep-learning grasp planners—their poor generalization to unseen objects due to reliance on limited, object-specific training corpora.

**HOW IT WORKS**

- **Core geometric insight:** At every valid contact point between a gripper and an object, the two surfaces share *identical local surface geometry* (matching normals, curvature, and tangential contact constraints). GOAG exploits this symmetry to decouple gripper modeling from object modeling.
- **Latent gripper representation:** The model is trained as a deep generative model that compresses the full contact-surface distribution of a specific gripper (contact normals, feasible contact-area manifolds, joint-space constraints) into a compact latent code. Training requires only the gripper's geometric description—no object data.
- **Inference-time object conditioning:** Object point-cloud or mesh features are injected *exclusively* at inference time. The model retrieves, from the latent gripper distribution, the subset of contact configurations whose surface geometry is admissible for the given object, effectively sampling valid grasp poses without any retraining.
- **Sampling efficiency:** Because the search space is the gripper's own compact latent manifold rather than the full 3D contact-space, generating large batches of candidate grasps is significantly faster than methods that enumerate object-specific collision checks in high-dimensional space.
- **Validation protocols:** Experiments span both simulation (standard grasp benchmark suites) and physical real-world manipulation tests, using multiple dexterous grippers drawn from the literature (not a single proprietary hand).
- **Benchmark & metric:** On the **MultiDex** dataset, GOAG achieves an **average success rate of 86.93 %**, matching or exceeding leading object-specific methods that were explicitly trained on that dataset's objects, while generating grasps at a substantially lower computational cost when large numbers of grasps are requested.

**WHY IT MATTERS TO DEVELOPERS AND RESEARCHERS**

- **Eliminates the object-data bottleneck:** Traditional data-driven grasp planners require thousands of labeled grasp samples per object category. GOAG removes this requirement entirely; a new object in the scene is handled with zero additional training, making deployment in open-ended warehouses, surgical settings, or disaster-response robots dramatically simpler.
- **Gripper-agnostic architecture pattern:** Because the model is trained per-gripper rather than per-object, swapping to a new hand (e.g., moving from a Shadow Hand to a Barrett Hand) only requires retraining the small gripper-encoder network, not rebuilding the entire grasp pipeline.
- **Scalability for mass-grasp generation:** The compact latent sampling mechanism means that planning N candidate grasps for pick-and-place, bin-picking, or multi-object rearrangement tasks scales sub-linearly compared to per-object collision-checked planners—critical for time-constrained manipulation stacks.
- **State-of-the-art on a recognized benchmark:** The 86.93 % average success on MultiDex (a widely used dexterous-grasp benchmark) puts GOAG at the frontier of published results, validated in both simulation and real hardware, which gives engineers confidence to integrate it into production manipulation pipelines.
- **Open-sourced for reproducibility:** Code, videos, and project assets are publicly available, lowering the barrier for robotics teams to benchmark, fine-tune, or extend the method to their own gripper hardware.
- **Addresses a fundamental generalization gap:** By shifting the inductive bias from "learn objects" to "learn my own hand and match at contact time," GOAG directly tackles the unsolved problem of distribution shift in dexterous manipulation, a gap that purely data-driven end-to-end networks still struggle to close.

**CONCRETE USE-CASE EXAMPLES**

- Autonomous bin-picking in logistics where SKU shapes vary day-to-day and retraining is infeasible.
- In-hand object reorientation with a 6-DoF dexterous hand handling novel industrial parts.
- Surgical or rehabilitation robotics where the tool-gripper geometry is fixed but the tissue/implant geometry is variable per patient.
- Multi-robot systems that share a common gripper-encoder across heterogeneous hands, reducing per-robot deployment cost.

**Original Paper URL:** https://huggingface.co/papers/2608.19759

---

**WHAT CoToGrasp Is**

- CoToGrasp (Contact-Topology-Conditioned Dexterous Grasp Synthesis via Canonical Workspace Learning) is a generative framework for synthesizing diverse, physically stable dexterous grasps that are explicitly conditioned on a target contact topology rather than merely optimizing for static stability.
- It is developed by the CEA-LIST research group and is positioned as a solution to two long-standing gaps in robotic manipulation: (a) current planners answer "can the gripper hold this object?" instead of "how should it hold it to serve a downstream task?" and (b) conditioning on human grasp taxonomies (e.g., cylindrical, pinch, hook) traditionally demands object-level annotated datasets that are prohibitively expensive to collect.
- The framework is fully object-agnostic during training, meaning it never requires a per-object grasp annotation, and it generalizes to completely unseen object geometries at inference time (zero-shot).

**HOW CoToGrasp Works – Architecture and Training Pipeline**

- **Contact-topology conditioning:** Instead of a binary "stable / unstable" objective, the model takes as input a specific contact topology (the combinatorial pattern of which fingers/contact points engage which regions of the object). This encodes the semantic functional intent of the grasp (e.g., a cylindrical power grasp vs. a precision pinch) into the generation process.
- **Feature-based canonical workspace (the core novelty):**
  - Local geometric features of the target object are projected into a single, unified, gripper-centric coordinate frame.
  - This projection effectively normalizes away the arbitrary size, pose, and shape of the object, collapsing all objects into one shared "canonical" space defined by the gripper's own kinematics.
  - The result is a decoupling: the model reasons about *where on the gripper* contacts should occur and *what topology* they form, independent of *which specific object* is being grasped.
- **Intrinsic contact-manifold learning:** Within the canonical workspace, the model learns the intrinsic contact manifold of the dexterous hand—the low-dimensional manifold of feasible, stable contact configurations the fingers can achieve. By constraining generation to this learned manifold, the output grasps are guaranteed to be kinematically realizable by the hand hardware.
- **Object-agnostic training regime:** Because every object is mapped into the same gripper-centric feature space, the model never needs to memorize object-specific grasp distributions. Training data can be synthesized from generic geometry (e.g., procedurally generated meshes) without any human grasp-taxonomy labels.
- **Zero-shot inference:** At test time, the geometry of a novel, previously unseen object is projected into the canonical workspace, and the model samples from the learned contact manifold to produce a topology-conditioned grasp without any fine-tuning or retrieval step.

**BENCHMARKS, EVALUATION, AND VALIDATION**

- **Primary benchmark:** The large-scale **DexGraspNet** dataset, which contains diverse dexterous grasp annotations across a wide variety of object categories and hand configurations.
- **Performance claim:** CoToGrasp achieves state-of-the-art results on DexGraspNet, outperforming existing taxonomy-guided planners that rely on object-annotated training data.
- **Physical-robot validation:** The synthesized grasps were executed on a **physical robot platform** (dexterous hand), confirming both:
  - *Physical viability* – the grasps produce actual stable contact under real-world dynamics (friction, compliance, payload).
  - *Kinematic feasibility* – the finger joint trajectories required to reach the synthesized contact configuration are within the hand's joint limits and reach envelope.
- **Code and reproducibility:** Source code and project assets are publicly available at **https://cea-list.github.io/cotograspweb/**.

**WHY THIS MATTERS TO DEVELOPERS AND RESEARCHERS**

- **Eliminates the annotation bottleneck:** Teams deploying dexterous hands in pick-and-place, assembly, or tool-use pipelines no longer need to collect and label thousands of per-object grasp demonstrations for each new SKU. A single object-agnostic model transfers across the entire object catalog.
- **Functional grasp selection, not just stability:** By conditioning on contact topology, a developer can programmatically request a "cylindrical power grasp" for lifting a bottle or a "two-finger precision grasp" for handling a wafer, enabling task-aware manipulation without hand-crafted planners per object class.
- **Plug-and-play with existing robot stacks:** Because the output is expressed in the gripper's own kinematic space (joint-space targets on a learned contact manifold), the grasps integrate directly into standard IK / trajectory-planning pipelines (MoveIt, ROS 2, or vendor SDKs) without additional geometric conversion.
- **Scales to long-tail objects:** The zero-shot property is critical in warehouses, electronics manufacturing, and recycling, where the set of objects is open-ended and constant; a taxonomy-guided model would require re-training for every new object family.
- **Open-source availability** from a public research group (CEA-LIST) lowers the barrier for academic and industry teams to benchmark against or build upon the canonical-workspace paradigm.

**KEY TERMS AND REFERENCES FOR FURTHER READING**

- Framework name: **CoToGrasp**
- Core concept: feature-based **canonical workspace**, intrinsic **contact manifold**, **contact-topology conditioning**
- Benchmark dataset: **DexGraspNet**
- Project / code: https://cea-list.github.io/cotograspweb/
- Institutional group: **CEA-LIST** (French alternative energy and low-carbon technologies research institute)
- Publication venue: Hugging Face Daily Papers (arXiv-style preprint)

https://huggingface.co/papers/2608.19776

---

**WHAT: Next-Audio-Patch-Embedding Prediction (NAPE)**

NAPE is a self-supervised audio representation learning framework published by researchers and featured on Hugging Face Daily Papers. It applies the autoregressive "predict the next element" paradigm—long dominant in large language models and increasingly adopted in visual foundation models—to the audio domain. Specifically, NAPE trains a causal Transformer to predict each successive patch embedding of a log-mel spectrogram from all preceding patches, using only causal masking and a stop-gradient operation as its training signal.

**Key design choices (intentional minimalism):**

- No reconstruction decoder (unlike contrastive-augmentation methods such as HuBERT/wav2vec 2.0 style setups).
- No discrete acoustic tokenizer (avoids VQ-VAE or similar quantization stages).
- No student-teacher distillation architecture (unlike BYOL-style or DINO-style audio SSL).
- No auxiliary regularization losses (no masking losses, no contrastive terms, no auxiliary prediction heads).
- The sole inductive bias is the causal (left-to-right) attention mask over temporal patches plus a stop-gradient to prevent the model from collapsing into a constant-output shortcut.

**HOW IT WORKS – Technical Mechanics:**

- **Input representation:** Raw audio is converted into a log-mel spectrogram, which is then segmented into overlapping or sequential patches along the time axis. Each patch is projected (via a lightweight embedding layer or the first Transformer block) into a continuous embedding vector.
- **Model backbone:** A standard causal (decoder-only) Transformer. At every position *t*, the model conditions only on patch embeddings from positions 1 … *t* (enforced by the causal attention mask) and outputs a prediction for the embedding at position *t + 1*.
- **Training objective:** A single regression/prediction loss between the predicted next patch embedding and the stop-gradient-applied ground-truth next patch embedding. The stop-gradient severs the gradient path through the target, ensuring the model learns genuine predictive structure rather than trivially mapping inputs to a shared constant.
- **No auxiliary heads:** There is no separate contrastive loss, no masked-patch reconstruction, no auxiliary prediction task. The architecture reduces to: [embedding layer → N × causal Transformer blocks → prediction head], trained end-to-end with one loss.
- **Emergent structure:** The authors report that the model spontaneously develops structured (e.g., temporal or harmonic) attention patterns in its self-attention maps without any explicit architectural constraint or supervision encouraging such behavior.

**WHY IT MATTERS – Results, Scaling, and Developer Relevance:**

- **Benchmark performance:** Evaluated across six audio and speech benchmarks (spanning both audio understanding and speech tasks), NAPE achieves state-of-the-art fine-tuning performance on several of them, matching or surpassing systems that rely on far more complex pre-training pipelines (contrastive + masked-reconstruction, distillation, quantization).
- **Scaling behavior:** Performance improves consistently and predictably as encoder width/depth are increased, indicating the objective does not hit a representation ceiling at small model sizes—a property developers value when selecting a base model for downstream fine-tuning at various compute budgets.
- **Linear-probing strength:** Frozen NAPE embeddings, without any downstream fine-tuning, produce strong linear-probing accuracy. This means developers can use NAPE as a plug-and-play feature extractor for lightweight applications (edge inference, rapid prototyping, few-shot transfer) without training additional parameters.
- **Simplicity and transferability:** Because the training recipe contains no modality-specific tricks (no audio tokenizers, no multi-branch contrastive losses), the same codebase and training loop can, in principle, be applied to other time-series modalities (e.g., biosignals, sensor streams) with minimal modification. This unifies the "predict the next embedding" interface across text, vision, and audio under one conceptual umbrella.
- **Reduced engineering complexity:** Teams building audio ML pipelines can drop components such as VQ-VAE tokenization, EMA-teacher updates, or multi-objective loss weighting, lowering hyperparameter search space, reducing training instability, and simplifying reproducibility.
- **Attention interpretability:** The emergent structured attention patterns give developers a built-in interpretability hook—visualizing which spectrogram patches the model attends to can aid debugging and model selection without requiring external explainability tooling.

**Architectural & Method Summary (at a glance):**

- Architecture name: Causal Transformer (decoder-only), with log-mel spectrogram patch embeddings as input.
- Training signal: Causal masking + stop-gradient next-embedding prediction (single objective).
- Explicitly excluded components: reconstruction decoders, acoustic/discrete tokenizers, student-teacher distillation, auxiliary regularization losses.
- Evaluation scope: 6 audio/speech benchmarks; reported SOTA fine-tuning, strong linear-probing, consistent scaling, emergent structured attention.

**Bottom line for developers:** NAPE demonstrates that the "predict the next token/embedding" recipe—already proven in LLMs and increasingly in vision—transfers cleanly to audio with a minimal, single-objective causal Transformer. For teams seeking a simple, scalable, and highly transferable audio encoder without the engineering overhead of multi-objective SSL recipes, NAPE represents a compelling new baseline to evaluate against.

Original source: https://huggingface.co/papers/2608.19863

---

**SWE-bench Science: Technical Summary**

**WHAT IT IS**

- SWE-bench Science is a repository-level benchmark specifically designed to evaluate the capabilities and failure modes of autonomous coding agents when performing scientific software engineering (SWE) tasks.
- Unlike generic coding benchmarks (e.g., the original SWE-bench) that often operate at the function or single-file level, this benchmark targets whole-repository problems where scientific code acts as part of the measurement or analytical instrument itself, meaning a bug can corrupt the evidentiary basis of a scientific claim.
- The benchmark comprises 119 curated tasks drawn from 98 real GitHub repositories spanning 20 distinct scientific domains (e.g., physics, biology, chemistry, materials science, astronomy, etc.), making it one of the most domain-diverse agent evaluations to date.
- It was published via Hugging Face Daily Papers (arXiv identifier 2608.19799) and is positioned as a diagnostic testbed for understanding *why* coding agents fail on scientific code, not just *whether* they succeed.

**HOW IT WORKS – TASK STRUCTURE AND EVALUATION PROTOCOL**

- **Three task paradigms** are used to tax different agent capabilities:
  - *Issue-driven*: The agent receives a GitHub-style issue description and must locate and repair the underlying defect in the repository.
  - *Expert-exploratory*: The agent is given a vague or high-level research question and must navigate the codebase, form hypotheses, and implement a fix without a precise bug report.
  - *Engineering-integration*: The agent must modify or integrate components across the repository, testing system-level coherence rather than isolated function correctness.
- **Evaluation metric**: The primary reported metric is pass@1 (single-attempt exact-resolution rate), emphasizing that the agent must produce a correct, complete repair in one shot.
- **Paired ablation study**: The authors run a controlled comparison in which explicit scientific guidance (e.g., domain-specific hints, expected physical/chemical behavior) is removed while the full repository context and executable engineering environment (unit tests, linting, type-checking) are preserved. This isolates the marginal contribution of scientific knowledge from raw coding ability.
- **Failure-mechanism taxonomy**: Every failure is manually categorized into one of four recurring mechanisms:
  1. Deficits in scientific knowledge or domain abstraction (agent does not understand the physics/biology/chemistry the code encodes).
  2. Misguided exploration or surface-level repair (agent patches symptoms without identifying the root cause, or searches the wrong module).
  3. Incomplete repair coverage or system-integration failure (agent fixes one function but breaks downstream dependents or misses a coupled component).
  4. Failure to generalize scientific knowledge beyond the observed test cases (overfitting to the specific test harness rather than encoding the correct domain invariant).

**KEY QUANTITATIVE FINDINGS**

- The best-performing agent evaluated—**Claude Code with Opus-5 (max)**—achieves a **pass@1 below 50%**, indicating that even frontier-scale models fail on more than half of repository-level scientific engineering tasks.
- In the ablation, removing scientific guidance produced a mixed result:
  - When the guidance was *well-grounded* (accurate, correctly scoped), it constrained the search space, improved average pass rate, and reduced token consumption per repair.
  - When the guidance was *poorly aligned* (vague, slightly inaccurate, or mis-scoped), it triggered an anchoring effect: the agent locked onto the misleading hint, wasted tokens, and did *not* improve exact-repair success over the no-guidance baseline.
- No single agent dominated across all three paradigms; performance gaps between paradigms (especially the Expert-exploratory set) were wider than between agents, suggesting task framing and domain reasoning are more limiting factors than raw code-generation capability.

**WHY IT MATTERS TO DEVELOPERS, RESEARCHERS, AND THE SCIENTIFIC SOFTWARE ECOSYSTEM**

- **Reliability of scientific conclusions**: In domains like genomics, climate modeling, particle physics, and computational chemistry, a silent bug in analysis code can invalidate published results. A benchmark that explicitly measures whether agents can *repair* such code—rather than merely write it from scratch—is critical for the growing use of AI in lab and field software.
- **Agent product development**: The four-mechanism taxonomy gives LLM-based agent developers (e.g., teams building Devin, SWE-agent, or IDE-integrated copilots) concrete failure categories to target in their training data, tool-use scaffolding, and evaluation pipelines.
- **Context-window and tooling design**: The token-efficiency findings from the ablation suggest that providing *precise, well-scoped* scientific context (not just a long domain brief) is more effective for guiding retrieval-augmented or tool-augmented agents, informing how context is assembled in production agent pipelines.
- **Benchmarking gap filled**: Prior benchmarks (SWE-bench, SWE-bench-Live, Multi-SWE-bench) skew toward web, systems, and general-purpose Python/JS repositories. SWE-bench Science introduces 20 scientific domains and repository-level integration tasks, filling a previously underrepresented niche in the agent-evaluation landscape.
- **Reproducibility and open science**: Because the benchmark is built from public GitHub repositories, any lab can reproduce the evaluation, contribute new domain tasks, or audit the failure annotations, supporting transparent progress tracking in scientific SWE.

**CONCRETE USE CASES AND PRACTICAL TAKEAWAYS**

- A computational-biology team maintaining a 200 kLOC simulation codebase can use SWE-bench Science task formats to stress-test whether their internal AI-assisted debugging pipeline catches domain-specific invariants (e.g., conservation laws, thermodynamic consistency) that generic unit tests miss.
- An LLM agent vendor can adopt the three-paradigm split (Issue-driven / Expert-exploratory / Engineering-integration) as an internal eval suite to regression-test model upgrades before deployment into scientific-industry clients (pharma, aerospace, energy).
- Researchers building retrieval-augmented agents can use the ablation protocol as a template: pair a domain-knowledge retrieval step with a no-retrieval control to quantify the *net* contribution of scientific context versus pure code-context reasoning.
- The below-50% pass@1 ceiling provides a realistic baseline: teams should not expect a single-shot autonomous fix for complex scientific SWE and should design human-in-the-loop review gates around agent output, especially for the Engineering-integration and Expert-exploratory paradigms where failure rates are highest.

**ORIGINAL SOURCE**

https://huggingface.co/papers/2608.19799

---

**What It Is**

- "Chain-of-Experience for Continual LLM Improvement" is a research paper (arXiv: 2608.18027) that formalizes a new inference-time learning paradigm called **Chain-of-Experience (CoE)**, in which large language models iteratively interact with themselves or their environment to accumulate experiential traces and improve their answers *during* a single test-time session, rather than relying solely on a single zero-shot or few-shot pass.
- The work is positioned as a bridge between static benchmark evaluation and human-like continuous learning: instead of treating each query as an isolated event, CoE treats multi-turn inference as a **continual improvement loop** where prior attempts, self-generated critiques, and external correctness signals feed back into subsequent generations.
- The study is evaluated across **three task domains** — mathematics, coding, and general knowledge — using **8 frontier LLMs**, explicitly including **GPT-5**, **Gemini-2.5 Pro**, and **Claude-4.5 Sonnet** as representative of the current model landscape.

**How It Works**

- **Core loop:** For each task instance the model produces an initial answer, then enters an iterative refinement cycle. In each cycle the model receives one or more *feedback signals*, conditions on them, and produces a revised answer. The accumulated history of past answers and feedback forms the "chain of experience."
- **Feedback channels instantiated in the paper:**
  - *Self-feedback (model-as-critic):* The LLM generates its own critique, error analysis, or alternative reasoning trace without any external oracle.
  - *Environmental / correctness feedback:* Binary or graded signals such as whether a math derivation is numerically correct, whether generated code passes **public unit-test suites** (e.g., LeetCode-style or Codeforces-style pass rates), or whether a knowledge answer matches a reference.
  - *Complementary multi-channel fusion:* Combining self-feedback with an independent correctness signal simultaneously to exploit distinct improvement dimensions.
- **Evaluation protocol:** Each of the 8 LLMs is run in both a feedback-free baseline mode and a CoE mode across the math, coding, and knowledge benchmarks. The paper measures (a) absolute accuracy gains, (b) **accuracy per token** as an efficiency metric, (c) **API cost** across the iterative session, and (d) robustness under intentionally weak or spurious feedback.
- **Key quantitative results reported:**
  - Self-feedback alone produces **substantial gains** over the feedback-free zero-shot baseline across all three domains and all eight models.
  - The combined CoE protocol achieves a **5.6 % overall accuracy improvement** (averaged across tasks and models) while simultaneously reducing **API cost by 19 %** relative to naively sampling more attempts.
  - CoE delivers **higher accuracy per token** than existing test-time strategies (e.g., self-consistency, best-of-N sampling), indicating that structured experience accumulation is more token-efficient than brute-force re-sampling.
  - **Most of the improvement is realized in the first few iterations**, after which the marginal gain plateaus — a practical signal for setting a low iteration budget in production.
  - A **positive correlation** is observed between a model's base (zero-shot) ability and its capacity to benefit from CoE: stronger base models extract more value from the same feedback signals.
  - Models demonstrate **robustness to weak or spurious feedback** (e.g., noisy correctness labels), suggesting the mechanism does not catastrophically degrade when feedback quality is imperfect.

**Why It Matters to Developers and Practitioners**

- **Cost-efficiency at inference time:** The 19 % API-cost reduction at +5.6 % accuracy means teams can get measurably better outputs *cheaper* than simply increasing the number of parallel samples or raising temperature, which has direct budget implications for high-volume LLM applications (coding assistants, math tutoring bots, RAG pipelines).
- **A framework beyond "self-consistency":** CoE provides a structured, multi-turn refinement architecture that is more general than one-shot self-consistency or best-of-N. Developers can plug in *any* available signal — a compiler, a unit-test harness, a human-in-the-loop verdict, or a retrieval-grounded fact check — as an environmental feedback channel without retraining.
- **Practical iteration budget:** Because gains concentrate in the first few CoE cycles, production systems can cap refinement at 2–3 iterations to capture most of the benefit while controlling latency, rather than running unbounded loops.
- **Model-agnostic design:** The protocol is not tied to a specific architecture; it works across GPT-5, Gemini-2.5 Pro, Claude-4.5 Sonnet, and five other LLMs, making it a drop-in inference wrapper for heterogeneous fleets.
- **Robustness to imperfect signals:** The demonstrated tolerance to weak or spurious feedback reduces the engineering burden of building perfect evaluation oracles; even a coarse pass/fail test signal or a heuristic linter score can meaningfully improve final answers.
- **Bridging evaluation and deployment:** By showing that standard benchmark scores (zero-shot) systematically *underestimate* a model's real-world capability when iterative interaction is allowed, the paper argues that deployment architectures should allocate compute to the CoE loop rather than solely to pre-training scale, shifting engineering focus toward test-time compute strategies.
- **Complementary feedback as an architectural pattern:** The finding that self-critique and external correctness signals address *distinct* improvement dimensions suggests a principled way to design multi-agent or pipeline systems where a "critic" LLM and a "validator" service (e.g., a sandboxed code runner) operate in parallel, each feeding back into the generator.

**Summary of Concrete Metrics and Models**

- Models evaluated: GPT-5, Gemini-2.5 Pro, Claude-4.5 Sonnet, plus 5 additional LLMs (8 total).
- Domains: Mathematics, Coding (public test pass rates), Knowledge QA.
- Headline results: +5.6 % average accuracy gain, −19 % API cost, higher accuracy-per-token than self-consistency / best-of-N baselines.
- Iteration dynamics: Majority of CoE gains realized in the earliest iterations; diminishing returns thereafter.
- Feedback robustness: Graceful degradation under weak/spurious external signals.
- Base-ability correlation: Stronger zero-shot models show larger CoE gains.

Source: https://huggingface.co/papers/2608.18027

---

**FlashPrefill V2: Block-Sparse Prefill Attention for Long-Context LLM Serving**

**WHAT IT IS**

FlashPrefill V2 is a production-oriented block-sparse attention mechanism designed specifically to accelerate the prefilling phase of long-context Large Language Model (LLM) inference. It is the second-generation evolution of the original FlashPrefill, which was an algorithmic prototype relying on instantaneous pattern discovery and max-based dynamic thresholding. FlashPrefill V2 closes the gap between research prototype and deployable serving infrastructure by addressing approximation accuracy, hardware-level operator efficiency, and framework-level integration. It is designed to run as a drop-in attention backend within modern LLM inference frameworks such as SGLang, targeting workloads where context lengths extend to 128K tokens or beyond.

**HOW IT WORKS**

The architecture evolves along three concrete technical dimensions:

- **Mean Correction Term for Error Suppression**
  - The original FlashPrefill used a max-based dynamic threshold to select which attention blocks to compute, but this introduced non-trivial approximation error, especially as sparsity increased.
  - FlashPrefill V2 introduces an explicit mean correction term that compensates for the skipped attention blocks, effectively bounding the approximation error.
  - This allows the system to operate at extreme sparsity ratios (skipping a large fraction of the attention matrix) while keeping perplexity and downstream task performance degradation within acceptable bounds.

- **Redesigned Sparse Attention Operator (Hardware-Level)**
  - **PackGQA Memory Access:** The operator restructures how Grouped Query Attention (GQA) KV tensors are fetched from HBM, packing grouped heads into contiguous memory accesses to reduce bandwidth pressure on the sparse block pattern.
  - **Warp Specialization:** Different warps within a CTA are assigned specialized roles (e.g., one warp handles block-selection metadata, another performs the actual matmul, a third manages output accumulation), reducing intra-warp divergence and improving occupancy.
  - **Pingpong Pipelining:** Two computation stages are overlapped (one warp group computes while the other waits on memory), hiding HBM latency behind FLOPs—mirroring the software-pipelining strategy used in FlashAttention-3/4.
  - **FP8 Inference Support:** The operator natively supports FP8 (E4M3/E5M2) dot-product execution, aligning with quantization requirements for cost-sensitive production deployments. This is significant because the sparse attention kernel is not a separate code path but is fully integrated with the same pipelining structure as the dense FA3/4 kernels.
  - The overall kernel design is explicitly stated to be "fully aligned with the latest FlashAttention-3/4 implementations," meaning it leverages the same Blackwell/Hopper-specific tensor-core scheduling and shared-memory tiling strategies.

- **Framework-Native Integration**
  - **Paged KV Cache Support:** FlashPrefill V2 operates directly on non-contiguous, paged KV storage (as used by vLLM and SGLang), eliminating the need to gather scattered KV pages into a contiguous buffer before the sparse attention pass.
  - **Continuous Batching:** The sparse block-selection and computation pipeline is designed to handle variable-length sequences and new-token arrivals within a single batch iteration, which is the default scheduling mode in production serving stacks.
  - **SGLang Backend Integration:** It can be registered as an attention backend in SGLang, meaning the sparse prefill path is transparently selected at runtime based on sequence length and sparsity configuration without application-level changes.

**WHY IT MATTERS TO DEVELOPERS**

- **Quadratic Attention is the Dominant Prefill Cost:** At 128K context length, dense self-attention requires ~16.4 billion attention-score elements per head per layer. FlashPrefill V2's block-sparse approach computes only a small fraction of those elements, turning an O(n²) prefill into an effectively near-linear operation while preserving output quality.
- **Production-Grade, Not a Research Demo:** Unlike the first-generation FlashPrefill, V2 addresses the three practical gaps that blocked deployment—approximation error, lack of hardware-optimized operators, and missing framework integration. A developer can integrate it into a SGLang deployment without writing custom glue code.
- **Quantization-Ready:** Native FP8 support means the speedup advantage is not sacrificed when deploying with quantized weights, which is the standard practice for reducing inference cost on H100/H20-class hardware.
- **Concrete Benchmark Results (NVIDIA H20 GPUs, 128K context):**
  - **47.26× speedup** over FlashAttention-2 in FP8 precision.
  - **27.19× speedup** over FlashAttention-2 in BF16 precision.
  - **30.49× speedup** over a FlashAttention-3/4-aligned dense baseline in FP8—proving the gain is not merely due to outperforming an older kernel but represents a genuine architectural advantage even against the latest dense attention implementations.
- **Target Hardware:** NVIDIA H20 GPUs are highlighted as the evaluation platform, which are among the most widely deployed inference accelerators in current production environments (particularly in data-center deployments subject to certain export-control tiers), making the benchmarks directly relevant to a large installed base.
- **Use Cases:** Long-context document QA, multi-turn agentic workloads with growing context, codebase-level summarization, and any serving scenario where prefill latency (not decode latency) dominates end-to-end response time.

**Key Architectural References:** FlashAttention-2, FlashAttention-3, FlashAttention-4, SGLang, GQA (Grouped Query Attention), FP8 (E4M3/E5M2), Paged KV Cache, NVIDIA H20.

**Primary Trade-off to Monitor:** The mean correction term bounds but does not eliminate approximation error. At the extreme sparsity ratios needed for 47× speedups, quality-sensitive applications (e.g., mathematical reasoning, precise retrieval) should be validated against dense baselines before production rollout.

Source URL: https://huggingface.co/papers/2608.19758