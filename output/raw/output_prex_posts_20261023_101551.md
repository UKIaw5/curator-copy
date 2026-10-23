**Overview**
The repository `ikow/php2shell-poc` is a critical security research artifact providing Proof of Concept (PoC) code and detection methodologies for two newly disclosed vulnerabilities, identified as CVE-2026-109618 and CVE-2026-109619. These vulnerabilities affect the PHP core engine, specifically targeting the `session.upload_progress` mechanism, allowing for pre-authentication Remote Code Execution (RCE). The tool serves a dual purpose: it demonstrates the exploit chains for risk assessment and provides hardened detection rules for network and host-based intrusion prevention systems.

**Technical Mechanisms and Exploit Architecture**
*   **Target Vector:** The exploits leverage the internal `session.upload_progress` feature in PHP. This mechanism is designed to track file upload progress in the server-side session store. The research identifies a flaw in how PHP processes or exposes this progress data during the upload handshake or session initialization, occurring before any user authentication is required.
*   **Pre-Auth RCE Chains:** The project outlines **5 distinct RCE chains**. These chains likely involve:
    1.  Manipulating the `PHP_SESSION_UPLOAD_PROGRESS` file upload trigger.
    2.  Exploiting a memory corruption or logic error in the session handler’s processing of the progress key/value pairs.
    3.  Achieving arbitrary code execution (likely via command injection or deserialization vulnerabilities) without valid credentials.
*   **Vulnerability IDs:** The specific CVEs (CVE-2026-109618 and CVE-2026-109619) suggest two separate but related flaws, potentially covering different PHP versions or different facets of the `session.upload_progress` implementation (e.g., one for data overflow, another for logic bypass).

**Defensive Detection and Mitigation**
The repository goes beyond offensive PoC by providing a comprehensive detection suite, which is crucial for SOC teams and blue-team analysts:
*   **Suricata Rules:** Network-level signatures to detect malicious HTTP requests attempting to trigger the `session.upload_progress` exploit patterns. This allows for real-time blocking at the perimeter.
*   **Sigma Rules:** Host-based detection logic designed to analyze PHP application logs and process execution. It identifies the specific post-exploitation commands or anomalous file creations associated with the RCE chains.
*   **ModSecurity Rules:** Web Application Firewall (WAF) rules to inspect HTTP payloads for the specific malformed data or parameter manipulations required to trigger the vulnerability. This offers a layer of defense at the web server level.

**Significance for Developers and Security Teams**
*   **Immediate Action Required:** As these are pre-authentication RCE vulnerabilities, any running PHP instance potentially affected is at critical risk of immediate compromise. The availability of public PoC code significantly reduces the barrier for automated scanning and exploitation.
*   **Detection Engineering Value:** Unlike many PoC repositories that only provide exploit scripts, this project is notable for its integrated defensive tooling. The inclusion of Suricata, Sigma, and ModSecurity rules allows security engineers to deploy detection across the entire kill chain (network, application, and host) immediately.
*   **Architectural Insight:** The focus on `session.upload_progress` highlights a common blind spot in secure coding practices where standard library features are assumed to be safe. Developers auditing their PHP applications should verify how they handle file uploads and session data, particularly in edge cases involving progress tracking.

**Key Metrics and Artifacts**
*   **CVEs:** CVE-2026-109618, CVE-2026-109619
*   **Exploit Chains:** 5 distinct pre-auth RCE paths
*   **Detection Formats:** Suricata (NIDS/NIPS), Sigma (Host/Log), ModSecurity (WAF)
*   **Affected Component:** PHP `session.upload_progress` extension/core functionality

https://github.com/ikow/php2shell-poc

<<<CURATOR_ITEM_BOUNDARY>>>

**Overview: LM2LM and the Path to Recursive Self-Improvement**

