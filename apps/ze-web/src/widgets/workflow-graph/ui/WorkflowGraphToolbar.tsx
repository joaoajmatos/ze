interface Props {
  hideNotTaken: boolean;
  onToggleHideNotTaken: () => void;
  onFitView: () => void;
}

export function WorkflowGraphToolbar({ hideNotTaken, onToggleHideNotTaken, onFitView }: Props) {
  return (
    <div className="graph-tools">
      <button type="button" className="ctl" onClick={onFitView}>
        Fit
      </button>
      <button type="button" className="ctl" aria-pressed={hideNotTaken} onClick={onToggleHideNotTaken}>
        {hideNotTaken ? "Show skipped" : "Hide skipped"}
      </button>
    </div>
  );
}
