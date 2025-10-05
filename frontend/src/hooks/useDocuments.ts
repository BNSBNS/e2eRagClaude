"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api";
import { useSession } from "@/app/providers/SessionProvider";

/** Fetch single document */
export function useDocument(documentId: string) {
  const { isAuthenticated } = useSession();

  return useQuery({
    queryKey: ["documents", documentId],
    queryFn: async () => {
      const response = await apiClient.get(`/api/documents/${documentId}`);
      return response.data;
    },
    enabled: Boolean(isAuthenticated && documentId),
  });
}

/** Fetch list of documents */
export function useDocuments() {
  const { isAuthenticated } = useSession();

  return useQuery({
    queryKey: ["documents"],
    queryFn: async () => {
      // expects backend to return an array of documents (or structured object)
      const res = await apiClient.get("/api/documents");
      return res.data;
    },
    enabled: Boolean(isAuthenticated),
  });
}

/** Upload hook */
export function useUploadDocument() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ file, documentType }: { file: File; documentType: string }) =>
      apiClient.uploadDocument(file, documentType),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents"] });
    },
    onError: (error) => {
      console.error("Upload failed:", error);
    },
  });
}

/** Delete hook */
export function useDeleteDocument() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (documentId: string) => apiClient.deleteDocument(documentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents"] });
    },
  });
}

/** Document QA mutation */
export function useDocumentQuery() {
  return useMutation({
    mutationFn: ({ documentId, query, method }: { documentId: string; query: string; method: "rag" | "graph" }) =>
      apiClient.queryDocument(documentId, query, method),
  });
}
