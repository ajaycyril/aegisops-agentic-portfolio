import { headers } from "next/headers";

import { CommandCenter } from "@/components/command-center";
import {
  getApiBaseUrl,
  getApiStatus,
  getDemoWorkflowRunTrace,
  getDemoWorkflowRunTraceEval,
  getToolCatalog,
  getWorkflowCatalog,
} from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function Home() {
  const requestHeaders = await headers();
  const apiBaseUrl = getApiBaseUrl(requestHeaders);
  const [
    apiStatus,
    workflowCatalog,
    toolCatalog,
    workflowRunTrace,
    workflowRunTraceEval,
  ] =
    await Promise.all([
      getApiStatus(apiBaseUrl),
      getWorkflowCatalog(apiBaseUrl),
      getToolCatalog(apiBaseUrl),
      getDemoWorkflowRunTrace(apiBaseUrl),
      getDemoWorkflowRunTraceEval(apiBaseUrl),
    ]);

  return (
    <CommandCenter
      apiBaseUrl={apiBaseUrl}
      apiStatus={apiStatus}
      toolCatalog={toolCatalog}
      workflowCatalog={workflowCatalog}
      workflowRunTrace={workflowRunTrace}
      workflowRunTraceEval={workflowRunTraceEval}
    />
  );
}
