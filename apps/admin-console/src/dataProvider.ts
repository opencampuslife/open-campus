import type {
  BaseRecord,
  CreateParams,
  CustomParams,
  DataProvider,
  DeleteOneParams,
  GetListParams,
  GetManyParams,
  GetOneParams,
  UpdateParams,
} from "@refinedev/core";

const resourceMap: Record<string, string> = {
  staging_docs: "/api/admin/staging/docs",
  sources: "/api/admin/sources",
  ingestion_runs: "/api/admin/ingestion/runs",
  graph_runs: "/api/admin/graph/runs",
  graph_latest: "/api/admin/graph/latest",
  crm_leads: "/api/crm/leads",
  sales_sessions: "/api/sales/sessions",
  campus_leaves: "/api/campus/leaves",
  campus_repairs: "/api/campus/repairs",
  audit_logs: "/api/admin/audit",
  health: "/api/admin/health",
};

let _csrfToken: string | null = null;
let _csrfFetching: Promise<string | null> | null = null;

export async function fetchCsrfToken(): Promise<string | null> {
  if (_csrfToken) return _csrfToken;
  if (_csrfFetching) return _csrfFetching;

  _csrfFetching = fetch("/api/csrf-token", { headers: getAdminHeaders() })
    .then(async (res) => {
      if (!res.ok) return null;
      const body = (await res.json()) as Record<string, unknown>;
      _csrfToken = (body.csrf_token as string) || null;
      _csrfFetching = null;
      return _csrfToken;
    })
    .catch(() => {
      _csrfFetching = null;
      return null;
    });

  return _csrfFetching;
}

export function getCsrfHeaders(baseHeaders?: Record<string, string>): Record<string, string> {
  const headers = { ...getAdminHeaders(), ...(baseHeaders || {}) };
  if (_csrfToken) {
    headers["X-CSRF-Token"] = _csrfToken;
  }
  return headers;
}

function getUrl(resource: string, id?: string | number): string {
  const base = resourceMap[resource] || `/api/admin/${resource}`;
  if (id !== undefined && id !== null) return `${base}/${id}`;
  return base;
}

function getTrustedProxyHeader(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const host = window.location.hostname;
  if (host !== "localhost" && host !== "127.0.0.1") return {};
  const token = localStorage.getItem("trusted_proxy_token") || "internal-gateway";
  return { "x-gaokao-trusted-proxy": token };
}

export function getAdminHeaders(extraHeaders: Record<string, string> = {}): Record<string, string> {
  const token = localStorage.getItem("admin_token");
  const role = localStorage.getItem("admin_role") || "admin";
  const userId = localStorage.getItem("admin_user_id") || "admin";
  const campus = localStorage.getItem("admin_campus") || "all";
  return {
    "Content-Type": "application/json",
    "x-gaokao-role": role,
    "x-gaokao-user-id": userId,
    "x-gaokao-campus": campus,
    "x-gaokao-auth-level": "admin",
    ...getTrustedProxyHeader(),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    "X-Admin-Role": role,
    ...extraHeaders,
  };
}

