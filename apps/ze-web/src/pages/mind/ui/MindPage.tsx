import { useNavigate } from "react-router-dom";
import { BeliefsFeed } from "@/widgets/beliefs-feed";
import { EntitySearch } from "@/widgets/entity-search";
import { People } from "@/widgets/people";
import { Procedures } from "@/widgets/procedures";
import { useChatAbout } from "@/features/ask-bar";

export function MindPage() {
  const navigate = useNavigate();
  const chatAbout = useChatAbout();
  return (
    <div className="mind-grid">
      <div className="mind-main">
        <BeliefsFeed onChatAbout={chatAbout} />
      </div>
      <div className="mind-rail">
        <People />
        <EntitySearch onSelect={(id) => navigate(`/mind/${id}`)} onChatAbout={chatAbout} />
        <Procedures onChatAbout={chatAbout} />
      </div>
    </div>
  );
}
