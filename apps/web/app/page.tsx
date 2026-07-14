import { CommandCenter } from "@/components/command-center";
import { getApiStatus, getWorkflowCatalog } from "@/lib/api";

export default async function Home() {
  const [apiStatus, workflowCatalog] = await Promise.all([getApiStatus(), getWorkflowCatalog()]);

  return <CommandCenter apiStatus={apiStatus} workflowCatalog={workflowCatalog} />;
}
