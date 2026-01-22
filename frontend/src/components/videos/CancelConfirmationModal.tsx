"use client";

import { useState } from "react";
import { Video, CleanupOption } from "@/lib/types";
import { AlertTriangle, Loader2, X, StopCircle, AlertCircle } from "lucide-react";

interface CancelConfirmationModalProps {
  videos: Video[];
  onConfirm: (cleanupOption: CleanupOption) => Promise<void>;
  onCancel: () => void;
  isLoading: boolean;
}

export function CancelConfirmationModal({
  videos,
  onConfirm,
  onCancel,
  isLoading,
}: CancelConfirmationModalProps) {
  const [cleanupOption, setCleanupOption] = useState<CleanupOption>("keep_video");

  const handleConfirm = () => {
    onConfirm(cleanupOption);
  };

  // Get status breakdown
  const statusCounts = videos.reduce(
    (acc, video) => {
      acc[video.status] = (acc[video.status] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>
  );

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-lg max-w-lg w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 sticky top-0 bg-white">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-orange-100 rounded-full">
              <StopCircle className="w-5 h-5 text-orange-600" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-gray-900">
                Stop Processing {videos.length} Video{videos.length !== 1 ? "s" : ""}?
              </h2>
              <p className="text-sm text-gray-500">
                This will stop the pipeline and clean up partial data
              </p>
            </div>
          </div>
          <button
            onClick={onCancel}
            disabled={isLoading}
            className="text-gray-400 hover:text-gray-600 disabled:opacity-50"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-6">
          {/* Status Summary */}
          <div>
            <h3 className="text-sm font-semibold text-gray-900 mb-3">
              Processing Status
            </h3>
            <div className="rounded-lg bg-gray-50 p-4 space-y-2 text-sm">
              {Object.entries(statusCounts).map(([status, count]) => (
                <div key={status} className="flex justify-between">
                  <span className="text-gray-600 capitalize">{status}:</span>
                  <span className="font-medium text-gray-900">{count}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Videos List */}
          <div>
            <h3 className="text-sm font-semibold text-gray-900 mb-3">
              Selected Videos
            </h3>
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {videos.map((video) => (
                <div
                  key={video.id}
                  className="flex items-center justify-between text-sm p-3 bg-gray-50 rounded"
                >
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-gray-900 truncate">
                      {video.title}
                    </p>
                    <p className="text-xs text-gray-500 capitalize">
                      Status: {video.status}
                      {video.progress_percent !== undefined &&
                        video.progress_percent > 0 &&
                        ` (${Math.round(video.progress_percent)}%)`}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Cleanup Options */}
          <div>
            <h3 className="text-sm font-semibold text-gray-900 mb-3">
              What to do with the video entry?
            </h3>
            <div className="space-y-3">
              {/* Keep Video Option */}
              <label className="flex items-start space-x-3 cursor-pointer p-3 border rounded-lg hover:bg-gray-50 transition-colors">
                <input
                  type="radio"
                  name="cleanup_option"
                  value="keep_video"
                  checked={cleanupOption === "keep_video"}
                  onChange={() => setCleanupOption("keep_video")}
                  disabled={isLoading}
                  className="mt-1 h-4 w-4 text-orange-600 border-gray-300 focus:ring-orange-500"
                />
                <div className="flex-1">
                  <p className="font-medium text-gray-900 text-sm">
                    Keep in library (Recommended)
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    Video stays in your library with &quot;canceled&quot; status.
                    You can reprocess it later without re-entering the URL.
                  </p>
                </div>
              </label>

              {/* Full Delete Option */}
              <label className="flex items-start space-x-3 cursor-pointer p-3 border rounded-lg hover:bg-gray-50 transition-colors">
                <input
                  type="radio"
                  name="cleanup_option"
                  value="full_delete"
                  checked={cleanupOption === "full_delete"}
                  onChange={() => setCleanupOption("full_delete")}
                  disabled={isLoading}
                  className="mt-1 h-4 w-4 text-orange-600 border-gray-300 focus:ring-orange-500"
                />
                <div className="flex-1">
                  <p className="font-medium text-gray-900 text-sm">
                    Remove from library
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    Delete the video entry completely. You&apos;ll need to
                    re-ingest the YouTube URL to process it again.
                  </p>
                </div>
              </label>
            </div>
          </div>

          {/* What Gets Cleaned Up */}
          <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
            <h4 className="text-sm font-semibold text-orange-800 mb-2">
              What gets cleaned up:
            </h4>
            <ul className="text-sm text-orange-700 space-y-1 list-disc list-inside">
              <li>Active Celery tasks will be revoked</li>
              <li>Partial audio files will be deleted</li>
              <li>Partial transcript files will be deleted</li>
              <li>Chunks in database will be removed</li>
              <li>Vectors in search index will be removed</li>
            </ul>
          </div>

          {/* Warning */}
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 flex gap-3">
            <AlertTriangle className="w-5 h-5 text-yellow-600 flex-shrink-0 mt-0.5" />
            <div className="text-sm text-yellow-800">
              <p className="font-semibold mb-1">
                In-flight tasks may take a moment to stop.
              </p>
              <p>
                If a task is in the middle of processing, it will stop at the next
                checkpoint. This is designed to prevent data corruption.
              </p>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-3 p-6 border-t border-gray-200 sticky bottom-0 bg-gray-50">
          <button
            onClick={onCancel}
            disabled={isLoading}
            className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-600 bg-white hover:bg-gray-100 hover:text-gray-700 transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-300 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Go Back
          </button>
          <button
            onClick={handleConfirm}
            disabled={isLoading}
            style={{
              backgroundColor: isLoading ? '#991b1b' : '#dc2626',
              color: 'white',
              padding: '10px 24px',
              borderRadius: '6px',
              border: 'none',
              fontSize: '14px',
              fontWeight: '600',
              cursor: isLoading ? 'not-allowed' : 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px',
              transition: 'all 150ms',
              boxShadow: '0 4px 12px rgba(220, 38, 38, 0.4)',
              opacity: isLoading ? 0.7 : 1,
              transform: 'scale(1)',
            }}
            onMouseEnter={(e) => {
              if (!isLoading) {
                (e.target as HTMLButtonElement).style.backgroundColor = '#b91c1c';
                (e.target as HTMLButtonElement).style.boxShadow = '0 8px 20px rgba(220, 38, 38, 0.6)';
                (e.target as HTMLButtonElement).style.transform = 'scale(1.05)';
              }
            }}
            onMouseLeave={(e) => {
              if (!isLoading) {
                (e.target as HTMLButtonElement).style.backgroundColor = '#dc2626';
                (e.target as HTMLButtonElement).style.boxShadow = '0 4px 12px rgba(220, 38, 38, 0.4)';
                (e.target as HTMLButtonElement).style.transform = 'scale(1)';
              }
            }}
          >
            {isLoading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Stopping...
              </>
            ) : (
              <>
                <AlertCircle className="w-4 h-4" />
                Stop Processing
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
