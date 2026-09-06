import {
  CompleteRequest,
  InterviewResponse,
  Patient,
  RespondRequest,
  RuntimeStatus,
  StartRequest,
} from "./contracts";

const apiBase = (
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  process.env.NEXT_PUBLIC_M2_API_BASE_URL ||
  "http://127.0.0.1:8000"
).replace(/\/$/, "");
const requestTimeoutMs = Number(process.env.NEXT_PUBLIC_API_TIMEOUT_MS || 30000);

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function parseError(response: Response): Promise<Error> {
  try {
    const body = await response.json();
    const detail = typeof body === "object" && body !== null && "detail" in body
      ? (body as { detail?: string }).detail || response.statusText
      : response.statusText;
    return new ApiError(response.status, `${response.status}: ${detail}`);
  } catch {
    return new ApiError(response.status, `${response.status}: ${response.statusText}`);
  }
}

async function request<TResponse>(path: string, init?: RequestInit): Promise<TResponse> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), requestTimeoutMs);
  const response = await fetch(`${apiBase}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
    signal: controller.signal,
  });
  window.clearTimeout(timeout);
  if (!response.ok) {
    throw await parseError(response);
  }
  return (await response.json()) as TResponse;
}

async function post<TRequest, TResponse>(path: string, body: TRequest): Promise<TResponse> {
  return request<TResponse>(path, { method: "POST", body: JSON.stringify(body) });
}

export async function startInterview(patient: Patient, consent: true): Promise<InterviewResponse> {
  const payload: StartRequest = { patient, consent };
  return post<StartRequest, InterviewResponse>("/interview/start", payload);
}

export async function submitResponse(payload: Omit<RespondRequest, "expected_revision"> & { expected_revision: number }): Promise<InterviewResponse> {
  return post<RespondRequest, InterviewResponse>("/interview/respond", payload);
}

export async function completeInterview(payload: CompleteRequest): Promise<InterviewResponse> {
  return post<CompleteRequest, InterviewResponse>("/interview/complete", payload);
}

export async function getInterview(interviewId: string): Promise<InterviewResponse> {
  return request<InterviewResponse>(`/interview/${encodeURIComponent(interviewId)}`);
}

export async function getRuntimeStatus(): Promise<RuntimeStatus> {
  return request<RuntimeStatus>("/health");
}
