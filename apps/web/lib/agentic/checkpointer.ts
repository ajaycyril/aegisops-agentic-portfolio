import { MemorySaver } from "@langchain/langgraph";
import type { BaseCheckpointSaver } from "@langchain/langgraph-checkpoint";

let checkpointerPromise: Promise<{
  saver: BaseCheckpointSaver;
  mode: "postgres" | "memory";
}> | null = null;

export function getCheckpointer() {
  checkpointerPromise ??= (async () => {
    const connectionString = process.env.DATABASE_URL;
    if (!connectionString) {
      return { saver: new MemorySaver(), mode: "memory" as const };
    }

    const { PostgresSaver } = await import(
      "@langchain/langgraph-checkpoint-postgres"
    );
    const saver = PostgresSaver.fromConnString(connectionString, {
      schema: "aegisops_demo",
    });
    await saver.setup();
    return { saver, mode: "postgres" as const };
  })();
  return checkpointerPromise;
}
