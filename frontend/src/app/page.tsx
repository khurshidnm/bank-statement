"use client";

import { useState } from "react";
import { AlertCircle, CheckCircle2 } from "lucide-react";
import Header from "@/components/Header";
import FileDropzone, { UploadStatus } from "@/components/FileDropzone";
import JsonViewer from "@/components/JsonViewer";
import { transformFile, TransformApiError, TransformResponse } from "@/lib/api";

export default function DashboardPage() {
  const [status, setStatus] = useState<UploadStatus>("idle");
  const [progress, setProgress] = useState(0);
  const [selectedFileName, setSelectedFileName] = useState<string | null>(null);
  const [result, setResult] = useState<TransformResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFileSelected = async (file: File) => {
    setSelectedFileName(file.name);
    setStatus("uploading");
    setProgress(0);
    setError(null);
    setResult(null);

    try {
      const response = await transformFile(file, setProgress);
      setResult(response);
      setStatus("success");
    } catch (err) {
      const message =
        err instanceof TransformApiError
          ? err.message
          : "Something went wrong while transforming this file.";
      setError(message);
      setStatus("error");
    }
  };

  return (
    <main className="min-h-screen">
      <Header />

      <div className="mx-auto max-w-5xl px-6 py-10">
        <FileDropzone
          status={status}
          progress={progress}
          selectedFileName={selectedFileName}
          onFileSelected={handleFileSelected}
        />

        {status === "error" && error && (
          <div className="mt-6 flex items-start gap-2.5 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
            <AlertCircle size={16} className="mt-0.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {status === "success" && result && (
          <div className="mt-6 space-y-4">
            <div className="flex items-center gap-2.5 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300">
              <CheckCircle2 size={16} className="shrink-0" />
              <span>
                Transformed <strong>{result.filename}</strong> &mdash;{" "}
                {result.total_records_processed} record
                {result.total_records_processed === 1 ? "" : "s"} normalized.
              </span>
            </div>

            <JsonViewer data={result.data} filename={result.filename} />
          </div>
        )}
      </div>
    </main>
  );
}
