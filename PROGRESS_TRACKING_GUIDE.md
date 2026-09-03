# Video Download Progress Tracking Guide

## Backend Changes ✅
The backend now provides real-time progress updates. Changes made:

1. **Enhanced Logging** - Backend terminal will show:
   ```
   [project_id] Download: 45.2% | 150MB/320MB | Speed: 1.2M/s | ETA: 02:34
   [project_id] Video downloaded successfully: /path/to/file (320MB)
   [project_id] Starting S3 upload to clipnera-videos...
   [project_id] S3 upload completed, generating presigned URL...
   ```

2. **Progress API Endpoint**
   - **Endpoint**: `GET /api/v1/clips/progress/{project_id}`
   - **Response**:
   ```json
   {
     "status": "downloading",
     "percent": 45.2,
     "total": "320MB",
     "speed": "1.2M/s",
     "eta": "02:34"
   }
   ```

## Frontend Implementation

### 1. Modify Download Component
When user clicks download, capture the `project_id` from the response:

```typescript
// Example: DashboardApp.tsx or ClipGeneratorView.tsx
const handleDownload = async (url: string) => {
  try {
    const response = await api.post('/clips/download', { url });
    const projectId = response.data.id;  // Capture project ID
    
    // Start polling progress
    startProgressPolling(projectId);
  } catch (error) {
    console.error('Download failed:', error);
  }
};
```

### 2. Create Progress Polling Hook
Create a new hook: `hooks/useDownloadProgress.ts`

```typescript
import { useState, useEffect, useRef } from 'react';
import { api } from '@/lib/api';

interface DownloadProgress {
  status: 'idle' | 'downloading' | 'uploading' | 'done' | 'error';
  percent: number;
  total: string | null;
  speed: string | null;
  eta: string | null;
}

export function useDownloadProgress(projectId: string | null) {
  const [progress, setProgress] = useState<DownloadProgress>({
    status: 'idle',
    percent: 0,
    total: null,
    speed: null,
    eta: null,
  });
  
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (!projectId) {
      if (intervalRef.current) clearInterval(intervalRef.current);
      return;
    }

    const pollProgress = async () => {
      try {
        const response = await api.get(`/clips/progress/${projectId}`);
        setProgress(response.data);
        
        // Stop polling when done
        if (response.data.status === 'done' || response.data.status === 'error') {
          if (intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
          }
        }
      } catch (error) {
        console.error('Failed to fetch progress:', error);
      }
    };

    // Start polling immediately, then every 500ms
    pollProgress();
    intervalRef.current = setInterval(pollProgress, 500);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [projectId]);

  return progress;
}
```

### 3. Update UI Component
Use the hook in your component:

```typescript
import { useDownloadProgress } from '@/hooks/useDownloadProgress';

export function ClipGeneratorView() {
  const [projectId, setProjectId] = useState<string | null>(null);
  const progress = useDownloadProgress(projectId);

  const handleDownload = async (url: string) => {
    try {
      const response = await api.post('/clips/download', { url });
      setProjectId(response.data.id);  // Start progress tracking
    } catch (error) {
      console.error('Download failed:', error);
    }
  };

  return (
    <div>
      {/* ... existing UI ... */}
      
      {projectId && (
        <div className="progress-container">
          <h3>Downloading Video...</h3>
          <div className="progress-bar">
            <div 
              className="progress-fill" 
              style={{ width: `${progress.percent}%` }}
            >
              {progress.percent.toFixed(1)}%
            </div>
          </div>
          <p className="progress-status">
            Status: {progress.status.toUpperCase()}
          </p>
          <p className="progress-details">
            {progress.total} | Speed: {progress.speed || '—'} | ETA: {progress.eta || '—'}
          </p>
        </div>
      )}
    </div>
  );
}
```

### 4. Add CSS Styling (tailwind)
```css
.progress-container {
  @apply mt-4 p-4 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg border border-blue-200;
}

.progress-bar {
  @apply w-full h-8 bg-gray-200 rounded-full overflow-hidden my-2;
}

.progress-fill {
  @apply h-full bg-gradient-to-r from-blue-500 to-indigo-600 flex items-center justify-center text-white text-sm font-semibold transition-all duration-300;
}

.progress-status {
  @apply text-sm font-medium text-gray-700 mt-2;
}

.progress-details {
  @apply text-xs text-gray-600 mt-1;
}
```

## Testing Checklist

- [ ] Start a download and see progress in browser console
- [ ] Verify backend terminal shows download logs with percentage
- [ ] Check progress bar updates every 500-1000ms
- [ ] Verify ETA and speed display
- [ ] Test with different video lengths
- [ ] Verify "uploading" status displays during S3 upload
- [ ] Confirm progress stops when download completes

## Notes

- The backend clears progress after download completes, so the endpoint will return `idle` status
- If you need progress persistence, modify `YouTubeService.clear_progress()` to keep history
- Polling is more reliable than WebSockets for this use case
- Adjust poll interval (500ms) based on your performance needs
