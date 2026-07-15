import { CommandCenter } from "@/components/command-center";
import {
  getApiStatus,
  getDemoWorkflowRunTrace,
  getDemoWorkflowRunTraceEval,
  getWorkflowCatalog,
} from "@/lib/api";

export default async function Home() {
  const [apiStatus, workflowCatalog, workflowRunTrace, workflowRunTraceEval] =
    await Promise.all([
      getApiStatus(),
      getWorkflowCatalog(),
      getDemoWorkflowRunTrace(),
      getDemoWorkflowRunTraceEval(),
    ]);

  return (
    <CommandCenter
      apiStatus={apiStatus}
      workflowCatalog={workflowCatalog}
      workflowRunTrace={workflowRunTrace}
      workflowRunTraceEval={workflowRunTraceEval}
    />
  );
}
