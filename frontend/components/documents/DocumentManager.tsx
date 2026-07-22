"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, CheckCircle2, Loader2, Trash2, Upload, X } from "lucide-react";
import { useRef, useState, type ChangeEvent } from "react";

import {
  deleteDocument,
  listDocuments,
  uploadDocument,
  type DocumentItem,
} from "@/lib/api/documents";
import { ApiError } from "@/lib/api/client";

const ACCEPTED_EXTENSIONS = ".pdf,.docx,.txt,.csv,.xlsx";

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function StatusBadge({ document }: { document: DocumentItem }) {
  if (document.status === "ready") {
    return (
      <span className="flex items-center gap-1 text-xs text-green-600 dark:text-green-500">
        <CheckCircle2 size={13} />
        {document.chunk_count} {document.chunk_count === 1 ? "chunk" : "chunks"}
      </span>
    );
  }
  if (document.status === "failed") {
    return (
      <span
        className="flex items-center gap-1 text-xs text-red-500"
        title={document.error_message ?? "Processing failed"}
      >
        <AlertCircle size={13} />
        Failed
      </span>
    );
  }
  return (
    <span className="flex items-center gap-1 text-xs text-black/50 dark:text-white/50">
      <Loader2 size={13} className="animate-spin" />
      {document.status === "processing" ? "Processing" : "Pending"}
    </span>
  );
}

function DocumentRow({ document }: { document: DocumentItem }) {
  const queryClient = useQueryClient();

  const { mutate: remove, isPending: isDeleting } = useMutation({
    mutationFn: () => deleteDocument(document.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["documents"] }),
  });

  return (
    <div className="group flex items-center justify-between gap-3 rounded-lg border border-black/10 dark:border-white/10 px-3 py-2.5">
      <div className="flex-1 min-w-0">
        <p className="truncate text-sm text-black/80 dark:text-white/80">{document.filename}</p>
        <div className="mt-0.5 flex items-center gap-2">
          <span className="text-xs text-black/40 dark:text-white/40">{formatSize(document.size_bytes)}</span>
          <StatusBadge document={document} />
        </div>
      </div>
      <button
        onClick={() => remove()}
        disabled={isDeleting}
        aria-label="Delete document"
        className="flex-shrink-0 text-black/40 hover:text-red-500 dark:text-white/40 opacity-0 group-hover:opacity-100 disabled:opacity-40"
      >
        <Trash2 size={14} />
      </button>
    </div>
  );
}

export function DocumentManager({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const { data: documents, isLoading } = useQuery({
    queryKey: ["documents"],
    queryFn: listDocuments,
    // Keep polling while anything is still pending/processing so status flips to
    // ready/failed without the user having to reopen the modal.
    refetchInterval: (query) => {
      const items = query.state.data as DocumentItem[] | undefined;
      const hasInFlight = items?.some((d) => d.status === "pending" || d.status === "processing");
      return hasInFlight ? 2000 : false;
    },
  });

  const { mutate: upload, isPending: isUploading } = useMutation({
    mutationFn: uploadDocument,
    onSuccess: () => {
      setUploadError(null);
      queryClient.invalidateQueries({ queryKey: ["documents"] });
    },
    onError: (error) => {
      setUploadError(error instanceof ApiError ? error.message : "Upload failed");
    },
  });

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (file) upload(file);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4" onClick={onClose}>
      <div
        className="w-full max-w-lg rounded-2xl bg-white dark:bg-neutral-900 border border-black/10 dark:border-white/10 shadow-xl max-h-[85vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-black/10 dark:border-white/10">
          <div>
            <h2 className="text-sm font-semibold">Knowledge base</h2>
            <p className="text-xs text-black/50 dark:text-white/50 mt-0.5">
              Upload documents so the assistant can reference them in chat.
            </p>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="text-black/40 hover:text-black dark:text-white/40 dark:hover:text-white flex-shrink-0"
          >
            <X size={18} />
          </button>
        </div>

        <div className="flex flex-col gap-2 px-5 py-4">
          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPTED_EXTENSIONS}
            onChange={handleFileChange}
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
            className="flex items-center justify-center gap-2 rounded-lg border border-dashed border-black/20 dark:border-white/20 px-3 py-3 text-sm text-black/60 hover:border-black/40 hover:bg-black/5 dark:text-white/60 dark:hover:border-white/40 dark:hover:bg-white/5 disabled:opacity-50"
          >
            {isUploading ? <Loader2 size={16} className="animate-spin" /> : <Upload size={16} />}
            {isUploading ? "Uploading..." : "Upload a file"}
          </button>
          <p className="text-xs text-black/40 dark:text-white/40">PDF, DOCX, TXT, CSV, or XLSX - up to 20MB.</p>
          {uploadError && <p className="text-xs text-red-500">{uploadError}</p>}

          <div className="mt-2 flex flex-col gap-2">
            {isLoading && <p className="text-sm text-black/40 dark:text-white/40">Loading...</p>}
            {!isLoading && (!documents || documents.length === 0) && (
              <p className="text-sm text-black/40 dark:text-white/40">No documents uploaded yet.</p>
            )}
            {documents?.map((document) => (
              <DocumentRow key={document.id} document={document} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
