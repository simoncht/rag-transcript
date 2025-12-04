"use client";

import { useState } from "react";
import { Video, VideoDeleteBreakdown } from "@/lib/types";
import { AlertTriangle, Loader2, X } from "lucide-react";

interface DeleteConfirmationModalProps {
  videos: Video[];
  onConfirm: (options: {
    removeFromLibrary: boolean;
    deleteSearchIndex: boolean;
    deleteAudio: boolean;
    deleteTranscript: boolean;
  }) => Promise<void>;
  onCancel: () => void;
  isLoading: boolean;
}

export function DeleteConfirmationModal({
  videos,
  onConfirm,
  onCancel,
  isLoading,
}: DeleteConfirmationModalProps) {
  const [removeFromLibrary, setRemoveFromLibrary] = useState(true);
  const [deleteSearchIndex, setDeleteSearchIndex] = useState(true);
  const [deleteAudio, setDeleteAudio] = useState(true);
  const [deleteTranscript, setDeleteTranscript] = useState(true);

  // Calculate totals
  const calculateBreakdown = () => {
    let totalAudio = 0;
    let totalTranscript = 0;
    let totalIndex = 0;

    videos.forEach((video) => {
      totalAudio += video.audio_file_size_mb || 0;
      totalTranscript += video.transcript_size_mb || 0;
      // Estimate index size (~3.3 KB per chunk)
      if (video.tags) {
        // Using a rough estimate since we don't have chunk count in Video type
        totalIndex += (video.storage_total_mb || 0) * 0.15; // Estimate 15% of total for index
      }
    });

    return {
      audio: Math.round(totalAudio * 1000) / 1000,
      transcript: Math.round(totalTranscript * 1000) / 1000,
      index: Math.round(totalIndex * 1000) / 1000,
    };
  };

  const breakdown = calculateBreakdown();
  const totalSavings =
    (deleteAudio ? breakdown.audio : 0) +
    (deleteTranscript ? breakdown.transcript : 0) +
    (deleteSearchIndex ? breakdown.index : 0);

  const handleConfirm = () => {
    onConfirm({
      removeFromLibrary,
      deleteSearchIndex,
      deleteAudio,
      deleteTranscript,
    });
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 sticky top-0 bg-white">
          <h2 className="text-lg font-semibold text-gray-900">
            Delete {videos.length} Video{videos.length !== 1 ? "s" : ""}
          </h2>
          <button
            onClick={onCancel}
            disabled={isLoading}
            className="text-gray-400 hover:text-gray-600 disabled:opacity-50"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-6">
          {/* Storage Breakdown */}
          <div>
            <h3 className="text-sm font-semibold text-gray-900 mb-3">
              Storage Breakdown
            </h3>
            <div className="rounded-lg bg-gray-50 p-4 space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-600">Audio files:</span>
                <span className="font-medium text-gray-900">
                  {breakdown.audio.toFixed(2)} MB
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Transcript files:</span>
                <span className="font-medium text-gray-900">
                  {breakdown.transcript.toFixed(2)} MB
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Search index (estimated):</span>
                <span className="font-medium text-gray-900">
                  {breakdown.index.toFixed(2)} MB
                </span>
              </div>
              <div className="border-t border-gray-200 pt-2 mt-2 flex justify-between">
                <span className="font-semibold text-gray-900">Total:</span>
                <span className="font-semibold text-gray-900">
                  {(breakdown.audio + breakdown.transcript + breakdown.index).toFixed(2)} MB
                </span>
              </div>
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
                    <p className="text-xs text-gray-500">
                      {((video.audio_file_size_mb || 0) + (video.transcript_size_mb || 0)).toFixed(2)} MB
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Deletion Options */}
          <div>
            <h3 className="text-sm font-semibold text-gray-900 mb-3">
              What to Delete
            </h3>
            <div className="space-y-3">
              {/* Remove from Library */}
              <label className="flex items-start space-x-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={removeFromLibrary}
                  onChange={(e) => setRemoveFromLibrary(e.target.checked)}
                  disabled={isLoading}
                  className="mt-1 h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                />
                <div className="flex-1">
                  <p className="font-medium text-gray-900 text-sm">
                    Remove from library
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    Hide videos from your library. Database records are kept for
                    audit purposes.
                  </p>
                </div>
              </label>

              {/* Delete Search Index */}
              <label className="flex items-start space-x-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={deleteSearchIndex}
                  onChange={(e) => setDeleteSearchIndex(e.target.checked)}
                  disabled={isLoading}
                  className="mt-1 h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                />
                <div className="flex-1">
                  <p className="font-medium text-gray-900 text-sm">
                    Delete search index
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    Remove chunks from vector store.{" "}
                    <span className="font-semibold text-red-600">
                      ⚠️ Chat won't be able to search these videos anymore.
                    </span>
                  </p>
                </div>
              </label>

              {/* Delete Audio */}
              <label className="flex items-start space-x-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={deleteAudio}
                  onChange={(e) => setDeleteAudio(e.target.checked)}
                  disabled={isLoading}
                  className="mt-1 h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                />
                <div className="flex-1">
                  <p className="font-medium text-gray-900 text-sm">
                    Delete audio files ({breakdown.audio.toFixed(2)} MB)
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    Permanently delete downloaded audio. Cannot re-transcribe
                    later.
                  </p>
                </div>
              </label>

              {/* Delete Transcript */}
              <label className="flex items-start space-x-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={deleteTranscript}
                  onChange={(e) => setDeleteTranscript(e.target.checked)}
                  disabled={isLoading}
                  className="mt-1 h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                />
                <div className="flex-1">
                  <p className="font-medium text-gray-900 text-sm">
                    Delete transcript files ({breakdown.transcript.toFixed(2)} MB)
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    Permanently delete transcript files. Saved chat history is
                    unaffected.
                  </p>
                </div>
              </label>
            </div>
          </div>

          {/* Total Savings */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-gray-900">
                Total space freed:
              </span>
              <span className="text-lg font-bold text-blue-600">
                {totalSavings.toFixed(2)} MB
              </span>
            </div>
          </div>

          {/* Warning */}
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 flex gap-3">
            <AlertTriangle className="w-5 h-5 text-yellow-600 flex-shrink-0 mt-0.5" />
            <div className="text-sm text-yellow-800">
              <p className="font-semibold mb-1">This action cannot be undone.</p>
              <p>
                Deleted files are permanently removed. Database records are soft-deleted
                for audit purposes.
              </p>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-3 p-6 border-t border-gray-200 sticky bottom-0 bg-gray-50">
          <button
            onClick={onCancel}
            disabled={isLoading}
            className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            disabled={
              isLoading || (!removeFromLibrary && !deleteSearchIndex && !deleteAudio && !deleteTranscript)
            }
            className="inline-flex items-center px-4 py-2 border border-transparent rounded-md text-sm font-medium text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
            Delete {videos.length > 1 ? `${videos.length} Videos` : "Video"}
          </button>
        </div>
      </div>
    </div>
  );
}