LM2LM (Language Models to Improve Language Models) is a novel framework designed to automate the discovery of effective architectural and training modifications for Large Language Models (LLMs). This research addresses the critical bottleneck in "AI for AI" pipelines: the high cost and instability associated with using Reinforcement Learning (RL) to train LLMs that can autonomously propose and validate model improvements. By decoupling expensive real-world execution from the learning loop, LM2LM enables models to learn the *ability* to improve other models without incurring the computational burden of running full training cycles for every proposal during the RL phase.

**Core Technical Challenges Addressed**

The paper identifies two primary hurdles in automating LM research using RL:

*   **Prohibitive Computational Cost:** Traditional RL for this task requires collecting rewards from real experimental outcomes. Evaluating tens of thousands of proposals, where each might require a full model-training run (approx. 10 GPU-hours per run), results in hundreds of thousands of GPU-hours just for reward collection. This makes direct RL training on real feedback economically and practically infeasible.
*   **Reward Hacking and Distribution Shift:** When using a surrogate reward model (a model that predicts outcomes rather than measuring them), the RL policy tends to exploit biases in the surrogate. As the policy optimizes, it drifts toward proposing "overestimated" improvements—proposals that score highly on the surrogate but perform poorly in reality. This leads to unreliable feedback signals and degraded performance.

**Methodology: How LM2LM Works**

LM2LM employs a hybrid approach combining a **Research World Model (RWM)** with periodic real-world validation to solve the cost-reliability trade-off.

*   **Research World Model (RWM) as Reward Model:**
    *   Instead of running actual training jobs for every proposal, LM2LM uses a frozen LLM acting as a "world model."
    *   This RWM is conditioned on **real experimental records** (context) containing past proposals, their configurations, and their measured performance gains.
    *   The RWM predicts the expected gain of a new proposal generated by the policy model. This predicted gain serves as the reward signal for the RL optimization loop, allowing for massive parallelization of proposal evaluation at near-zero computational cost per step.

*   **Periodic Real-Execution Calibration:**
    *   To prevent the RWM from becoming stale or unreliable due to distribution shift, the system implements a feedback loop.
    *   Periodically, the policy generates a batch of proposals. The RWM ranks them, and the top-ranked proposals are **actually executed** in the real environment.
    *   The true measured outcomes of these real executions are appended to the RWM’s context window. This "ground-truth" injection continuously calibrates the RWM, ensuring its predictions remain aligned with reality even as the policy model evolves.

**Key Results and Metrics**

*   **Benchmark Performance:** LM2LM was evaluated across **eight distinct environments** covering both autoregressive and diffusion-based LM development tasks.
*   **Model Comparison:** The system enables **Qwen3.8-27B** to outperform **GPT-6-sol**.
*   **Efficiency Advantage:** LM2LM achieves this superior performance while requiring **33% lower data-generation cost** compared to the baseline. Notably, GPT-6-sol was given a significant advantage of **300 real experimental records** in its context, yet LM2LM still outperformed it.
*   **Generalization:** The approach demonstrates strong generalization capabilities, successfully transferring to model families that were **unseen during training**, indicating that the model has learned general principles of LM improvement rather than overfitting to specific architectures.

**Why This Matters to Developers and Researchers**

*   **Cost-Effective AI R&D:** For organizations building automated AI research pipelines, LM2LM drastically reduces the GPU overhead associated with hyperparameter search and architecture discovery. It allows for thousands of "thought experiments" at the cost of only occasional real validations.
*   **Robustness in Automation:** By addressing reward hacking through dynamic context updating (RWM), this framework offers a more stable and reliable method for automating complex engineering tasks than standard surrogate-based RL.
*   **Foundation for Recursive Self-Improvement:** This work is a step toward true recursive self-improvement, where AI systems not only improve themselves but also become proficient at designing and optimizing other AI systems, reducing the reliance on human intuition for next-generation model architecture.

**Conclusion**

LM2LM represents a significant advancement in the automation of machine learning research. By leveraging a context-aware Research World Model for scalable feedback and periodic real-world execution for reliability, it provides a viable, cost-efficient path for LLMs to autonomously discover effective improvements in other language models.

