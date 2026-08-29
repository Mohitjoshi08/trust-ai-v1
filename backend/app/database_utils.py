import uuid
import json
from sqlalchemy.orm import Session
from app.models.schemas import AnomalyReport
from app.models.db_models import AnomalyReportModel, HypothesisModel, EvidenceModel

def save_anomaly_report_to_db(db: Session, dataset_id: str, report: AnomalyReport):
    report_id = str(uuid.uuid4())
    
    # Save parent AnomalyReportModel
    db_report = AnomalyReportModel(
        id=report_id,
        dataset_id=dataset_id,
        anomaly_start=report.anomaly_window.start_time,
        anomaly_end=report.anomaly_window.end_time,
        metric_name=report.anomaly_window.metric_name,
        severity=report.anomaly_window.severity,
        recovered=report.recovered,
        raw_decomposition=json.loads(report.decomposition.json()),
        raw_rag=json.loads(report.rag.json()),
        rejected_logs=[json.loads(rl.json()) for rl in (report.rejected_logs or [])]
    )
    db.add(db_report)
    
    # Save Hypotheses
    for hyp in report.hypotheses:
        db_hyp = HypothesisModel(
            id=hyp.id,
            report_id=report_id,
            rank=hyp.rank,
            title=hyp.title,
            description=hyp.description,
            evidence_strength=hyp.evidence_strength.value,
            analyst_feedback=hyp.analyst_feedback
        )
        db.add(db_hyp)
        
        # Save Evidence
        for ev in hyp.evidence_matrix:
            db_ev = EvidenceModel(
                id=ev.id,
                hypothesis_id=hyp.id,
                log_id=ev.log_id,
                checkpoint=ev.checkpoint,
                status=ev.status.value,
                timestamp=ev.timestamp,
                details=ev.details
            )
            db.add(db_ev)
            
    db.commit()
    return report_id
