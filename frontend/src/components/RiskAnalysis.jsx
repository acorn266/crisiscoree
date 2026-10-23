import React from 'react';

function severityTone(severity) {
  if (!severity) return 'unavailable';
  const s = severity.toUpperCase();
  if (['HIGH', 'EXTREME', 'ELEVATED', 'CRITICAL', 'ELEVATED_STRESS'].includes(s)) return 'high';
  if (['MEDIUM', 'MODERATE', 'MONITOR', 'PARTIAL'].includes(s)) return 'medium';
  if (['LOW', 'NONE'].includes(s)) return 'low';
  return 'unavailable';
}

function getDisasterTitle(name, model, method) {
  if (name === "Flood") {
    return `AI Flood Risk — ${model || 'Isolation Forest'}`;
  }
  if (name === "Earthquake") {
    return `Earthquake Event Risk — ${model || 'Isolation Forest'}`;
  }
  if (name === "Heatwave") {
    return `AI Heat Risk — ${method === 'supervised_ml' ? 'Supervised ML' : 'ML/Anomaly Detection'}`;
  }
  if (name === "Drought") {
    return `Drought Risk — ${model || 'Isolation Forest'}`;
  }
  if (name === "Cyclone") {
    return `Cyclone Condition Risk — ${model || 'Isolation Forest'}`;
  }
  return name;
}

function RiskRow({ name, category }) {
  // If the category is not available or data limited
  const isAvailable = category && category.available !== false && category.score !== null;
  const severity = category?.level ?? 'DATA_LIMITED';
  const tone = severityTone(severity);
  const score = category?.score;
  const model = category?.model ?? 'Isolation Forest';
  const method = category?.method ?? 'anomaly_detection';
  const confidence = category?.confidence;
  const factors = category?.factors ?? [];

  const displayTitle = getDisasterTitle(name, model, method);

  return (
    <div className="risk-item" style={{ borderBottom: '1px solid #222', paddingBottom: '12px', marginBottom: '12px' }}>
      <div className="risk-info" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontWeight: '500' }}>{displayTitle}</span>
        <strong className={tone} style={{ padding: '2px 6px', borderRadius: '4px', fontSize: '0.85rem' }}>
          {isAvailable ? severity : 'DATA LIMITED'}
        </strong>
      </div>
      
      {isAvailable ? (
        <>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginTop: '6px' }}>
            <div className="progress-track" style={{ flexGrow: 1, height: '6px', backgroundColor: '#222', borderRadius: '3px', overflow: 'hidden' }}>
              <div className={`progress-bar ${tone}`} style={{ height: '100%', width: `${Math.min(score, 100)}%` }} />
            </div>
            <span className="risk-score" style={{ fontWeight: '600', minWidth: '40px', textAlign: 'right' }}>{score}%</span>
          </div>
          
          <div style={{ display: 'flex', gap: '12px', fontSize: '0.75rem', color: '#8c9ba5', marginTop: '4px' }}>
            <span>Method: {method === 'supervised_ml' ? 'Supervised' : 'Anomaly Detection'}</span>
            <span>Confidence: {confidence ? `${Math.round(confidence * 100)}%` : 'N/A'}</span>
          </div>

          {factors.length > 0 && (
            <div style={{ fontSize: '0.75rem', color: '#b9c6cf', marginTop: '4px', paddingLeft: '8px', borderLeft: '2px solid #555' }}>
              <strong>Why?</strong> {factors.join(', ')}
            </div>
          )}
        </>
      ) : (
        <div className="risk-no-score" style={{ fontSize: '0.8rem', color: '#5b6973', marginTop: '6px', fontStyle: 'italic' }}>
          — Data limited. {name === 'Drought' ? 'Limited by absence of long-term drought baseline.' : 'Insufficient features for anomaly detection.'}
        </div>
      )}
    </div>
  );
}

function RiskAnalysis({ risk, loading }) {
  const overall = risk?.overall ?? { level: 'DATA_LIMITED', score: null };
  const risks = risk?.risks ?? {};
  
  // Backwards compatibility with raw backend/risk schema
  const floodCat = risks.flood ?? risk?.flood;
  const earthquakeCat = risks.earthquake ?? risk?.earthquake;
  const droughtCat = risks.drought ?? risk?.drought;
  const heatwaveCat = risks.heatwave ?? risk?.heatwave;
  const cycloneCat = risks.cyclone ?? risk?.cyclone;

  const overallScore = overall.score;
  const overallLevel = overall.level ?? 'UNAVAILABLE';
  const overallTone = severityTone(overallLevel);

  return (
    <aside className="card risk-analysis-panel" style={{ display: 'flex', flexDirection: 'column' }}>
      <div className="section-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #333', paddingBottom: '10px', marginBottom: '15px' }}>
        <h2>RISK ANALYSIS</h2>
        <span className="ai-badge" style={{ backgroundColor: '#10b981', color: '#fff', fontSize: '0.75rem', padding: '2px 8px', borderRadius: '10px', fontWeight: 'bold' }}>AI Engine Active</span>
      </div>

      {loading ? (
        <p className="panel-note">Loading localized AI risk profiles...</p>
      ) : (
        <>
          <div style={{ flexGrow: 1 }}>
            <RiskRow name="Flood" category={floodCat} />
            <RiskRow name="Earthquake" category={earthquakeCat} />
            <RiskRow name="Heatwave" category={heatwaveCat} />
            <RiskRow name="Drought" category={droughtCat} />
            <RiskRow name="Cyclone" category={cycloneCat} />
          </div>

          <div className="overall-risk-row" style={{ borderTop: '2px solid #333', paddingTop: '15px', marginTop: '10px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <span style={{ fontWeight: 'bold', fontSize: '1.1rem' }}>Overall AI Risk Score</span>
              <strong className={overallTone} style={{ fontSize: '1.1rem', textTransform: 'uppercase' }}>
                {overallScore !== null ? `${overallLevel} (${overallScore}%)` : 'DATA LIMITED'}
              </strong>
            </div>
            
            {overallScore !== null && (
              <div className="progress-track" style={{ height: '8px', backgroundColor: '#222', borderRadius: '4px', overflow: 'hidden', marginBottom: '12px' }}>
                <div className={`progress-bar ${overallTone}`} style={{ height: '100%', width: `${Math.min(overallScore, 100)}%` }} />
              </div>
            )}
          </div>
        </>
      )}

      <div style={{ borderTop: '1px solid #222', paddingTop: '8px', marginTop: '8px', display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: '#5b6973' }}>
        <span>AI Engine: CrisisCore AI Risk Engine v1.0</span>
        <span>Confidence: {overall.confidence ? `${Math.round(overall.confidence * 100)}%` : '--'}</span>
      </div>
    </aside>
  );
}

export default RiskAnalysis;
