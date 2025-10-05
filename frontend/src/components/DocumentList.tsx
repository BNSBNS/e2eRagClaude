"use client";

import React from "react";
import { useDocuments, useDeleteDocument } from "@/hooks/useDocuments";
import { useAuth } from "@/hooks/useAuth";
import Link from "next/link";

type Doc = {
  id: string | number;
  title?: string;
  status?: string;
  content_type?: string;
  metadata?: { num_pages?: number; char_count?: number };
  created_at?: string;
  user_id?: string | number;
};

export function DocumentList() {
  const { data: documents, isLoading, isError } = useDocuments();
  const deleteMutation = useDeleteDocument();
  const { user } = useAuth();

  if (isLoading) {
    return (
      <div className="text-center py-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto" />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="text-center py-8">
        <p className="text-red-600">Failed to load documents.</p>
      </div>
    );
  }

  const docsArray: Doc[] = Array.isArray(documents) ? documents : (documents?.data ?? []);

  if (!docsArray || docsArray.length === 0) {
    return (
      <div className="text-center py-12 bg-gray-50 rounded-lg">
        <p className="text-gray-500">No documents uploaded yet</p>
      </div>
    );
  }

  const handleDelete = async (documentId: string | number) => {
    if (!confirm("Are you sure you want to delete this document?")) return;
    try {
      await deleteMutation.mutateAsync(String(documentId));
    } catch (err) {
      console.error("Delete failed", err);
    }
  };

  const getStatusColor = (status?: string) => {
    switch (status) {
      case "completed":
        return "bg-green-100 text-green-800";
      case "processing":
        return "bg-yellow-100 text-yellow-800";
      case "failed":
        return "bg-red-100 text-red-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  // Robust isDeleting check:
  // - check .status for 'pending' (your typings)
  // - fallback to other boolean flags or status strings using `any` to avoid TS complaints
  const isDeleting =
    deleteMutation.status === "pending" ||
    (deleteMutation as any).status === "loading" ||
    Boolean((deleteMutation as any).isLoading) ||
    Boolean((deleteMutation as any).isPending);

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {docsArray.map((doc) => (
        <div key={String(doc.id)} className="bg-white border rounded-lg p-4 hover:shadow-md transition-shadow">
          <div className="flex justify-between items-start mb-2">
            <h3 className="font-medium text-gray-900 truncate flex-1">{doc.title ?? `Document ${doc.id}`}</h3>
            <span className={`px-2 py-1 text-xs rounded-full ${getStatusColor(doc.status)}`}>{doc.status ?? "unknown"}</span>
          </div>

          <p className="text-sm text-gray-600 mb-3">Type: {(doc.content_type ?? "unknown").toString().toUpperCase()}</p>

          {doc.metadata && (
            <p className="text-xs text-gray-500 mb-3">
              {doc.metadata.num_pages && `${doc.metadata.num_pages} pages`}
              {doc.metadata.char_count && ` • ${Math.round(doc.metadata.char_count / 1000)}K chars`}
            </p>
          )}

          <div className="flex justify-between items-center pt-3 border-t">
            <span className="text-xs text-gray-400">{doc.created_at ? new Date(doc.created_at).toLocaleDateString() : ""}</span>

            <div className="flex space-x-2">
              {doc.status === "completed" && (
                <Link href={`/documents/${doc.id}`}>
                  <span className="text-xs text-blue-600 hover:text-blue-800">Query</span>
                </Link>
              )}

              {(user?.role === "admin" || doc.user_id === user?.id) && (
                <button onClick={() => handleDelete(doc.id)} className="text-xs text-red-600 hover:text-red-800" disabled={isDeleting}>
                  {isDeleting ? "Deleting..." : "Delete"}
                </button>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
