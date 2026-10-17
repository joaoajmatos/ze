import { useContactsPageQuery } from "@/entities/contact";
import { ConnectedPrimitiveTree } from "@/features/primitive-tree";
import { Control, Module } from "@/shared/ui";

export function People({ onChatAbout }: { onChatAbout?: (element: Element) => void }) {
  const page = useContactsPageQuery();
  const tree = page.data?.tree;
  const empty = Array.isArray(tree) && tree.length === 0;

  return (
    <Module label="People" onChatAbout={onChatAbout} chatAboutLabel="the people I know">
      {page.isLoading && <p role="status" className="note">Looking up the people I know…</p>}
      {page.isError && (
        <p className="note">
          Could not load people. <Control onClick={() => void page.refetch()}>Retry</Control>
        </p>
      )}
      {empty && <p className="note">No people yet. Connect Gmail or tell me about someone.</p>}
      {tree != null && !empty && <ConnectedPrimitiveTree components={tree} />}
    </Module>
  );
}
