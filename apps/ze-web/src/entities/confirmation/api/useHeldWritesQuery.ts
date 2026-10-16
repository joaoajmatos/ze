import { useQuery } from "@tanstack/react-query";
import { listHeldWrites } from "@myguyze/ze-client";
import type { HeldWriteOut } from "@myguyze/ze-client";
import { queryKeys } from "@/shared/lib";

export function useHeldWritesQuery() {
  return useQuery<HeldWriteOut[]>({
    queryKey: queryKeys.heldWrites,
    queryFn: async () => {
      const { data, error } = await listHeldWrites({ query: { status: "open" } });
      if (error) throw error;
      return data!.items;
    },
  });
}
