import { useState } from 'react';
import { Upload as UploadIcon, CheckCircle, Database, Menu } from 'lucide-react';
import { auth } from '../firebase';
import { Sidebar } from '../components/Sidebar';

export default function Upload() {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [columns, setColumns] = useState<string[]>([]);
  const [datasetId, setDatasetId] = useState('');
  const [mapping, setMapping] = useState({
    timestamp_col: '',
    metric_col: '',
    dimension_cols: [] as string[]
  });
  const [success, setSuccess] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const token = import.meta.env.VITE_DEMO_MODE === 'true' ? 'demo' : await auth.currentUser?.getIdToken();
      const headers: Record<string, string> = token ? { 'Authorization': `Bearer ${token}` } : {};

      const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
      const res = await fetch(`${API_BASE_URL}/api/v1/datasets/upload`, {
        method: 'POST',
        headers,
        body: formData
      });

      if (!res.ok) throw new Error('Upload failed');
      
      const data = await res.json();
      setColumns(data.columns);
      setDatasetId(data.dataset_id);
    } catch (err) {
      console.error(err);
      alert('Failed to upload ZIP file. Ensure it contains metrics.csv and logs.json.');
    } finally {
      setUploading(false);
    }
  };

  const handleSaveMapping = async () => {
    try {
      const token = import.meta.env.VITE_DEMO_MODE === 'true' ? 'demo' : await auth.currentUser?.getIdToken();
      const headers: Record<string, string> = token ? { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' } : { 'Content-Type': 'application/json' };

      const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
      const res = await fetch(`${API_BASE_URL}/api/v1/datasets/${datasetId}/map`, {
        method: 'POST',
        headers,
        body: JSON.stringify(mapping)
      });

      if (!res.ok) throw new Error('Failed to save mapping');
      setSuccess(true);
    } catch (err) {
      console.error(err);
      alert('Failed to save column mapping');
    }
  };

  return (
    <div className="app-layout">
      <Sidebar open={sidebarOpen} setOpen={setSidebarOpen} />
      
      <div className="dashboard-content" style={{ padding: '32px', maxWidth: '800px', margin: '0 auto', width: '100%' }}>
        <div className="flex items-center gap-4 mb-6">
          <button className="btn-icon" onClick={() => setSidebarOpen(true)}>
            <Menu size={18} />
          </button>
          <Database size={24} color="var(--primary)" />
          <h1 className="headline-md">Data Sources</h1>
        </div>

      {!columns.length ? (
        <div className="card" style={{ textAlign: 'center', padding: '48px' }}>
          <UploadIcon size={48} color="var(--outline)" style={{ margin: '0 auto 16px' }} />
          <h2 className="title-lg">Upload Dataset</h2>
          <p className="text-muted body-md mt-2 mb-6">Upload your metric & log ZIP file (.zip containing metrics.csv and logs.json)</p>
          
          <input 
            type="file" 
            accept=".zip" 
            onChange={handleFileChange}
            id="file-upload"
            style={{ display: 'none' }}
          />
          <div className="flex justify-center gap-4">
            <label htmlFor="file-upload" className="btn" style={{ cursor: 'pointer' }}>
              Choose File
            </label>
            <button 
              className="btn btn-primary" 
              onClick={handleUpload}
              disabled={!file || uploading}
            >
              {uploading ? 'Uploading...' : 'Upload & Parse'}
            </button>
          </div>
          {file && <p className="body-md mt-4">{file.name}</p>}
        </div>
      ) : !success ? (
        <div className="card">
          <h2 className="title-lg mb-4">Map Columns</h2>
          <p className="text-muted body-md mb-6">Map your metrics.csv columns to Trace.ai's required fields.</p>
          
          <div className="flex flex-col gap-4">
            <div>
              <label className="label-md">Timestamp Column</label>
              <select 
                className="mt-1"
                style={{ width: '100%', padding: '10px', borderRadius: 'var(--radius-md)', background: 'var(--surface-container-lowest)' }}
                value={mapping.timestamp_col}
                onChange={e => setMapping({...mapping, timestamp_col: e.target.value})}
              >
                <option value="">Select column...</option>
                {columns.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>

            <div>
              <label className="label-md">Target Metric Column</label>
              <select 
                className="mt-1"
                style={{ width: '100%', padding: '10px', borderRadius: 'var(--radius-md)', background: 'var(--surface-container-lowest)' }}
                value={mapping.metric_col}
                onChange={e => setMapping({...mapping, metric_col: e.target.value})}
              >
                <option value="">Select column...</option>
                {columns.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>

            <div>
              <label className="label-md">Dimension Columns</label>
              <select 
                multiple
                className="mt-1"
                style={{ width: '100%', padding: '10px', borderRadius: 'var(--radius-md)', background: 'var(--surface-container-lowest)', minHeight: '100px' }}
                value={mapping.dimension_cols}
                onChange={e => setMapping({
                  ...mapping, 
                  dimension_cols: Array.from(e.target.selectedOptions, option => option.value)
                })}
              >
                {columns.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
              <p className="text-muted" style={{ fontSize: '11px', marginTop: '4px' }}>Hold Ctrl/Cmd to select multiple dimensions.</p>
            </div>

            <button 
              className="btn btn-primary mt-4" 
              onClick={handleSaveMapping}
              disabled={!mapping.timestamp_col || !mapping.metric_col}
            >
              Save Configuration
            </button>
          </div>
        </div>
      ) : (
        <div className="card" style={{ textAlign: 'center', padding: '48px' }}>
          <CheckCircle size={48} color="var(--success)" style={{ margin: '0 auto 16px' }} />
          <h2 className="title-lg">Dataset Ready</h2>
          <p className="text-muted body-md mt-2 mb-6">Your data has been mapped successfully and is ready for analysis.</p>
          <button className="btn btn-primary" onClick={() => window.location.href = '/'}>
            Go to Dashboard
          </button>
        </div>
      )}
    </div>
  </div>
  );
}