https://huggingface.co/papers/2610.23344

<<<CURATOR_ITEM_BOUNDARY>>>

**Technical Summary: FrontierCS 2 Benchmark Analysis**

**What It Is**
FrontierCS 2 is a rigorous benchmark designed to evaluate the capability of Large Language Model (LLM) agents to perform genuine research and development (R&D) in frontier Computer Science, rather than solving isolated, static programming problems. It consists of 48 open-ended tasks derived from actual published academic papers and their associated open-source repositories. Additionally, the benchmark maintains a private, non-public set of over 100 tasks reserved for future challenges. The core objective is to measure whether AI agents can inherit an existing codebase and make substantive contributions that match the specific contributions made by human researchers.

**How It Works**
The benchmark employs a novel "in-research-environment" evaluation methodology that differs significantly from traditional static benchmarks:

*   **Task Construction via Contribution Deletion:** For each task, the original paper’s specific technical contribution is identified and removed from both the documentation and the released code. This deleted segment serves as the "human reference," establishing the performance bar that the agent must meet.
*   **Dynamic Repository Inheritance:** Unlike benchmarks that provide a clean problem statement, FrontierCS 2 places the agent inside a working, complex research environment. The agent inherits the full repository context, including existing dependencies, architecture, and partial implementations.
*   **Iterative Patch Submission with Opaque Evaluation:**
    *   The agent may submit code patches at any point during the session.
    *   For each intermediate patch, a judge returns a score based on a "development suite," but the specific details of the evaluator, the held-out final test suite, and the human reference remain private to the agent.
    *   The final submission is graded strictly against the private held-out final suite and compared against the human reference contribution.
*   **Multi-Domain Coverage:** The 48 public tasks span 13 distinct Computer Science domains, including:
    *   Machine Learning Systems
    *   High-Performance Computing (HPC)
    *   Database Systems
    *   Cybersecurity
    *   Robotics

**Why It Matters to Developers**
FrontierCS 2 provides a more realistic indicator of LLM utility in professional software engineering and research contexts by addressing several key limitations of previous benchmarks:

*   **Contextual Complexity:** It tests an agent’s ability to navigate and modify existing, complex codebases rather than generating scripts in a vacuum. This is more representative of real-world developer workflows involving legacy code, integrated systems, and incremental updates.
*   **Rigorous Success Metrics:** The benchmark distinguishes between "beating the reference score" and actually "passing." Data indicates that even when agents achieve higher combined final scores than the human reference, they often fail on specific metrics or workloads, highlighting that aggregate scores can mask critical functional deficiencies.
*   **Benchmarking Real-World R&D Capacity:** By using actual academic contributions as the gold standard, the benchmark measures an agent’s ability to replicate high-level scientific reasoning and engineering implementation, which is crucial for developers relying on AI for advanced R&D assistance.

**Key Performance Metrics & Findings**
*   **Top Performer:** Claude Opus 5.5 emerged as the strongest agent among the 12 evaluated.
*   **Pass Rate:** The best agent passed 58% of its total runs.
*   **Task Difficulty Distribution:**
    *   No single task was passed by all runs of all agents.
    *   On a shared capability scale, the median task difficulty is roughly equivalent to the maximum capability of the strongest current agent (Claude Opus 5.5), indicating that FrontierCS 2 remains a highly challenging benchmark for state-of-the-art models.
*   **Score vs. Pass Discrepancy:** A significant number of runs that exceeded the human reference in combined final scores still failed to meet the specific criteria for a "pass," underscoring the benchmark’s strict multi-metric evaluation protocol.

Source: https://huggingface.co/papers/2610.29932

<<<CURATOR_ITEM_BOUNDARY>>>

### Technical Summary: Stratified Sparse Attention (SSA)

