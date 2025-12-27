'use client';

import { useCallback } from 'react';
import { Upload, FileText, X } from 'lucide-react';

interface FileUploadProps {
  file: File | null;
  onFileChange: (file: File | null) => void;
  accept?: string;
  label?: string;
}

export function FileUpload({
  file,
  onFileChange,
  accept = '.pdf',
  label = 'העלה קובץ PDF',
}: FileUploadProps) {
  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const droppedFile = e.dataTransfer.files[0];
      if (droppedFile && droppedFile.type === 'application/pdf') {
        onFileChange(droppedFile);
      }
    },
    [onFileChange]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
  }, []);

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const selectedFile = e.target.files?.[0];
      if (selectedFile) {
        onFileChange(selectedFile);
      }
    },
    [onFileChange]
  );

  if (file) {
    return (
      <div className="flex items-center gap-3 p-4 bg-primary-50 border border-primary-200 rounded-lg">
        <FileText className="text-primary-500" size={24} />
        <div className="flex-1">
          <p className="font-medium text-primary-800">{file.name}</p>
          <p className="text-sm text-primary-600">
            {(file.size / 1024 / 1024).toFixed(2)} MB
          </p>
        </div>
        <button
          onClick={() => onFileChange(null)}
          className="p-2 text-primary-600 hover:text-primary-800 hover:bg-primary-100 rounded-full transition-colors"
        >
          <X size={20} />
        </button>
      </div>
    );
  }

  return (
    <div
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      className="relative border-2 border-dashed border-surface-300 rounded-lg p-8 text-center hover:border-primary-400 hover:bg-primary-50/50 transition-colors cursor-pointer"
    >
      <input
        type="file"
        accept={accept}
        onChange={handleFileInput}
        className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
      />
      <Upload className="mx-auto text-gray-400 mb-3" size={40} />
      <p className="text-gray-600 font-medium">{label}</p>
      <p className="text-sm text-gray-400 mt-1">גרור קובץ לכאן או לחץ לבחירה</p>
    </div>
  );
}
