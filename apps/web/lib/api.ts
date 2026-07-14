export type ApiHealth = {
  status: string;
  service: string;
};

export type ApiStatus =
  | {
      configured: false;
      label: "not_configured";
      message: string;
    }
  | {
      configured: true;
      label: "online";
      message: string;
      health: ApiHealth;
    }
  | {
      configured: true;
      label: "unreachable";
      message: string;
    };

export async function getApiStatus(): Promise<ApiStatus> {
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;

  if (!baseUrl) {
    return {
      configured: false,
      label: "not_configured",
      message: "API URL is not configured for this deployment.",
    };
  }

  try {
    const response = await fetch(`${baseUrl.replace(/\/$/, "")}/health`, {
      cache: "no-store",
      headers: {
        accept: "application/json",
      },
    });

    if (!response.ok) {
      return {
        configured: true,
        label: "unreachable",
        message: `API health check returned HTTP ${response.status}.`,
      };
    }

    const health = (await response.json()) as ApiHealth;
    return {
      configured: true,
      label: "online",
      message: "API health endpoint is reachable.",
      health,
    };
  } catch {
    return {
      configured: true,
      label: "unreachable",
      message: "API health endpoint could not be reached.",
    };
  }
}