**Overview**
Stratified Sparse Attention (SSA) is a novel inference framework designed to optimize Long-Context Large Language Model (LLM) performance by resolving the efficiency-accuracy trade-off inherent in sparse attention mechanisms. Traditional sparse attention methods struggle with an "accuracy gap" when operating at extreme sparsity levels (high compression ratios). SSA bridges this gap by unifying deterministic token retrieval with statistical sampling, allowing models to maintain high accuracy while significantly reducing the computational cost associated with the Key-Value (KV) cache.

**How It Works: Technical Architecture & Mechanism**
*   **Unified Framework Logic:** SSA operates as a hybrid system that combines two distinct attention strategies:
    *   **Deterministic Retrieval:** The method first identifies and attends to high-scoring tokens using standard retrieval techniques (equivalent to Top-k selection).
    *   **Score-Guided Sampling:** For the residual attention mass (the probability weight not captured by the top tokens), SSA employs a sampling mechanism guided by proxy attention scores.
*   **Probability Correction:** A key differentiator is the inclusion of a correction factor for sampling probabilities. By accounting for the likelihood of sampled tokens, SSA recovers attention mass that would otherwise be lost in pure retrieval methods or corrupted by noise in pure sampling methods.
*   **Generalization:** The framework is mathematically generalized such that Top-k, Top-p (nucleus sampling), and hybrid Top-k + uniform sampling are all special cases of SSA. This allows for a unified tuning process rather than disjoint method selection.
*   **Implementation Optimization:** The method utilizes optimized CUDA kernels to ensure that the theoretical accuracy gains translate into tangible hardware-level speedups, specifically targeting decode phase acceleration.

**Performance Metrics & Benchmarks**
*   **Benchmark Scope:** Evaluated across RULER, LongBench, LOFT, and AIME using five model architectures ranging from 3B to 27B parameters (including Ministral-3-8B).
*   **Accuracy Gains (RULER-HARD):**
    *   At **32K context length** with 50x attention sparsity: SSA improved accuracy from **81.8%** (strongest baseline) to **84.2%**, recovering **94%** of dense-attention performance.
    *   At **128K context length** with 50x attention sparsity: SSA improved accuracy from **63.8%** to **69.3%**, recovering **85%** of dense-attention performance.
*   **Inference Speed:**
    *   Achieved up to **2.96x decode speedup** compared to FlashInfer at **1M context** length.
    *   Demonstrates that SSA maintains accuracy advantages even under aggressive sparsity constraints where other methods degrade significantly.

**Why It Matters to Developers**
*   **Cost-Efficiency for Long Contexts:** Developers building applications requiring long-context processing (e.g., document analysis, codebase understanding) can significantly reduce GPU memory bandwidth and compute costs by using extreme sparsity without the typical accuracy penalty.
*   **Practical Deployment:** Unlike academic sampling methods that often suffer from high variance or inconsistent results, SSA provides a deterministic-retrieval foundation with statistical enhancement, offering a more reliable drop-in replacement for standard attention mechanisms.
*   **Hardware Acceleration:** The provided optimized CUDA kernels allow for immediate integration into high-performance inference pipelines, delivering nearly 3x speedups at scale, which is critical for serving LLMs with multi-million token contexts.
*   **Open Source Availability:** The code is publicly available for immediate experimentation and integration into production systems.

Source: https://huggingface.co/papers/2610.28441

<<<CURATOR_ITEM_BOUNDARY>>>

### **Executive Summary: StyleStream 2.0**

**StyleStream 2.0** is a fast and controllable streaming Voice Style Conversion (VSC) framework designed to address the latency constraints and lack of textual controllability found in previous generation systems. It achieves a **2x speedup** in inference speed and introduces a novel text-conditioned interface for both designing new voices and editing specific vocal attributes in real-time.

---

### **1. What is StyleStream 2.0?**

