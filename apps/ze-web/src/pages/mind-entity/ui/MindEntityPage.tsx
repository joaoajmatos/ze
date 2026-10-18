import { Link, useNavigate, useParams } from "react-router-dom";
import { EntityNeighbourhood, Suspicions } from "@/widgets/entity-neighbourhood";
import { EntitySearch } from "@/widgets/entity-search";
import { PluginModuleSlot } from "@/widgets/plugin-module";
import { useChatAbout } from "@/features/ask-bar";
import { useEntityDetailQuery } from "@/entities/memory-graph";
import { useScreenPublisher } from "@/entities/screen-context";
import { Control } from "@/shared/ui";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function MindEntityPage() {
  const { entityId } = useParams<{ entityId: string }>();
  const navigate = useNavigate();
  const valid = entityId != null && UUID.test(entityId);
  const { data, isLoading, isError, refetch } = useEntityDetailQuery(valid ? entityId : null);
  const open = (id: string) => navigate(`/mind/${id}`);
  const chatAbout = useChatAbout();
  useScreenPublisher(
    data
      ? {
          subject: [{ kind: "entity", id: data.entity.id, label: data.entity.canonical_name, component: "entity_module" }],
          focused_module: "Mind",
        }
      : null,
  );

  return (
    <div className="mind-grid">
      <div className="mind-main">
        <Link to="/mind" className="ctl-text back-link">← Back to Mind</Link>
        {isLoading && <p role="status" className="note">Looking around that entity…</p>}
        {isError && (
          <p className="note">
            Could not load that entity. <Control onClick={() => void refetch()}>Retry</Control>
          </p>
        )}
        {(!valid || data === null) && !isLoading && !isError && <p className="note">No entity here</p>}
        {valid && data && <EntityNeighbourhood detail={data} onSelectEntity={open} onChatAbout={chatAbout} />}
        {valid && data && <Suspicions entityId={data.entity.id} onChatAbout={chatAbout} />}
        {valid && data && (
          <PluginModuleSlot
            slot="mind.entity"
            subject={{ kind: "entity", id: data.entity.id, label: data.entity.canonical_name, entity_type: data.entity.entity_type }}
          />
        )}
      </div>
      <div className="mind-rail">
        <EntitySearch onSelect={open} onChatAbout={chatAbout} />
      </div>
    </div>
  );
}
