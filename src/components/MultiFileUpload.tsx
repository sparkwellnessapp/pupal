'use client';

import { useCallback } from 'react';
import { Upload, FileText, X, Files } from 'lucide-react';

interface MultiFileUploadProps {
  files: File[];
  onFilesChange: (files: File[]) => void;
  accept?: string;
  label?: string;
  maxFiles?: number;
}

export function MultiFileUpload({
  files,
  onFilesChange,
  accept = '.pdf',
  label = 'העלה קבצי PDF',
  maxFiles = 50,
}: MultiFileUploadProps) {
  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const droppedFiles = Array.from(e.dataTransfer.files).filter(
        (f) => f.type === 'application/pdf'
      );
      const newFiles = [...files, ...droppedFiles].slice(0, maxFiles);
      onFilesChange(newFiles);
    },
    [files, onFilesChange, maxFiles]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
  }, []);

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const selectedFiles = Array.from(e.target.files || []);
      const newFiles = [...files, ...selectedFiles].slice(0, maxFiles);
      onFilesChange(newFiles);
      // Reset input
      e.target.value = '';
    },
    [files, onFilesChange, maxFiles]
  );

  const removeFile = (index: number) => {
    const newFiles = files.filter((_, i) => i !== index);
    onFilesChange(newFiles);
  };

  const clearAll = () => {
    onFilesChange([]);
  };

  const totalSize = files.reduce((sum, f) => sum + f.size, 0);

  return (
    <div className="space-y-3">
      {/* Drop zone */}
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        className="relative border-2 border-dashed border-surface-300 rounded-lg p-6 text-center hover:border-green-400 hover:bg-green-50/50 transition-colors cursor-pointer"
      >
        <input
          type="file"
          accept={accept}
          multiple
          onChange={handleFileInput}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
        />
        <Upload className="mx-auto text-gray-400 mb-2" size={32} />
        <p className="text-gray-600 font-medium">{label}</p>
        <p className="text-sm text-gray-400 mt-1">
          גרור קבצים לכאן או לחץ לבחירה (עד {maxFiles} קבצים)
        </p>
      </div>

      {/* File list */}
      {files.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-2 text-gray-600">
              <Files size={16} />
              <span>{files.length} קבצים</span>
              <span className="text-gray-400">
                ({(totalSize / 1024 / 1024).toFixed(1)} MB)
              </span>
            </div>
            <button
              onClick={clearAll}
              className="text-red-500 hover:text-red-700 text-xs"
            >
              נקה הכל
            </button>
          </div>

          <div className="max-h-48 overflow-y-auto space-y-1">
            {files.map((file, index) => (
              <div
                key={index}
                className="flex items-center gap-2 p-2 bg-surface-50 rounded-lg text-sm"
              >
                <FileText size={16} className="text-gray-400 flex-shrink-0" />
                <span className="flex-1 truncate text-gray-700">{file.name}</span>
                <span className="text-xs text-gray-400">
                  {(file.size / 1024).toFixed(0)} KB
                </span>
                <button
                  onClick={() => removeFile(index)}
                  className="text-gray-400 hover:text-red-500 p-1"
                >
                  <X size={14} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
