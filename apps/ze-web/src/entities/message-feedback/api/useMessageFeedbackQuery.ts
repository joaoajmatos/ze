import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { queryKeys } from "@/shared/lib";
import type { MessageFeedback } from "../model/types";
import { fetchMessageFeedback } from "./feedbackApi";

const MAX_IDS = 100;

export function useMessageFeedbackQuery(messageIds: string[]) {
  const ids = useMemo(() => [...new Set(messageIds)].slice(-MAX_IDS).sort(), [messageIds]);
  const idsKey = ids.join(",");

  const query = useQuery({
    queryKey: queryKeys.messageFeedback(idsKey),
    queryFn: () => fetchMessageFeedback(ids),
    enabled: ids.length > 0,
    placeholderData: keepPreviousData,
    retry: false,
  });

  const byId = useMemo(
    () => new Map<string, MessageFeedback>((query.data ?? []).map((f) => [f.message_id, f])),
    [query.data],
  );
  return { byId, isLoading: query.isLoading };
}
