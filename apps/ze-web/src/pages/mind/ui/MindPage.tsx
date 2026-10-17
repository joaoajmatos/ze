import { useNavigate } from "react-router-dom";
import { BeliefsFeed } from "@/widgets/beliefs-feed";
import { EntitySearch } from "@/widgets/entity-search";
import { People } from "@/widgets/people";
import { Procedures } from "@/widgets/procedures";

export function MindPage() {
  const navigate = useNavigate();
  return (
    <div className="mind-grid">
      <div className="mind-main">
        <BeliefsFeed />
      </div>
      <div className="mind-rail">
        <People />
        <EntitySearch onSelect={(id) => navigate(`/mind/${id}`)} />
        <Procedures />
      </div>
    </div>
  );
}
