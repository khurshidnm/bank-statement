"use client";

import { useCallback, useState } from "react";
import { useDropzone, FileRejection } from "react-dropzone";
import { FileSpreadsheet, Loader2, UploadCloud } from "lucide-react";
import clsx from "clsx";

const ACCEPTED_MIME_TYPES = {
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
  "application/vnd.ms-excel": [".xls"],
  "text/csv": [".csv"],
  "application/json": [".json"],
};

export type UploadStatus = "idle" | "uploading" | "success" | "error";

interface FileDropzoneProps {
  status: UploadStatus;
  progress: number;
  selectedFileName: string | null;
  onFileSelected: (file: File) => void;
}

export default function FileDropzone({
  status,
  progress,
  selectedFileName,
  onFileSelected,
}: FileDropzoneProps) {
  const [rejectionMessage, setRejectionMessage] = useState<string | null>(null);

  const onDrop = useCallback(
    (acceptedFiles: File[], fileRejections: FileRejection[]) => {
      if (fileRejections.length > 0) {
        setRejectionMessage(fileRejections[0].errors[0]?.message ?? "File was rejected.");
        return;
      }
      setRejectionMessage(null);
      if (acceptedFiles.length > 0) {
        onFileSelected(acceptedFiles[0]);
      }
    },
    [onFileSelected]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_MIME_TYPES,
    maxSize: 25 * 1024 * 1024,
    multiple: false,
    disabled: status === "uploading",
  });

  const isUploading = status === "uploading";

  return (
    <div>
      <div
        {...getRootProps()}
        className={clsx(
          "flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-14 text-center transition-colors",
          isDragActive ? "border-accent bg-accent/5" : "border-border bg-surface",
          isUploading && "pointer-events-none opacity-70"
        )}
      >
        <input {...getInputProps()} />
        {isUploading ? (
          <Loader2 className="mb-4 animate-spin text-accent" size={32} />
        ) : selectedFileName ? (
          <FileSpreadsheet className="mb-4 text-accent" size={32} />
        ) : (
          <UploadCloud className="mb-4 text-muted" size={32} />
        )}

        {isUploading ? (
          <p className="text-sm font-medium text-white">
            Transforming {selectedFileName}&hellip; {progress}%
          </p>
        ) : selectedFileName ? (
          <p className="text-sm font-medium text-white">{selectedFileName}</p>
        ) : (
          <>
            <p className="text-sm font-medium text-white">
              Drag &amp; drop a file, or click to browse
            </p>
            <p className="mt-1 text-xs text-muted">
              Supports .xlsx, .xls, .csv, .json &middot; up to 25MB
            </p>
          </>
        )}

        {isUploading && (
          <div className="mt-4 h-1.5 w-full max-w-xs overflow-hidden rounded-full bg-border">
            <div
              className="h-full rounded-full bg-accent transition-all"
              style={{ width: `${progress}%` }}
            />
          </div>
        )}
      </div>

      {rejectionMessage && (
        <p className="mt-2 text-xs text-red-400">{rejectionMessage}</p>
      )}
    </div>
  );
}
