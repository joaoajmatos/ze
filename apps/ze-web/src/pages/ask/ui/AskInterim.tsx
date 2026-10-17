import { useEffect } from "react";
import { useParams } from "react-router-dom";
import { ChatWorkspace } from "@/widgets/chat-workspace";
import { useSession } from "@/entities/session";

/** Ask's interim content; phase 187 replaces this file. `/ask/:threadId` opens that thread. */
export function AskInterim() {
  const { threadId } = useParams<{ threadId: string }>();
  const selectSession = useSession((s) => s.selectSession);

  useEffect(() => {
    if (threadId && useSession.getState().threadId !== threadId) selectSession(threadId);
  }, [threadId, selectSession]);

  return (
    <div className="ask-place">
      <ChatWorkspace threadId={threadId} />
    </div>
  );
}
