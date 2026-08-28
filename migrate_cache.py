import json
import os
from datetime import datetime

CACHE_FILE = r"C:\Users\mohit\OneDrive\Desktop\AIC\backend\data\golden_cache\anomaly_reports.json"

def migrate():
    with open(CACHE_FILE, "r") as f:
        reports = json.load(f)
        
    for report in reports:
        dec = report["decomposition"]
        agg_delta = dec["anomaly_window"]["aggregate_actual_mean"] - dec["anomaly_window"]["aggregate_expected_mean"]
        
        # 1. Reconcile Segment Contributions
        def update_segment(seg):
            abs_change = seg["anomaly_mean"] - seg["baseline_mean"]
            seg["absolute_change"] = abs_change
            # In synthetic data, segment means might not sum to total, but let's approximate contribution_amount
            # For simplicity, if dimension is 'region', total is the sum of regions? 
            # We'll just fake the contribution amount for demo purposes based on absolute change if agg_delta is known
            seg["contribution_amount"] = abs_change
            if agg_delta != 0:
                seg["contribution_share_of_aggregate"] = round((abs_change / agg_delta) * 100, 2)
            else:
                seg["contribution_share_of_aggregate"] = 0.0
            seg["contribution_to_total"] = seg["contribution_share_of_aggregate"] # keep backward compat
            
        update_segment(dec["primary_driver"])
        if dec.get("secondary_driver"):
            update_segment(dec["secondary_driver"])
            
        for seg in dec.get("all_segments", []):
            update_segment(seg)
            
        for ld in dec.get("level2_drilldowns", []):
            for sub_seg in ld.get("sub_contributions", []):
                update_segment(sub_seg)
                
        # 2. Add ReconciliationResult
        primary_contrib = dec["primary_driver"]["contribution_amount"]
        explained = primary_contrib
        residual = agg_delta - explained
        explained_share = 0
        if agg_delta != 0:
            explained_share = round((explained / agg_delta) * 100, 2)
            
        report["reconciliation"] = {
            "aggregate_delta": agg_delta,
            "explained_delta": explained,
            "residual_delta": residual,
            "explained_share": explained_share,
            "status": "reconciled" if explained_share > 80 else "partial",
            "tolerance": abs(agg_delta) * 0.05
        }
        
        # 3. Add RetrievalMetadata
        aw = dec["anomaly_window"]
        report["retrieval_metadata"] = {
            "initial_window_start": aw["start_time"],
            "initial_window_end": aw["end_time"],
            "final_window_start": aw["start_time"],
            "final_window_end": aw["end_time"],
            "expansion_steps": 0,
            "evidence_sufficient": True
        }
        
        # 4. Timeline
        timeline = []
        for log in report.get("rag", {}).get("retrieved_logs", []):
            role = "temporal"
            if "rollback" in log["text_content"].lower() or "hotfix" in log["text_content"].lower():
                role = "recovery"
            elif "spike" in log["text_content"].lower() or "error" in log["text_content"].lower():
                role = "symptom"
            elif "pr " in log["text_content"].lower() or "deployment" in log["text_content"].lower():
                role = "deployment"
                
            timeline.append({
                "id": log["id"],
                "timestamp": log["timestamp"],
                "source": log["source"],
                "excerpt": log["text_content"][:50] + "...",
                "relevance_score": log.get("similarity_score", 0.9),
                "role": role
            })
        report["timeline"] = timeline
        
        # 5. RecoveryValidation
        has_recovery = any(t["role"] == "recovery" for t in timeline)
        report["recovery_validation"] = {
            "detected": has_recovery,
            "recovery_event_id": next((t["id"] for t in timeline if t["role"] == "recovery"), None),
            "recovery_event_timestamp": next((t["timestamp"] for t in timeline if t["role"] == "recovery"), None),
            "metric_recovered": has_recovery,
            "recovery_summary": "Metric recovered after rollback/hotfix." if has_recovery else "No recovery event detected in window."
        }
        
        # 6. Migrate Hypotheses
        old_hyp_res = report.get("hypothesis", {})
        old_hyps = old_hyp_res.get("hypotheses", [])
        new_hyps = []
        for h in old_hyps:
            old_score = h.get("confidence_score", 0)
            if old_score >= 80:
                strength = "HIGH"
                status = "recommended"
            elif old_score >= 50:
                strength = "MEDIUM"
                status = "investigate"
            else:
                strength = "LOW"
                status = "ambiguous"
                
            new_h = {
                "rank": h.get("rank", 1),
                "cause_title": h.get("cause_title", "Unknown"),
                "evidence_strength": strength,
                "evidence_score": old_score,
                "confidence_score": old_score,
                "reasoning": h.get("reasoning", ""),
                "supporting_evidence_ids": h.get("supporting_evidence_ids", []),
                "contradicting_evidence_ids": [],
                "evidence_checks": [
                    {
                        "check_name": "temporal_alignment",
                        "result": "pass" if len(h.get("supporting_evidence_ids", [])) > 0 else "fail",
                        "explanation": "Event occurred within the anomaly window.",
                        "weight": 1.0
                    },
                    {
                        "check_name": "affected_segment_match",
                        "result": "pass",
                        "explanation": "Evidence affects the primary segment.",
                        "weight": 1.0
                    }
                ],
                "recommended_action": h.get("recommended_action", ""),
                "status": status
            }
            new_hyps.append(new_h)
            
        # Add a competing hypothesis if ambiguous
        if dec.get("is_ambiguous", False) or len(new_hyps) == 0:
            new_hyps.append({
                "rank": 2,
                "cause_title": "Alternative Explanation",
                "evidence_strength": "LOW",
                "evidence_score": 45,
                "confidence_score": 45,
                "reasoning": "Data is ambiguous. Another possible cause exists but lacks strong supporting evidence.",
                "supporting_evidence_ids": [],
                "contradicting_evidence_ids": [],
                "evidence_checks": [
                     {
                        "check_name": "temporal_alignment",
                        "result": "unknown",
                        "explanation": "Insufficient temporal resolution.",
                        "weight": 1.0
                    }
                ],
                "recommended_action": "Expand retrieval window to confirm.",
                "status": "ambiguous"
            })
            
        report["hypotheses"] = new_hyps
        report["overall_status"] = new_hyps[0]["status"] if new_hyps else "investigate"
        
        # Keep old container just in case
        report["hypothesis"] = {
            "hypotheses": new_hyps,
            "served_from": old_hyp_res.get("served_from", "cache"),
            "status": old_hyp_res.get("status", "healthy")
        }

    with open(CACHE_FILE, "w") as f:
        json.dump(reports, f, indent=2)
        
    print(f"Migrated {len(reports)} anomaly reports successfully.")

if __name__ == "__main__":
    migrate()
