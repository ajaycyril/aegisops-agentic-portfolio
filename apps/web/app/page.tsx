import { CommandCenter } from "@/components/command-center";
import {
  getApiStatus,
  getDemoWorkflowRunTrace,
  getWorkflowCatalog,
} from "@/lib/api";

export default async function Home() {
  const [apiStatus, workflowCatalog, workflowRunTrace] = await Promise.all([
    getApiStatus(),
    getWorkflowCatalog(),
    getDemoWorkflowRunTrace(),
  ]);

  return (
    <CommandCenter
      apiStatus={apiStatus}
      workflowCatalog={workflowCatalog}
      workflowRunTrace={workflowRunTrace}
    />
  );
}
