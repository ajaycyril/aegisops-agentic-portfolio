import { CommandCenter } from "@/components/command-center";
import { getApiStatus } from "@/lib/api";

export default async function Home() {
  const apiStatus = await getApiStatus();

  return <CommandCenter apiStatus={apiStatus} />;
}