*   **Core Functionality:** A zero-shot Voice Style Conversion system that transforms a source audio utterance to match the timbre, accent, and emotion of a target voice while strictly preserving linguistic content.
*   **Key Differentiator:** Unlike StyleStream 1.0, which was limited to audio-to-audio conversion, StyleStream 2.0 introduces a **text-based interface** for voice manipulation.
    *   **Voice Design:** Generates a new voice style from a natural language prompt (e.g., "whispery and tired female voice").
    *   **Voice Editing:** Modifies specific attributes of a source utterance (e.g., change "happiness" to "sadness") while preserving non-edited attributes.
*   **Performance Goal:** Optimized for low-latency streaming on consumer-grade hardware, reducing end-to-end latency from ~1s to **520ms**.

---

### **2. How It Works: Technical Architecture**

The system relies on two key architectural innovations: a specialized flow-matching backbone and a decoupled style-embedding pathway.

#### **A. Latency Optimization: Few-Step Pixel MeanFlow + Self Forcing**
To achieve sub-600ms latency, the system replaces the standard diffusion/flow-matching sampling process with a more efficient training and inference strategy:
*   **Pixel MeanFlow Model:** The backbone is trained as a **few-step pixel MeanFlow** model. This reduces the number of sampling steps required to generate high-fidelity audio, directly impacting inference speed.
*   **Autoregressive Feedback (Self Forcing):** The model is fine-tuned using **autoregressive feedback inspired by "Self Forcing."**
    *   *Mechanism:* This technique improves robustness under streaming inference by forcing the model to predict future frames based on its own previous outputs, minimizing error accumulation in long-form or real-time streams.
    *   *Result:* Maintains conversion quality despite the aggressive reduction in sampling steps.

#### **B. Controllability: Compact Style Embedding & Unified Flow Matching**
To enable text-based control, StyleStream 2.0 removes the direct reliance on mel-spectrogram context for style transfer and instead routes style information through a dedicated vector space.
*   **Compact Style Embedding:** Target style information is encoded into a **compact style embedding** rather than being derived from raw mel-spectrograms. This decouples style from content, allowing for precise manipulation.
*   **Unified Text-Conditioned Flow Matching Model:**
    *   A single flow matching model is trained in this embedding space to handle both **design** and **editing**.
    *   **Text-to-Style Mapping:** The model learns to map natural language prompts directly to points in the style embedding space.
    *   **Attribute-Specific Editing:** By conditioning on specific text instructions, the model can modify targeted attributes (e.g., emotion, timbre) within the embedding space without disturbing the linguistic content or unrelated style features.

---

### **3. Why It Matters to Developers & Researchers**

*   **Real-Time Interactivity:** With **520ms end-to-end latency** on a consumer GPU, StyleStream 2.0 enables true real-time voice interaction for applications such as:
    *   Live dubbing for video games or virtual assistants.
    *   Real-time voice cloning in streaming video calls.
    *   Interactive storytelling where voice styles change dynamically with user input.
*   **Simplified Voice Engineering:** Developers no longer need to provide a target audio reference for every style change. Instead, they can use **natural language prompts** to define or edit voices, lowering the barrier to entry for non-audio-engineers and enabling dynamic, script-driven voice generation.
*   **Efficient Deployment:** The system is optimized for **consumer hardware**, meaning it does not require data-center-grade GPUs (e.g., A100/H100) for production-level inference, reducing deployment costs.
*   **SOTA Quality Metrics:** Experiments demonstrate that StyleStream 2.0 achieves the **strongest target style fidelity** in:
    *   Zero-shot VSC.
    *   Text-based voice design.
    *   Instruction-based voice editing.
    *   It remains competitive on **intelligibility** and **non-edited attribute preservation**, ensuring that changing one aspect of the voice (e.g., emotion) does not degrade the clarity or other stable traits (e.g., pitch).

---

### **Key Metrics & Benchmarks**