async function handleApiResponse(response: Response): Promise<unknown> {
  const data = await response.json();
  if (!response.ok) {
    const msg = data?.error || data?.message || `API Error (${response.status})`;
    throw new Error(msg);
  }
  return data;
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function asArray<T extends BaseRecord = BaseRecord>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

function unwrapResult<T extends BaseRecord = BaseRecord>(result: unknown): T {
  const record = asRecord(result);
  return asRecord(record.data ?? record) as T;
}

function unwrapList<T extends BaseRecord = BaseRecord>(result: unknown): T[] {
  const record = asRecord(result);
  const initial = record.data ?? record;
  if (Array.isArray(initial)) return asArray<T>(initial);
  const nested = asRecord(initial);
  for (const key of Object.keys(nested)) {
    if (Array.isArray(nested[key])) {
      return asArray<T>(nested[key]);
    }
  }
  return [];
}

export async function adminMutation(path: string, payload?: Record<string, unknown>): Promise<Record<string, unknown>> {
  const token = await fetchCsrfToken();
  if (!token) {
    throw new Error("CSRF token unavailable for admin mutation");
  }
  const response = await fetch(path, {
    method: "POST",
    headers: getCsrfHeaders(),
    body: JSON.stringify(payload || {}),
  });
  const data = await handleApiResponse(response);
  return asRecord(data);
}

export const dataProvider: DataProvider = {
  getApiUrl: () => "",

  getList: async <TData extends BaseRecord = BaseRecord>({
    resource,
    pagination,
    sorters,
    filters: _filters,
  }: GetListParams) => {
    const url = getUrl(resource);
    const params = new URLSearchParams();

    if (pagination) {
      const offset = ((pagination.current || 1) - 1) * (pagination.pageSize || 20);
      params.set("offset", String(offset));
      params.set("limit", String(pagination.pageSize || 20));
    }

    if (sorters && sorters.length > 0) {
      params.set("sort", sorters[0].field);
      params.set("order", sorters[0].order);
    }

    const qs = params.toString();
    const fullUrl = qs ? `${url}?${qs}` : url;

    const response = await fetch(fullUrl, { headers: getAdminHeaders() });
    const result = await handleApiResponse(response);
    const record = asRecord(result);
    const data = unwrapList<TData>(result);
    const total = typeof record.total === "number" ? record.total : data.length;

    return { data: Array.isArray(data) ? data : ([] as TData[]), total };
  },

  getOne: async <TData extends BaseRecord = BaseRecord>({
    resource,
    id,
  }: GetOneParams) => {
    const url = getUrl(resource, id);
    const response = await fetch(url, { headers: getAdminHeaders() });
    const result = await handleApiResponse(response);
    return { data: unwrapResult<TData>(result) };
  },

  create: async <TData extends BaseRecord = BaseRecord, TVariables = Record<string, unknown>>({
    resource,
    variables,
  }: CreateParams<TVariables>) => {
    const url = getUrl(resource);
    const response = await fetch(url, {
      method: "POST",
      headers: getAdminHeaders(),
      body: JSON.stringify(variables),
    });
    const result = await handleApiResponse(response);
    return { data: unwrapResult<TData>(result) };
  },

  update: async <TData extends BaseRecord = BaseRecord, TVariables = Record<string, unknown>>({
    resource,
    id,
    variables,
  }: UpdateParams<TVariables>) => {
    const url = getUrl(resource, id);
    const response = await fetch(url, {
      method: "PATCH",
      headers: getAdminHeaders(),
      body: JSON.stringify(variables),
    });
    const result = await handleApiResponse(response);
    return { data: unwrapResult<TData>(result) };
  },

  deleteOne: async <TData extends BaseRecord = BaseRecord, TVariables = Record<string, unknown>>({
    resource,
    id,
  }: DeleteOneParams<TVariables>) => {
    const url = getUrl(resource, id);
    const response = await fetch(url, {
      method: "DELETE",
      headers: getAdminHeaders(),
    });
    const result = await handleApiResponse(response);
    return { data: unwrapResult<TData>(result) };
  },

  getMany: async <TData extends BaseRecord = BaseRecord>({
    resource,
    ids,
  }: GetManyParams) => {
    const url = getUrl(resource);
    const params = new URLSearchParams();
    ids?.forEach((id: string | number) => params.append("id", String(id)));
    const response = await fetch(`${url}?${params.toString()}`, { headers: getAdminHeaders() });
    const result = await handleApiResponse(response);
    return { data: unwrapList<TData>(result) };
  },

  custom: async <
    TData extends BaseRecord = BaseRecord,
    TQuery = Record<string, string | number | boolean>,
    TPayload = Record<string, unknown>
  >({
    url,
    method,
    payload,
    query,
    headers,
  }: CustomParams<TQuery, TPayload>) => {
    const qs = query ? "?" + new URLSearchParams(query).toString() : "";
    const response = await fetch(`${url}${qs}`, {
      method: method || "GET",
      headers: getAdminHeaders(headers as Record<string, string>),
      body: payload ? JSON.stringify(payload) : undefined,
    });
    const result = await handleApiResponse(response);
    return { data: unwrapResult<TData>(result) };
  },
};
