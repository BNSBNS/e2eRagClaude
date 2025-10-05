// src/components/upload/FileUpload.tsx
import React, { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { apiClient } from '@/lib/api';
import { useWebSocket } from '@/hooks/useWebSocket';

interface FileUploadProps {
  onUploadComplete: (document: any) => void;
}

export const FileUpload: React.FC<FileUploadProps> = ({ onUploadComplete }) => {
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const { sendMessage } = useWebSocket();

  const getDocumentType = (file: File): string => {
    if (file.type.includes('pdf')) return 'pdf';
    if (file.type.includes('text/plain')) return 'txt';
    if (file.type.includes('csv')) return 'csv';
    return 'unknown';
  };

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    setUploading(true);
    setProgress(0);
    
    for (let i = 0; i < acceptedFiles.length; i++) {
      const file = acceptedFiles[i];
      const documentType = getDocumentType(file);

      try {
        // Update progress for current file
        setProgress(Math.round(((i + 0.5) / acceptedFiles.length) * 100));

        // Use the existing uploadDocument method
        const response = await apiClient.uploadDocument(file, documentType);

        // Update progress to completed for this file
        setProgress(Math.round(((i + 1) / acceptedFiles.length) * 100));

        // Notify WebSocket for real-time updates
        if (sendMessage) {
          sendMessage({
            type: 'document_upload',
            document_id: response.data?.id

          });
        }

        onUploadComplete(response);
      } catch (error) {
        console.error('Upload failed for file:', file.name, error);
        // You might want to show user-friendly error messages here
      }
    }
    
    setUploading(false);
    setProgress(0);
  }, [onUploadComplete, sendMessage]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'text/plain': ['.txt'],
      'text/csv': ['.csv']
    },
    maxSize: 10485760, // 10MB
    multiple: true
  });

  return (
    <div
      {...getRootProps()}
      className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
        isDragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300'
      } ${uploading ? 'pointer-events-none opacity-50' : ''}`}
    >
      <input {...getInputProps()} />
      {uploading ? (
        <div className="space-y-2">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto" />
          <p>Uploading... {progress}%</p>
          <div className="w-full bg-gray-200 rounded-full h-2.5">
            <div 
              className="bg-blue-600 h-2.5 rounded-full transition-all duration-300" 
              style={{ width: `${progress}%` }}
            ></div>
          </div>
        </div>
      ) : (
        <div>
          {isDragActive ? (
            <p>Drop the files here...</p>
          ) : (
            <div>
              <svg className="mx-auto h-12 w-12 text-gray-400" stroke="currentColor" fill="none" viewBox="0 0 48 48">
                <path d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              <p className="mt-2">Drag 'n' drop files here, or click to select files</p>
            </div>
          )}
          <p className="text-sm text-gray-500 mt-2">
            Supports PDF, TXT, CSV files up to 10MB
          </p>
        </div>
      )}
    </div>
  );
};