| Metric | StyleStream 1.0 | StyleStream 2.0 | Improvement |
| :--- | :--- | :--- | :--- |
| **End-to-End Latency** | ~1000 ms | **520 ms** | **2x Faster** |
| **Hardware Requirement** | Consumer GPU | Consumer GPU | Same |
| **Style Control Interface** | Audio-to-Audio | **Text-Based** (Design & Edit) | New Feature |
| **Target Style Fidelity** | SOTA | **Strongest** (SOTA+) | Improved |
| **Intelligibility** | Competitive | Competitive | Maintained |
| **Attribute Preservation** | N/A | **Competitive** | New Feature |

---

### **Use Cases**

1.  **Dynamic Voice Acting:** A developer can script a character whose voice becomes "more angry" or "more tired" in real-time based on game events, using text instructions like *"increase anger by 20%"*.
2.  **Personalized AI Companions:** Users can describe their preferred AI assistant voice in natural language (e.g., "calm, deep baritone") without needing to record a reference sample.
3.  **Accessibility & Localization:** Real-time streaming VSC for live translation scenarios where the speaker's voice style must be preserved or adapted on the fly.

---

### **Source**
https://huggingface.co/papers/2610.28940

<<<CURATOR_ITEM_BOUNDARY>>>

**Project Overview**
Aerial-TV is an open-source Android TV launcher designed specifically to replace the bloated, ad-heavy default interfaces found on China-market consumer electronics, such as Xiaomi and TCL smart TVs. The project addresses the specific pain point of "junkware" and mandatory advertising in domestic Chinese television operating systems by providing a clean, streamlined desktop environment. It is currently trending on GitHub due to its utility for users seeking a privacy-respecting and performance-oriented alternative to proprietary TV skins.

**Technical Architecture and Implementation**
*   **Design Language:** The interface is explicitly modeled after **tvOS** (Apple’s operating system for the Apple TV), utilizing its distinct visual hierarchy, card-based navigation, and smooth transition animations to provide a familiar and modern user experience on Android-based hardware.
*   **Boot-time Interception:** The core technical mechanism involves **automatic boot-time takeover**. This requires the application to hold specific permissions or use accessibility services to register as the default home intent handler immediately upon system startup, bypassing the manufacturer's default launcher before the standard ad-injecting interface can render.
*   **Ad-Free Environment:** By replacing the OEM launcher, the project effectively removes the software layer responsible for injecting third-party advertisements and tracking beacons, resulting in a "clean" desktop environment without commercial overlays.
*   **Target Hardware Specifics:** The codebase is optimized for the Android variants used in Chinese smart TVs (often based on Android 8.0 to Android 11/12 kernels with proprietary overlays like Mi TV OS or HiHome), ensuring compatibility with specific IR (infrared) and Bluetooth remote control protocols common in these regions.

**Why This Matters to Developers and Users**
*   **System-level Customization Insight:** Developers studying custom ROMs or launcher replacements can analyze how Aerial-TV handles intent filters, boot receivers, and permission persistence on locked-down TV operating systems.
*   **Performance Optimization:** By stripping away the resource-heavy manufacturer skins (which often consume significant RAM and CPU for background ad services), users observe measurable improvements in UI responsiveness and app launch times.
*   **Privacy Control:** It serves as a concrete case study for user-driven privacy enforcement on IoT devices, demonstrating how open-source software can mitigate the tracking capabilities embedded in consumer electronics firmware.
*   **Cross-Platform Design Patterns:** For UI/UX engineers, the project offers a practical implementation of Apple’s human interface guidelines on an Android platform, showcasing how to replicate high-polish navigation logic using standard Android View components or Compose.

**Key Constraints and Considerations**
*   **Regional Lock:** The solution is tailored for Chinese market models (Xiaomi, TCL, etc.) and may not apply to Western-market TVs (e.g., LG webOS, Samsung Tizen, or Western Android TV builds) due to different base OS architectures and OEM lock-downs.
*   **Security Implications:** The "boot-time takeover" functionality requires elevated permissions. Users must trust the open-source code, as a malicious variant could potentially compromise the TV’s network or data access.

Source: https://github.com/pengchujin/aerial-tv