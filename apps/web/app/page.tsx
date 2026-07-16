import { headers } from "next/headers";

import { CommandCenter } from "@/components/command-center";
import {
  getApiBaseUrl,
  getApiStatus,
  getDemoWorkflowRunTrace,
  getDemoWorkflowRunTraceEval,
  getWorkflowCatalog,
} from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function Home() {
  const requestHeaders = await headers();
  const apiBaseUrl = getApiBaseUrl(requestHeaders);
  const [apiStatus, workflowCatalog, workflowRunTrace, workflowRunTraceEval] =
    await Promise.all([
      getApiStatus(apiBaseUrl),
      getWorkflowCatalog(apiBaseUrl),
      getDemoWorkflowRunTrace(apiBaseUrl),
      getDemoWorkflowRunTraceEval(apiBaseUrl),
    ]);

  return (
    <CommandCenter
      apiBaseUrl={apiBaseUrl}
      apiStatus={apiStatus}
      workflowCatalog={workflowCatalog}
      workflowRunTrace={workflowRunTrace}
      workflowRunTraceEval={workflowRunTraceEval}
    />
  );
}
