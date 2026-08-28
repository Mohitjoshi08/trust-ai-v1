# Stitch Prompt: Trace.ai Dashboard

Copy and paste the following prompt into your UI generator (Stitch, v0, etc.):

```markdown
Build a premium, highly aesthetic, light-themed React dashboard for an enterprise AI tool called "Trace.ai". This tool is a "Causal Engine" that automatically detects anomalies in business metrics, decomposes the drop into specific segments, and uses an LLM to read operational logs and generate root-cause hypotheses.

I want you to have full creative freedom to design the most beautiful, modern, and intuitive user interface possible. Make it look like a state-of-the-art SaaS product.

**Core Data & Requirements:**
The dashboard needs to display the following information seamlessly. Feel free to structure, layout, and visualize this however you think works best:

1. **Multiple Anomalies Navigation:**
   - The system detects multiple anomalies across a timeline. The user needs a way to select or switch between them.
   - Example anomalies: "Stripe SDK Deployment Failure" (65% drop, high severity), "Web CDN Outage", "EMEA Payment Gateway Down".

2. **Time-Series Metric Chart:**
   - A visual representation (chart placeholder) showing the "Actual" metric dropping below the "Expected" baseline, highlighting the anomaly window in time.

3. **Deterministic Decomposition:**
   - The mathematical breakdown of *where* the drop occurred. 
   - Needs to show the "Primary Driver" (e.g., `device = iOS` dropped by 50%, contributing to 100% of the overall anomaly).
   - Needs to show a drill-down path (e.g., `revenue > device=iOS`).

4. **AI Causal Hypothesis:**
   - The LLM's conclusion based on reading logs.
   - Includes a Confidence Score (e.g., 92%).
   - Includes the Hypothesis Title (e.g., "Stripe SDK Deployment Failure") and a short paragraph of reasoning.
   - Includes the "Recommended Action" (e.g., "Rollback Stripe SDK to previous version").

5. **Supporting Evidence (Logs):**
   - The specific operational logs the AI used to form its hypothesis.
   - Example logs: A GitHub PR merged, a Zendesk ticket about a crash, a Slack message about an incident.

**Aesthetic Guidelines:**
- Use a stunning, clean, light theme.
- Focus on excellent typography, whitespace, and visual hierarchy.
- Use subtle, polished UI touches (e.g., soft shadows, delicate borders, elegant badges for severity or log sources).
- Use Lucide React icons.
- Ensure the layout is responsive and airy. Let your design skills shine!
```
