"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import * as api from "@/lib/api";

export const clientKeys = {
  all: ["clients"] as const,
  list: (q: string) => ["clients", q] as const,
  config: ["config"] as const,
};

export function useClients(q = "") {
  return useQuery({
    queryKey: clientKeys.list(q),
    queryFn: () => api.listClients(q),
  });
}

export function useActiveConfig() {
  return useQuery({ queryKey: clientKeys.config, queryFn: api.getConfig });
}

export function useActivateClient() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.activateClient(id),
    onSuccess: (client) => {
      qc.invalidateQueries({ queryKey: clientKeys.all });
      qc.invalidateQueries({ queryKey: clientKeys.config });
      toast.success(`Switched to ${client.name}`);
    },
  });
}
